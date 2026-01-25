"""
Brand Partnership Crawler
Builds comprehensive database of brand-athlete partnerships (NIL + Pro)
"""

import logging
import uuid
import asyncio
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from gravity.crawlers.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class BrandPartnershipCrawler(BaseCrawler):
    """
    Crawl brand websites for athlete partnerships (NIL + Pro)
    """
    
    def __init__(self):
        super().__init__(rate_limit_delay=1.0)  # Brand sites can be slower
        
        # Brand roster URLs (100+ major brands)
        self.brand_rosters = [
            {'name': 'Nike', 'url': 'https://www.nike.com/athletes', 'sport': 'all'},
            {'name': 'Gatorade', 'url': 'https://www.gatorade.com/athletes', 'sport': 'all'},
            {'name': 'Red Bull', 'url': 'https://www.redbull.com/athletes', 'sport': 'all'},
            {'name': 'Adidas', 'url': 'https://www.adidas.com/us/athletes', 'sport': 'all'},
            {'name': 'Under Armour', 'url': 'https://www.underarmour.com/en-us/athletes', 'sport': 'all'},
            {'name': 'Jordan', 'url': 'https://www.nike.com/jordan/athletes', 'sport': 'all'},
            {'name': 'Puma', 'url': 'https://us.puma.com/athletes', 'sport': 'all'},
            {'name': 'New Balance', 'url': 'https://www.newbalance.com/athletes', 'sport': 'all'},
            # Add more brands as needed
        ]
    
    def get_crawler_name(self) -> str:
        return "brand_partnership"
    
    def get_supported_sports(self) -> List[str]:
        return ['nfl', 'nba', 'cfb', 'ncaab', 'mlb', 'nhl', 'wnba']
    
    async def crawl(
        self,
        athlete_id: Optional[uuid.UUID] = None,
        athlete_name: Optional[str] = None,
        sport: Optional[str] = None,
        brand_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Crawl brand rosters for athlete partnerships
        
        Args:
            athlete_id: Optional athlete UUID (if provided, checks if athlete is on any brand roster)
            athlete_name: Optional athlete name
            sport: Optional sport filter
            brand_name: Optional specific brand to check
            **kwargs: Additional parameters
        
        Returns:
            Crawl result dict
        """
        try:
            # If athlete_id provided, check if athlete is on any brand roster
            if athlete_id:
                return await self._check_athlete_brands(athlete_id, athlete_name, sport)
            
            # If brand_name provided, crawl that specific brand
            if brand_name:
                return await self._crawl_brand_roster(brand_name)
            
            # Otherwise, crawl all brand rosters
            return await self._crawl_all_brands()
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Crawl failed: {e}")
            return self.create_crawl_result(
                success=False,
                errors=[str(e)]
            )
    
    async def _check_athlete_brands(
        self,
        athlete_id: uuid.UUID,
        athlete_name: Optional[str],
        sport: Optional[str]
    ) -> Dict[str, Any]:
        """Check if athlete is on any brand roster"""
        try:
            # Get athlete info
            athlete_info = self.get_athlete_info(athlete_id)
            if not athlete_info:
                return self.create_crawl_result(
                    success=False,
                    errors=[f"Athlete not found: {athlete_id}"]
                )
            
            athlete_name = athlete_info['name']
            sport = athlete_info.get('sport', sport)
            
            logger.info(f"{self.crawler_name}: Checking brand rosters for {athlete_name}")
            
            events_created = 0
            errors = []
            brands_found = []
            
            # Check each brand roster
            for brand in self.brand_rosters:
                try:
                    # Skip if sport-specific filter doesn't match
                    if brand.get('sport') != 'all' and brand.get('sport') != sport:
                        continue
                    
                    is_on_roster = await self._check_brand_roster(
                        brand['url'],
                        athlete_name
                    )
                    
                    if is_on_roster:
                        brands_found.append(brand['name'])
                        
                        # Store brand endorsement event
                        event_id = await self.store_event(
                            athlete_id=athlete_id,
                            event_type='brand_endorsement',
                            event_data={
                                'brand': brand['name'],
                                'source': brand['url'],
                                'is_verified': True,  # From official brand site
                                'is_national': True,
                                'partnership_type': 'endorsement'
                            },
                            event_timestamp=datetime.utcnow(),
                            source=brand['name'].lower()
                        )
                        
                        if event_id:
                            events_created += 1
                            await self.trigger_score_recalculation(athlete_id, 'brand_endorsement')
                            
                            # Also create/update NIL deal record
                            await self._create_nil_deal(athlete_id, brand['name'], brand['url'])
                
                except Exception as e:
                    error_msg = f"Brand {brand['name']} check failed: {e}"
                    logger.error(f"{self.crawler_name}: {error_msg}")
                    errors.append(error_msg)
            
            return self.create_crawl_result(
                success=True,
                events_created=events_created,
                errors=errors if errors else None,
                metadata={
                    'brands_found': brands_found,
                    'brands_checked': len(self.brand_rosters)
                }
            )
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Athlete brand check failed: {e}")
            return self.create_crawl_result(
                success=False,
                errors=[str(e)]
            )
    
    async def _crawl_brand_roster(self, brand_name: str) -> Dict[str, Any]:
        """Crawl a specific brand's athlete roster"""
        try:
            # Find brand in roster list
            brand = next((b for b in self.brand_rosters if b['name'].lower() == brand_name.lower()), None)
            
            if not brand:
                return self.create_crawl_result(
                    success=False,
                    errors=[f"Brand not found: {brand_name}"]
                )
            
            logger.info(f"{self.crawler_name}: Crawling {brand['name']} roster")
            
            # Scrape brand roster page
            athletes = await self._extract_athletes_from_roster(brand['url'], brand['name'])
            
            events_created = 0
            errors = []
            
            # For each athlete found, create/update partnership
            for athlete_name in athletes:
                try:
                    athlete_id = self.find_athlete_by_name(athlete_name)
                    
                    if athlete_id:
                        event_id = await self.store_event(
                            athlete_id=athlete_id,
                            event_type='brand_endorsement',
                            event_data={
                                'brand': brand['name'],
                                'source': brand['url'],
                                'is_verified': True,
                                'is_national': True
                            },
                            event_timestamp=datetime.utcnow(),
                            source=brand['name'].lower()
                        )
                        
                        if event_id:
                            events_created += 1
                            await self.trigger_score_recalculation(athlete_id, 'brand_endorsement')
                            await self._create_nil_deal(athlete_id, brand['name'], brand['url'])
                
                except Exception as e:
                    errors.append(f"Failed to process {athlete_name}: {e}")
            
            return self.create_crawl_result(
                success=True,
                events_created=events_created,
                errors=errors if errors else None,
                metadata={
                    'brand': brand['name'],
                    'athletes_found': len(athletes),
                    'partnerships_created': events_created
                }
            )
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Brand roster crawl failed: {e}")
            return self.create_crawl_result(
                success=False,
                errors=[str(e)]
            )
    
    async def _crawl_all_brands(self) -> Dict[str, Any]:
        """Crawl all brand rosters"""
        total_events = 0
        total_errors = []
        
        for brand in self.brand_rosters:
            try:
                result = await self._crawl_brand_roster(brand['name'])
                total_events += result.get('events_created', 0)
                if result.get('errors'):
                    total_errors.extend(result['errors'])
            except Exception as e:
                total_errors.append(f"Brand {brand['name']} failed: {e}")
        
        return self.create_crawl_result(
            success=True,
            events_created=total_events,
            errors=total_errors if total_errors else None,
            metadata={
                'brands_crawled': len(self.brand_rosters)
            }
        )
    
    async def _check_brand_roster(
        self,
        roster_url: str,
        athlete_name: str
    ) -> bool:
        """
        Check if athlete is on brand roster
        
        Args:
            roster_url: Brand roster URL
            athlete_name: Athlete name to search for
        
        Returns:
            True if athlete found on roster
        """
        try:
            # Scrape roster page with Firecrawl
            content = await self.scrape_with_firecrawl(roster_url)
            
            if not content:
                return False
            
            text = content.get('markdown', '') or content.get('content', '')
            text_lower = text.lower()
            
            # Check if athlete name appears (fuzzy match)
            name_parts = athlete_name.lower().split()
            if all(part in text_lower for part in name_parts):
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Brand roster check failed: {e}")
            return False
    
    async def _extract_athletes_from_roster(
        self,
        roster_url: str,
        brand_name: str
    ) -> List[str]:
        """
        Extract athlete names from brand roster page
        
        Args:
            roster_url: Brand roster URL
            brand_name: Brand name
        
        Returns:
            List of athlete names
        """
        try:
            # Scrape with Firecrawl
            content = await self.scrape_with_firecrawl(roster_url)
            
            if not content:
                return []
            
            text = content.get('markdown', '') or content.get('content', '')
            
            # Use AI to extract athlete names
            athletes = await self.extract_with_ai(
                text=text[:3000],  # Limit text length
                extraction_type='athlete_roster',
                context={'brand': brand_name}
            )
            
            if athletes and isinstance(athletes, list):
                return athletes
            
            # Fallback: Try regex patterns for common name formats
            # This is a simplified fallback - AI extraction is preferred
            name_pattern = r'([A-Z][a-z]+ [A-Z][a-z]+)'
            matches = re.findall(name_pattern, text)
            
            # Filter out common false positives
            false_positives = ['Brand Name', 'Athlete Name', 'View All', 'See More']
            unique_names = list(set(matches) - set(false_positives))
            
            return unique_names[:50]  # Limit to 50
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Athlete extraction failed: {e}")
            return []
    
    async def _create_nil_deal(
        self,
        athlete_id: uuid.UUID,
        brand_name: str,
        source_url: str
    ) -> None:
        """
        Create or update NIL deal record
        
        Args:
            athlete_id: Athlete UUID
            brand_name: Brand name
            source_url: Source URL
        """
        try:
            with self.storage.get_session() as session:
                from gravity.db.models import NILDeal
                from sqlalchemy import and_
                
                # Check if deal already exists
                existing_deal = session.query(NILDeal).filter(
                    and_(
                        NILDeal.athlete_id == athlete_id,
                        NILDeal.brand == brand_name
                    )
                ).first()
                
                if existing_deal:
                    # Update existing deal
                    existing_deal.is_verified = True
                    existing_deal.source_url = source_url
                    existing_deal.updated_at = datetime.utcnow()
                    session.commit()
                else:
                    # Create new deal
                    new_deal = NILDeal(
                        athlete_id=athlete_id,
                        brand=brand_name,
                        deal_type='endorsement',
                        is_national=True,
                        is_local=False,
                        source=brand_name.lower(),
                        source_url=source_url,
                        is_verified=True,
                        confidence_score=0.95,  # High confidence from official site
                        announced_date=datetime.utcnow().date()
                    )
                    session.add(new_deal)
                    session.commit()
                
                logger.debug(f"{self.crawler_name}: Created/updated NIL deal: {brand_name} for {athlete_id}")
                
        except Exception as e:
            logger.error(f"{self.crawler_name}: Failed to create NIL deal: {e}")
