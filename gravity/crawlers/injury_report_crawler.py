"""
Injury Report Crawler
Aggregates injury reports from multiple sources (ESPN, league sites, Sports Reference)
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import re

from gravity.crawlers.base_crawler import BaseCrawler
from gravity.injury_risk_analyzer import InjuryRiskAnalyzer

logger = logging.getLogger(__name__)


class InjuryReportCrawler(BaseCrawler):
    """
    Aggregate injury reports from ESPN, official league sites, and Sports Reference
    """
    
    def __init__(self):
        super().__init__(rate_limit_delay=1.0)
        self.injury_analyzer = InjuryRiskAnalyzer()
        
        # Injury report URLs by league
        self.injury_urls = {
            'nfl': [
                'https://www.espn.com/nfl/injuries',
                'https://www.nfl.com/injuries/league'
            ],
            'nba': [
                'https://www.espn.com/nba/injuries',
                'https://www.nba.com/stats/injury'
            ],
            'cfb': [
                'https://www.espn.com/college-football/injuries'
            ],
            'ncaab': [
                'https://www.espn.com/mens-college-basketball/injuries'
            ]
        }
    
    def get_crawler_name(self) -> str:
        return "injury_report"
    
    def get_supported_sports(self) -> List[str]:
        return ['nfl', 'nba', 'cfb', 'ncaab']
    
    async def crawl(
        self,
        athlete_id: Optional[uuid.UUID] = None,
        athlete_name: Optional[str] = None,
        sport: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Crawl injury reports for an athlete or league
        
        Args:
            athlete_id: Optional athlete UUID (if provided, crawls for that athlete)
            athlete_name: Optional athlete name
            sport: Sport identifier (required if crawling league-wide)
            **kwargs: Additional parameters
        
        Returns:
            Crawl result dict
        """
        try:
            # If athlete_id provided, crawl for that athlete
            if athlete_id:
                return await self._crawl_athlete_injuries(athlete_id, athlete_name, sport)
            
            # Otherwise, crawl league-wide injury reports
            if not sport:
                return self.create_crawl_result(
                    success=False,
                    errors=["sport required for league-wide crawl"]
                )
            
            return await self._crawl_league_injuries(sport)
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Crawl failed: {e}")
            return self.create_crawl_result(
                success=False,
                errors=[str(e)]
            )
    
    async def _crawl_athlete_injuries(
        self,
        athlete_id: uuid.UUID,
        athlete_name: Optional[str],
        sport: Optional[str]
    ) -> Dict[str, Any]:
        """Crawl injury reports for a specific athlete"""
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
            position = athlete_info.get('position', '')
            
            logger.info(f"{self.crawler_name}: Crawling injuries for {athlete_name} ({sport})")
            
            # Use injury risk analyzer to get injury history
            injury_data = self.injury_analyzer.analyze_injury_risk(
                athlete_name,
                position,
                sport=sport
            )
            
            events_created = 0
            errors = []
            
            # Check for current injury
            if injury_data.get('current_injury_status'):
                event_id = await self.store_event(
                    athlete_id=athlete_id,
                    event_type='injury',
                    event_data={
                        'injury_type': injury_data['current_injury_status'],
                        'status': injury_data.get('recovery_status', 'Unknown'),
                        'severity': self._classify_severity(injury_data['current_injury_status']),
                        'injury_risk_score': injury_data.get('injury_risk_score', 0),
                        'games_missed': injury_data.get('games_missed_last_season', 0)
                    },
                    event_timestamp=datetime.utcnow(),
                    source='injury_analyzer'
                )
                
                if event_id:
                    events_created += 1
                    await self.trigger_score_recalculation(athlete_id, 'injury')
            
            # Store injury history events
            for injury in injury_data.get('injury_history', [])[:5]:  # Last 5 injuries
                event_id = await self.store_event(
                    athlete_id=athlete_id,
                    event_type='injury',
                    event_data={
                        'injury_type': injury.get('injury_type', 'Unknown'),
                        'status': injury.get('status', 'Unknown'),
                        'date': injury.get('date', datetime.utcnow().isoformat()),
                        'severity': self._classify_severity(injury.get('injury_type', ''))
                    },
                    event_timestamp=self._parse_injury_date(injury.get('date')),
                    source='injury_history'
                )
                
                if event_id:
                    events_created += 1
            
            return self.create_crawl_result(
                success=True,
                events_created=events_created,
                errors=errors if errors else None,
                metadata={
                    'injury_risk_score': injury_data.get('injury_risk_score', 0),
                    'current_injury': injury_data.get('current_injury_status'),
                    'injury_history_count': injury_data.get('injury_history_count', 0)
                }
            )
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Athlete injury crawl failed: {e}")
            return self.create_crawl_result(
                success=False,
                errors=[str(e)]
            )
    
    async def _crawl_league_injuries(self, sport: str) -> Dict[str, Any]:
        """Crawl league-wide injury reports"""
        try:
            if sport not in self.injury_urls:
                return self.create_crawl_result(
                    success=False,
                    errors=[f"Unsupported sport: {sport}"]
                )
            
            logger.info(f"{self.crawler_name}: Crawling {sport.upper()} injury reports")
            
            events_created = 0
            errors = []
            
            # Crawl each injury report URL
            for url in self.injury_urls[sport]:
                try:
                    injuries = await self._scrape_injury_report(url, sport)
                    
                    for injury in injuries:
                        # Find athlete in database
                        athlete_id = self.find_athlete_by_name(
                            injury['player_name'],
                            sport
                        )
                        
                        if athlete_id:
                            event_id = await self.store_event(
                                athlete_id=athlete_id,
                                event_type='injury',
                                event_data={
                                    'injury_type': injury.get('injury_type', 'Unknown'),
                                    'status': injury.get('status', 'Unknown'),
                                    'severity': self._classify_severity(injury.get('injury_type', '')),
                                    'expected_return': injury.get('expected_return'),
                                    'source_url': url
                                },
                                event_timestamp=datetime.utcnow(),
                                source='injury_report'
                            )
                            
                            if event_id:
                                events_created += 1
                                await self.trigger_score_recalculation(athlete_id, 'injury')
                
                except Exception as e:
                    error_msg = f"Injury report scrape failed for {url}: {e}"
                    logger.error(f"{self.crawler_name}: {error_msg}")
                    errors.append(error_msg)
            
            return self.create_crawl_result(
                success=True,
                events_created=events_created,
                errors=errors if errors else None,
                metadata={
                    'sport': sport,
                    'sources_checked': len(self.injury_urls[sport])
                }
            )
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: League injury crawl failed: {e}")
            return self.create_crawl_result(
                success=False,
                errors=[str(e)]
            )
    
    async def _scrape_injury_report(
        self,
        url: str,
        sport: str
    ) -> List[Dict[str, Any]]:
        """
        Scrape injury report page
        
        Args:
            url: Injury report URL
            sport: Sport identifier
        
        Returns:
            List of injury dicts
        """
        try:
            # Scrape with Firecrawl
            content = await self.scrape_with_firecrawl(url)
            
            if not content:
                return []
            
            text = content.get('markdown', '') or content.get('content', '')
            
            # Parse injuries from text (simplified - would need proper HTML parsing)
            injuries = []
            
            # Look for injury patterns
            injury_patterns = [
                r'([A-Z][a-z]+ [A-Z][a-z]+).*?(Out|Questionable|Doubtful|Day-to-Day).*?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
                r'([A-Z][a-z]+ [A-Z][a-z]+).*?(ACL|hamstring|concussion|fracture|sprain|strain)'
            ]
            
            for pattern in injury_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    injuries.append({
                        'player_name': match.group(1),
                        'status': match.group(2) if len(match.groups()) > 1 else 'Unknown',
                        'injury_type': match.group(3) if len(match.groups()) > 2 else 'Unknown'
                    })
            
            # Deduplicate
            seen = set()
            unique_injuries = []
            for injury in injuries:
                key = (injury['player_name'], injury['injury_type'])
                if key not in seen:
                    seen.add(key)
                    unique_injuries.append(injury)
            
            return unique_injuries
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Injury report scrape failed: {e}")
            return []
    
    def _classify_severity(self, injury_type: str) -> str:
        """
        Classify injury severity
        
        Args:
            injury_type: Injury type string
        
        Returns:
            'high', 'medium', or 'low'
        """
        if not injury_type:
            return 'unknown'
        
        injury_lower = injury_type.lower()
        
        # High severity
        if any(keyword in injury_lower for keyword in ['acl', 'achilles', 'concussion', 'torn', 'fracture', 'broken', 'surgery']):
            return 'high'
        
        # Medium severity
        if any(keyword in injury_lower for keyword in ['sprain', 'strain', 'hamstring', 'groin', 'ankle', 'knee', 'shoulder', 'back']):
            return 'medium'
        
        # Low severity
        if any(keyword in injury_lower for keyword in ['bruise', 'contusion', 'soreness', 'rest']):
            return 'low'
        
        return 'unknown'
    
    def _parse_injury_date(self, date_str: Optional[str]) -> datetime:
        """Parse injury date string"""
        if not date_str:
            return datetime.utcnow()
        
        if isinstance(date_str, datetime):
            return date_str
        
        try:
            return datetime.fromisoformat(date_str)
        except:
            return datetime.utcnow()
