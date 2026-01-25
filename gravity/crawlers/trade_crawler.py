"""
Trade Crawler
Tracks athlete trades across all professional sports (NFL, NBA, MLB, NHL)
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import re

from gravity.crawlers.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class TradeCrawler(BaseCrawler):
    """
    Monitor trade trackers and official league transaction feeds
    """
    
    def __init__(self):
        super().__init__(rate_limit_delay=0.5)  # Faster during trade deadlines
        
        # Trade tracker URLs by sport
        self.trade_urls = {
            'nfl': [
                'https://www.espn.com/nfl/transactions',
                'https://www.nfl.com/transactions'
            ],
            'nba': [
                'https://www.espn.com/nba/transactions',
                'https://www.nba.com/transactions'
            ],
            'mlb': [
                'https://www.espn.com/mlb/transactions',
                'https://www.mlb.com/transactions'
            ],
            'nhl': [
                'https://www.espn.com/nhl/transactions',
                'https://www.nhl.com/transactions'
            ]
        }
        
        # Trade deadline dates (approximate, should be updated annually)
        self.trade_deadlines = {
            'nfl': {'month': 10, 'day': 31},  # October 31
            'nba': {'month': 2, 'day': 8},    # February 8
            'mlb': {'month': 7, 'day': 31},   # July 31
            'nhl': {'month': 3, 'day': 8}     # March 8
        }
    
    def get_crawler_name(self) -> str:
        return "trade"
    
    def get_supported_sports(self) -> List[str]:
        return ['nfl', 'nba', 'mlb', 'nhl']
    
    def is_trade_deadline_active(self, sport: str) -> bool:
        """
        Check if trade deadline is currently active (within 7 days)
        
        Args:
            sport: Sport identifier
        
        Returns:
            True if trade deadline is active
        """
        if sport not in self.trade_deadlines:
            return False
        
        deadline = self.trade_deadlines[sport]
        now = datetime.now()
        deadline_date = datetime(now.year, deadline['month'], deadline['day'])
        
        # Check if within 7 days before or after deadline
        days_until = (deadline_date - now).days
        return abs(days_until) <= 7
    
    async def crawl(
        self,
        athlete_id: Optional[uuid.UUID] = None,
        athlete_name: Optional[str] = None,
        sport: Optional[str] = None,
        high_frequency: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Crawl trade information
        
        Args:
            athlete_id: Optional athlete UUID (if provided, checks for that athlete's trades)
            athlete_name: Optional athlete name
            sport: Sport identifier (required for league-wide crawl)
            high_frequency: If True, runs more frequently (for trade deadlines)
            **kwargs: Additional parameters
        
        Returns:
            Crawl result dict
        """
        try:
            # If athlete_id provided, check for that athlete's trades
            if athlete_id:
                return await self._check_athlete_trades(athlete_id, athlete_name, sport)
            
            # Otherwise, crawl league-wide transactions
            if not sport:
                return self.create_crawl_result(
                    success=False,
                    errors=["sport required for league-wide crawl"]
                )
            
            return await self._crawl_league_trades(sport, high_frequency)
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Crawl failed: {e}")
            return self.create_crawl_result(
                success=False,
                errors=[str(e)]
            )
    
    async def _check_athlete_trades(
        self,
        athlete_id: uuid.UUID,
        athlete_name: Optional[str],
        sport: Optional[str]
    ) -> Dict[str, Any]:
        """Check for trades involving a specific athlete"""
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
            current_team = athlete_info.get('school') or athlete_info.get('team', '')
            
            if sport not in self.trade_urls:
                return self.create_crawl_result(
                    success=True,
                    events_created=0,
                    metadata={'reason': 'not_professional_sport'}
                )
            
            logger.info(f"{self.crawler_name}: Checking trades for {athlete_name} ({sport})")
            
            events_created = 0
            errors = []
            
            # Check each trade source
            for url in self.trade_urls[sport]:
                try:
                    trades = await self._scrape_trade_page(url, athlete_name, sport)
                    
                    for trade in trades:
                        event_id = await self.store_event(
                            athlete_id=athlete_id,
                            event_type='trade_completed',
                            event_data={
                                'trade_date': trade.get('date', datetime.utcnow().isoformat()),
                                'from_team': trade.get('from_team', current_team),
                                'to_team': trade.get('to_team', ''),
                                'trade_type': trade.get('trade_type', 'trade'),
                                'involved_players': trade.get('involved_players', []),
                                'draft_picks': trade.get('draft_picks', []),
                                'source_url': url
                            },
                            event_timestamp=self._parse_trade_date(trade.get('date')),
                            source='trade_tracker'
                        )
                        
                        if event_id:
                            events_created += 1
                            await self.trigger_score_recalculation(athlete_id, 'trade_completed')
                            
                            # Update athlete's team
                            await self._update_athlete_team(athlete_id, trade.get('to_team'))
                
                except Exception as e:
                    error_msg = f"Trade page scrape failed for {url}: {e}"
                    logger.error(f"{self.crawler_name}: {error_msg}")
                    errors.append(error_msg)
            
            return self.create_crawl_result(
                success=True,
                events_created=events_created,
                errors=errors if errors else None,
                metadata={
                    'sport': sport,
                    'trades_found': events_created
                }
            )
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Athlete trade check failed: {e}")
            return self.create_crawl_result(
                success=False,
                errors=[str(e)]
            )
    
    async def _crawl_league_trades(
        self,
        sport: str,
        high_frequency: bool = False
    ) -> Dict[str, Any]:
        """Crawl league-wide transactions"""
        try:
            if sport not in self.trade_urls:
                return self.create_crawl_result(
                    success=False,
                    errors=[f"Unsupported sport: {sport}"]
                )
            
            logger.info(f"{self.crawler_name}: Crawling {sport.upper()} transactions")
            
            events_created = 0
            errors = []
            
            # Crawl each transaction source
            for url in self.trade_urls[sport]:
                try:
                    trades = await self._scrape_trade_page(url, None, sport)
                    
                    for trade in trades:
                        # Find athletes involved in trade
                        for player_name in trade.get('involved_players', []):
                            athlete_id = self.find_athlete_by_name(player_name, sport)
                            
                            if athlete_id:
                                event_id = await self.store_event(
                                    athlete_id=athlete_id,
                                    event_type='trade_completed',
                                    event_data={
                                        'trade_date': trade.get('date', datetime.utcnow().isoformat()),
                                        'from_team': trade.get('from_team', ''),
                                        'to_team': trade.get('to_team', ''),
                                        'trade_type': trade.get('trade_type', 'trade'),
                                        'involved_players': trade.get('involved_players', []),
                                        'draft_picks': trade.get('draft_picks', []),
                                        'source_url': url
                                    },
                                    event_timestamp=self._parse_trade_date(trade.get('date')),
                                    source='trade_tracker'
                                )
                                
                                if event_id:
                                    events_created += 1
                                    await self.trigger_score_recalculation(athlete_id, 'trade_completed')
                                    await self._update_athlete_team(athlete_id, trade.get('to_team'))
                
                except Exception as e:
                    error_msg = f"Transaction page scrape failed for {url}: {e}"
                    logger.error(f"{self.crawler_name}: {error_msg}")
                    errors.append(error_msg)
            
            return self.create_crawl_result(
                success=True,
                events_created=events_created,
                errors=errors if errors else None,
                metadata={
                    'sport': sport,
                    'sources_checked': len(self.trade_urls[sport]),
                    'trades_found': events_created
                }
            )
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: League trade crawl failed: {e}")
            return self.create_crawl_result(
                success=False,
                errors=[str(e)]
            )
    
    async def _scrape_trade_page(
        self,
        url: str,
        athlete_name: Optional[str],
        sport: str
    ) -> List[Dict[str, Any]]:
        """
        Scrape trade/transaction page
        
        Args:
            url: Transaction page URL
            athlete_name: Optional athlete name to filter
            sport: Sport identifier
        
        Returns:
            List of trade dicts
        """
        try:
            # Scrape with Firecrawl
            content = await self.scrape_with_firecrawl(url)
            
            if not content:
                return []
            
            text = content.get('markdown', '') or content.get('content', '')
            
            # Use AI to extract trade information
            if athlete_name:
                # Extract trades for specific athlete
                trades = await self.extract_with_ai(
                    text=text[:3000],
                    extraction_type='trade_info',
                    context={'athlete_name': athlete_name}
                )
                
                if trades and isinstance(trades, dict):
                    return [trades]  # Single trade
                elif trades and isinstance(trades, list):
                    return trades
            else:
                # Extract all trades from page
                # This would need a different AI prompt or regex parsing
                # For now, use regex fallback
                trades = self._extract_trades_regex(text, sport)
                return trades
            
            return []
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Trade page scrape failed: {e}")
            return []
    
    def _extract_trades_regex(
        self,
        text: str,
        sport: str
    ) -> List[Dict[str, Any]]:
        """
        Extract trades using regex patterns (fallback)
        
        Args:
            text: Page text
            sport: Sport identifier
        
        Returns:
            List of trade dicts
        """
        trades = []
        
        # Common trade patterns
        trade_patterns = [
            r'([A-Z][a-z]+ [A-Z][a-z]+).*?traded.*?to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'([A-Z][a-z]+ [A-Z][a-z]+).*?acquired.*?by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'([A-Z][a-z]+ [A-Z][a-z]+).*?signed.*?with\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
        ]
        
        for pattern in trade_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                trades.append({
                    'player_name': match.group(1),
                    'to_team': match.group(2),
                    'trade_type': 'trade',
                    'date': datetime.utcnow().isoformat()
                })
        
        # Deduplicate
        seen = set()
        unique_trades = []
        for trade in trades:
            key = (trade['player_name'], trade['to_team'])
            if key not in seen:
                seen.add(key)
                unique_trades.append(trade)
        
        return unique_trades
    
    async def _update_athlete_team(
        self,
        athlete_id: uuid.UUID,
        new_team: str
    ) -> None:
        """
        Update athlete's team in database
        
        Args:
            athlete_id: Athlete UUID
            new_team: New team name
        """
        try:
            with self.storage.get_session() as session:
                from gravity.db.models import Athlete
                
                athlete = session.query(Athlete).filter(
                    Athlete.athlete_id == athlete_id
                ).first()
                
                if athlete:
                    # Update team (or school for college athletes)
                    if athlete.sport in ['cfb', 'ncaab']:
                        athlete.school = new_team
                    else:
                        # For pro sports, might need a separate team field
                        # For now, update metadata
                        if not athlete.metadata:
                            athlete.metadata = {}
                        athlete.metadata['current_team'] = new_team
                        athlete.metadata['previous_teams'] = athlete.metadata.get('previous_teams', [])
                        if athlete.school:
                            athlete.metadata['previous_teams'].append(athlete.school)
                    
                    athlete.updated_at = datetime.utcnow()
                    session.commit()
                    
                    logger.debug(f"{self.crawler_name}: Updated team for {athlete_id}: {new_team}")
                
        except Exception as e:
            logger.error(f"{self.crawler_name}: Failed to update athlete team: {e}")
    
    def _parse_trade_date(self, date_str: Optional[str]) -> datetime:
        """Parse trade date string"""
        if not date_str:
            return datetime.utcnow()
        
        if isinstance(date_str, datetime):
            return date_str
        
        try:
            return datetime.fromisoformat(date_str)
        except:
            return datetime.utcnow()
