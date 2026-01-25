"""
Transfer Portal Crawler
Monitors CFB transfer portal for athlete entries, commitments, and withdrawals
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import re

from gravity.crawlers.base_crawler import BaseCrawler
from gravity.nil.connectors.on3_connector import On3Connector
from gravity.nil.connectors.sports247_connector import Sports247Connector
from gravity.nil.connectors.rivals_connector import RivalsConnector

logger = logging.getLogger(__name__)


class TransferPortalCrawler(BaseCrawler):
    """
    Monitor transfer portal databases for CFB athlete movements
    """
    
    def __init__(self):
        super().__init__(rate_limit_delay=0.5)  # Faster for time-sensitive data
        # Initialize connectors for transfer portal sources
        self.on3_connector = On3Connector()
        self.sports247_connector = Sports247Connector()
        self.rivals_connector = RivalsConnector()
    
    def get_crawler_name(self) -> str:
        return "transfer_portal"
    
    def get_supported_sports(self) -> List[str]:
        return ['cfb']  # Transfer portal is primarily CFB
    
    async def crawl(
        self,
        athlete_id: Optional[uuid.UUID] = None,
        athlete_name: Optional[str] = None,
        sport: Optional[str] = None,
        school: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Monitor transfer portal for athlete entries
        
        Args:
            athlete_id: Optional athlete UUID
            athlete_name: Athlete name (required if athlete_id not provided)
            sport: Sport (should be 'cfb')
            school: Optional school name
            **kwargs: Additional parameters
        
        Returns:
            Crawl result dict
        """
        try:
            # Resolve athlete_id if not provided
            if not athlete_id and athlete_name:
                athlete_id = self.find_athlete_by_name(athlete_name, sport)
                if not athlete_id:
                    logger.warning(f"{self.crawler_name}: Athlete not found: {athlete_name}")
                    return self.create_crawl_result(
                        success=False,
                        errors=[f"Athlete not found: {athlete_name}"]
                    )
            
            if not athlete_id:
                return self.create_crawl_result(
                    success=False,
                    errors=["athlete_id or athlete_name required"]
                )
            
            # Get athlete info
            athlete_info = self.get_athlete_info(athlete_id)
            if not athlete_info:
                return self.create_crawl_result(
                    success=False,
                    errors=[f"Athlete not found: {athlete_id}"]
                )
            
            athlete_name = athlete_info['name']
            school = athlete_info.get('school', school)
            sport = athlete_info.get('sport', sport)
            
            if sport != 'cfb':
                logger.info(f"{self.crawler_name}: Skipping {athlete_name} - not CFB")
                return self.create_crawl_result(
                    success=True,
                    events_created=0,
                    metadata={'reason': 'not_cfb'}
                )
            
            logger.info(f"{self.crawler_name}: Monitoring transfer portal for {athlete_name} ({school})")
            
            events_created = 0
            errors = []
            
            # Check each transfer portal source
            portal_sources = [
                ('on3', self._check_on3_portal),
                ('247sports', self._check_247sports_portal),
                ('rivals', self._check_rivals_portal),
                ('espn', self._check_espn_portal)
            ]
            
            for source_name, check_func in portal_sources:
                try:
                    portal_entry = await check_func(athlete_name, school)
                    
                    if portal_entry:
                        # Store transfer portal entry event
                        event_id = await self.store_event(
                            athlete_id=athlete_id,
                            event_type='transfer_portal_entry',
                            event_data={
                                'source': source_name,
                                'previous_school': school,
                                'portal_date': portal_entry.get('date', datetime.utcnow().isoformat()),
                                'status': portal_entry.get('status', 'active'),
                                'source_url': portal_entry.get('url', '')
                            },
                            event_timestamp=datetime.utcnow(),
                            source=source_name
                        )
                        
                        if event_id:
                            events_created += 1
                            # Trigger score recalculation (Risk and Proximity)
                            await self.trigger_score_recalculation(athlete_id, 'transfer_portal_entry')
                            
                            # Update feature snapshot
                            await self._update_transfer_portal_status(athlete_id, 'active')
                            
                except Exception as e:
                    error_msg = f"{source_name} portal check failed: {e}"
                    logger.error(f"{self.crawler_name}: {error_msg}")
                    errors.append(error_msg)
            
            return self.create_crawl_result(
                success=True,
                events_created=events_created,
                errors=errors if errors else None,
                metadata={
                    'sources_checked': len(portal_sources),
                    'portal_entries_found': events_created
                }
            )
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Crawl failed: {e}")
            return self.create_crawl_result(
                success=False,
                errors=[str(e)]
            )
    
    async def _check_on3_portal(
        self,
        athlete_name: str,
        school: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Check On3 transfer portal"""
        try:
            # Use On3 connector to search for athlete
            raw_data = await self.on3_connector.fetch_raw_async(athlete_name, school, 'football')
            
            if raw_data:
                text = raw_data.get('search_html', '') + ' ' + (raw_data.get('profile_data', '') or '')
                text_lower = text.lower()
                
                # Check for transfer portal keywords
                if any(keyword in text_lower for keyword in ['transfer portal', 'entered portal', 'portal entry']):
                    return {
                        'date': datetime.utcnow().isoformat(),
                        'status': 'active',
                        'url': raw_data.get('profile_url', '')
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: On3 portal check failed: {e}")
            return None
    
    async def _check_247sports_portal(
        self,
        athlete_name: str,
        school: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Check 247Sports transfer portal"""
        try:
            raw_data = await self.sports247_connector.fetch_raw_async(athlete_name, school, 'football')
            
            if raw_data:
                text = raw_data.get('search_results', '') + ' ' + (raw_data.get('profile_data', '') or '')
                text_lower = text.lower()
                
                if any(keyword in text_lower for keyword in ['transfer portal', 'entered portal']):
                    return {
                        'date': datetime.utcnow().isoformat(),
                        'status': 'active',
                        'url': raw_data.get('profile_url', '')
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: 247Sports portal check failed: {e}")
            return None
    
    async def _check_rivals_portal(
        self,
        athlete_name: str,
        school: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Check Rivals transfer portal"""
        try:
            raw_data = await self.rivals_connector.fetch_raw_async(athlete_name, school, 'football')
            
            if raw_data:
                text = raw_data.get('search_results', '') + ' ' + (raw_data.get('profile_data', '') or '')
                text_lower = text.lower()
                
                if any(keyword in text_lower for keyword in ['transfer portal', 'entered portal']):
                    return {
                        'date': datetime.utcnow().isoformat(),
                        'status': 'active',
                        'url': raw_data.get('profile_url', '')
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Rivals portal check failed: {e}")
            return None
    
    async def _check_espn_portal(
        self,
        athlete_name: str,
        school: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Check ESPN transfer tracker"""
        try:
            # ESPN transfer tracker URL
            espn_url = "https://www.espn.com/college-football/transfers"
            
            # Scrape with Firecrawl
            content = await self.scrape_with_firecrawl(espn_url)
            
            if content:
                text = content.get('markdown', '') or content.get('content', '')
                text_lower = text.lower()
                
                # Check if athlete name appears in transfer list
                if athlete_name.lower() in text_lower:
                    # Try to extract transfer date
                    date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', text)
                    transfer_date = date_match.group(1) if date_match else datetime.utcnow().isoformat()
                    
                    return {
                        'date': transfer_date,
                        'status': 'active',
                        'url': espn_url
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: ESPN portal check failed: {e}")
            return None
    
    async def _update_transfer_portal_status(
        self,
        athlete_id: uuid.UUID,
        status: str
    ) -> None:
        """
        Update transfer portal status in feature snapshot
        
        Args:
            athlete_id: Athlete UUID
            status: Portal status ('active', 'committed', 'withdrawn')
        """
        try:
            # This would update the feature_snapshots table
            # For now, we'll rely on the event processor to handle this
            # when it recalculates features
            logger.debug(f"{self.crawler_name}: Transfer portal status update queued for {athlete_id}")
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Failed to update portal status: {e}")
