"""
Game Stats Crawler
Continuously updates game-by-game performance statistics for all sports
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import re

from gravity.crawlers.base_crawler import BaseCrawler
from gravity.nba_stats_collector import NBAStatsCollector

logger = logging.getLogger(__name__)


class GameStatsCrawler(BaseCrawler):
    """
    Monitor and update game-by-game performance statistics
    """
    
    def __init__(self):
        super().__init__(rate_limit_delay=0.5)  # Faster for stats updates
        self.nba_stats_collector = NBAStatsCollector(None)  # Pass scraper if needed
        
        # Box score URLs by sport
        self.box_score_urls = {
            'nfl': 'https://www.espn.com/nfl/scoreboard',
            'nba': 'https://www.espn.com/nba/scoreboard',
            'cfb': 'https://www.espn.com/college-football/scoreboard',
            'ncaab': 'https://www.espn.com/mens-college-basketball/scoreboard'
        }
    
    def get_crawler_name(self) -> str:
        return "game_stats"
    
    def get_supported_sports(self) -> List[str]:
        return ['nfl', 'nba', 'cfb', 'ncaab', 'mlb', 'nhl']
    
    async def crawl(
        self,
        athlete_id: Optional[uuid.UUID] = None,
        athlete_name: Optional[str] = None,
        sport: Optional[str] = None,
        date: Optional[datetime] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Crawl game stats for an athlete or league
        
        Args:
            athlete_id: Optional athlete UUID (if provided, crawls for that athlete)
            athlete_name: Optional athlete name
            sport: Sport identifier (required if crawling league-wide)
            date: Optional date to crawl (defaults to today/yesterday)
            **kwargs: Additional parameters
        
        Returns:
            Crawl result dict
        """
        try:
            # If athlete_id provided, crawl for that athlete
            if athlete_id:
                return await self._crawl_athlete_stats(athlete_id, athlete_name, sport, date)
            
            # Otherwise, crawl league-wide completed games
            if not sport:
                return self.create_crawl_result(
                    success=False,
                    errors=["sport required for league-wide crawl"]
                )
            
            return await self._crawl_league_stats(sport, date)
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Crawl failed: {e}")
            return self.create_crawl_result(
                success=False,
                errors=[str(e)]
            )
    
    async def _crawl_athlete_stats(
        self,
        athlete_id: uuid.UUID,
        athlete_name: Optional[str],
        sport: Optional[str],
        date: Optional[datetime]
    ) -> Dict[str, Any]:
        """Crawl game stats for a specific athlete"""
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
            
            logger.info(f"{self.crawler_name}: Crawling game stats for {athlete_name} ({sport})")
            
            events_created = 0
            errors = []
            
            # Get recent games (last 10 games)
            recent_games = await self._get_recent_games(athlete_name, sport, position, limit=10)
            
            for game in recent_games:
                try:
                    # Store game stats event
                    event_id = await self.store_event(
                        athlete_id=athlete_id,
                        event_type='game_stats',
                        event_data={
                            'game_date': game.get('date', datetime.utcnow().isoformat()),
                            'opponent': game.get('opponent', ''),
                            'team': game.get('team', ''),
                            'stats': game.get('stats', {}),
                            'game_result': game.get('result', ''),
                            'team_score': game.get('team_score'),
                            'opponent_score': game.get('opponent_score'),
                            'sport': sport
                        },
                        event_timestamp=self._parse_game_date(game.get('date')),
                        source='game_stats'
                    )
                    
                    if event_id:
                        events_created += 1
                        await self.trigger_score_recalculation(athlete_id, 'game_stats')
                
                except Exception as e:
                    error_msg = f"Failed to process game {game.get('date')}: {e}"
                    logger.error(f"{self.crawler_name}: {error_msg}")
                    errors.append(error_msg)
            
            # Update feature snapshot with recent games
            await self._update_recent_games_stats(athlete_id, recent_games)
            
            return self.create_crawl_result(
                success=True,
                events_created=events_created,
                errors=errors if errors else None,
                metadata={
                    'games_found': len(recent_games),
                    'sport': sport
                }
            )
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Athlete stats crawl failed: {e}")
            return self.create_crawl_result(
                success=False,
                errors=[str(e)]
            )
    
    async def _crawl_league_stats(
        self,
        sport: str,
        date: Optional[datetime]
    ) -> Dict[str, Any]:
        """Crawl league-wide completed games"""
        try:
            if sport not in self.box_score_urls:
                return self.create_crawl_result(
                    success=False,
                    errors=[f"Unsupported sport: {sport}"]
                )
            
            if not date:
                # Default to yesterday (most recent completed games)
                date = datetime.utcnow() - timedelta(days=1)
            
            logger.info(f"{self.crawler_name}: Crawling {sport.upper()} games for {date.date()}")
            
            # Get completed games for date
            games = await self._get_completed_games(sport, date)
            
            events_created = 0
            errors = []
            
            # Process each game
            for game in games:
                try:
                    # Get box score for game
                    box_score = await self._get_box_score(game['game_id'], sport)
                    
                    if box_score:
                        # Process each player's stats
                        for player_stats in box_score.get('players', []):
                            athlete_name = player_stats.get('name')
                            if not athlete_name:
                                continue
                            
                            # Find athlete in database
                            athlete_id = self.find_athlete_by_name(athlete_name, sport)
                            
                            if athlete_id:
                                event_id = await self.store_event(
                                    athlete_id=athlete_id,
                                    event_type='game_stats',
                                    event_data={
                                        'game_date': game.get('date', date.isoformat()),
                                        'opponent': game.get('opponent', ''),
                                        'team': game.get('team', ''),
                                        'stats': player_stats.get('stats', {}),
                                        'game_result': game.get('result', ''),
                                        'team_score': game.get('team_score'),
                                        'opponent_score': game.get('opponent_score'),
                                        'sport': sport
                                    },
                                    event_timestamp=date,
                                    source='game_stats'
                                )
                                
                                if event_id:
                                    events_created += 1
                                    await self.trigger_score_recalculation(athlete_id, 'game_stats')
                
                except Exception as e:
                    error_msg = f"Game {game.get('game_id')} processing failed: {e}"
                    logger.error(f"{self.crawler_name}: {error_msg}")
                    errors.append(error_msg)
            
            return self.create_crawl_result(
                success=True,
                events_created=events_created,
                errors=errors if errors else None,
                metadata={
                    'sport': sport,
                    'date': date.isoformat(),
                    'games_processed': len(games)
                }
            )
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: League stats crawl failed: {e}")
            return self.create_crawl_result(
                success=False,
                errors=[str(e)]
            )
    
    async def _get_recent_games(
        self,
        athlete_name: str,
        sport: str,
        position: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent games for an athlete
        
        Args:
            athlete_name: Athlete name
            sport: Sport identifier
            position: Player position
            limit: Maximum number of games
        
        Returns:
            List of game dicts
        """
        games = []
        
        try:
            # Use sport-specific collectors
            if sport == 'nba':
                # Use NBA stats collector
                stats = self.nba_stats_collector.collect_stats(athlete_name, position)
                recent_games = stats.get('weekly_stats', []) or stats.get('recent_games', [])
                
                for game in recent_games[:limit]:
                    games.append({
                        'date': game.get('date', datetime.utcnow().isoformat()),
                        'opponent': game.get('opponent', ''),
                        'team': game.get('team', ''),
                        'stats': {
                            'points': game.get('points'),
                            'rebounds': game.get('rebounds'),
                            'assists': game.get('assists'),
                            'minutes': game.get('minutes')
                        },
                        'result': game.get('result', ''),
                        'team_score': game.get('team_score'),
                        'opponent_score': game.get('opponent_score')
                    })
            
            elif sport in ['nfl', 'cfb']:
                # For NFL/CFB, would use ESPN API or similar
                # For now, return empty - can be enhanced
                logger.debug(f"{self.crawler_name}: NFL/CFB game stats collection not yet implemented")
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Failed to get recent games: {e}")
        
        return games
    
    async def _get_completed_games(
        self,
        sport: str,
        date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get list of completed games for a date
        
        Args:
            sport: Sport identifier
            date: Date to check
        
        Returns:
            List of game dicts
        """
        games = []
        
        try:
            # Scrape scoreboard page
            scoreboard_url = self.box_score_urls.get(sport)
            if not scoreboard_url:
                return games
            
            # Add date parameter if supported
            date_str = date.strftime('%Y%m%d')
            scoreboard_url = f"{scoreboard_url}?date={date_str}"
            
            content = await self.scrape_with_firecrawl(scoreboard_url)
            
            if content:
                # Parse games from content (simplified - would need proper HTML parsing)
                # For now, return empty - can be enhanced with proper parsing
                logger.debug(f"{self.crawler_name}: Game parsing from scoreboard not yet fully implemented")
        
        except Exception as e:
            logger.error(f"{self.crawler_name}: Failed to get completed games: {e}")
        
        return games
    
    async def _get_box_score(
        self,
        game_id: str,
        sport: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get box score for a specific game
        
        Args:
            game_id: Game identifier
            sport: Sport identifier
        
        Returns:
            Box score dict or None
        """
        try:
            # Construct box score URL
            box_score_url = f"https://www.espn.com/{sport}/boxscore/_/gameId/{game_id}"
            
            # Scrape with Firecrawl
            content = await self.scrape_with_firecrawl(box_score_url)
            
            if content:
                # Parse box score (simplified - would need proper HTML parsing)
                # For now, return None - can be enhanced
                logger.debug(f"{self.crawler_name}: Box score parsing not yet fully implemented")
                return None
            
            return None
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Failed to get box score: {e}")
            return None
    
    async def _update_recent_games_stats(
        self,
        athlete_id: uuid.UUID,
        recent_games: List[Dict[str, Any]]
    ) -> None:
        """
        Update feature snapshot with recent games stats
        
        Args:
            athlete_id: Athlete UUID
            recent_games: List of recent game dicts
        """
        try:
            # This would update the feature_snapshots table
            # For now, we'll rely on the event processor to handle this
            logger.debug(f"{self.crawler_name}: Recent games stats update queued for {athlete_id}")
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Failed to update recent games stats: {e}")
    
    def _parse_game_date(self, date_str: Optional[str]) -> datetime:
        """Parse game date string"""
        if not date_str:
            return datetime.utcnow()
        
        if isinstance(date_str, datetime):
            return date_str
        
        try:
            return datetime.fromisoformat(date_str)
        except:
            return datetime.utcnow()
