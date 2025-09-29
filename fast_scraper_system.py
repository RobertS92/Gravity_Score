#!/usr/bin/env python3
"""
Fast Scraper System for NFL Gravity Pipeline
High-performance, concurrent scraping with incremental updates and intelligent caching
"""

import asyncio
import aiohttp
import threading
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import random
from dataclasses import dataclass
import json
import hashlib

# Import existing scrapers
from enhanced_nfl_scraper import EnhancedNFLScraper
from social_media_agent import SocialMediaAgent
from enhanced_db_schema import EnhancedNFLDatabase

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ScrapingTask:
    """Represents a single scraping task."""
    task_id: str
    task_type: str  # 'roster', 'player_detail', 'social_media', 'stats'
    team: str
    player_name: str = None
    priority: int = 1  # Higher number = higher priority
    retries: int = 0
    max_retries: int = 3
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class FastScraperSystem:
    """
    High-performance scraping system with the following features:
    - Concurrent/parallel processing
    - Intelligent rate limiting
    - Smart caching and deduplication
    - Incremental updates only
    - Real-time progress tracking
    - Error handling and retry logic
    - Database integration with bulk operations
    """
    
    def __init__(self, max_workers: int = 10, requests_per_second: int = 5):
        self.max_workers = max_workers
        self.requests_per_second = requests_per_second
        self.request_delay = 1.0 / requests_per_second
        
        # Initialize database
        self.db = EnhancedNFLDatabase()
        
        # Initialize scrapers
        self.nfl_scraper = EnhancedNFLScraper()
        self.social_scraper = SocialMediaAgent()
        
        # Create optimized session
        self.session = self._create_optimized_session()
        
        # Task management
        self.task_queue = []
        self.completed_tasks = []
        self.failed_tasks = []
        self.running_tasks = set()
        
        # Progress tracking
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'players_processed': 0,
            'players_updated': 0,
            'players_skipped': 0,
            'start_time': None,
            'requests_made': 0,
            'cache_hits': 0
        }
        
        # Caching system
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour
        
        # Rate limiting
        self.last_request_time = 0
        self.request_lock = threading.Lock()
        
        # NFL teams for batch processing
        self.nfl_teams = [
            'bills', 'dolphins', 'patriots', 'jets',  # AFC East
            'ravens', 'bengals', 'browns', 'steelers',  # AFC North
            'texans', 'colts', 'jaguars', 'titans',  # AFC South
            'broncos', 'chiefs', 'raiders', 'chargers',  # AFC West
            'cowboys', 'giants', 'eagles', 'commanders',  # NFC East
            'bears', 'lions', 'packers', 'vikings',  # NFC North
            'falcons', 'panthers', 'saints', 'buccaneers',  # NFC South
            '49ers', 'cardinals', 'rams', 'seahawks'  # NFC West
        ]
    
    def _create_optimized_session(self) -> requests.Session:
        """Create an optimized requests session with connection pooling and retries."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        # Configure adapter with connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=50,
            pool_maxsize=50
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1'
        })
        
        return session
    
    def _rate_limit(self):
        """Intelligent rate limiting to avoid being blocked."""
        with self.request_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            
            if time_since_last < self.request_delay:
                sleep_time = self.request_delay - time_since_last
                # Add small random jitter to avoid synchronized requests
                sleep_time += random.uniform(0, 0.1)
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()
            self.stats['requests_made'] += 1
    
    def _get_cache_key(self, task_type: str, identifier: str) -> str:
        """Generate cache key for a scraping task."""
        return hashlib.md5(f"{task_type}:{identifier}".encode()).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self.cache:
            return False
        
        cached_item = self.cache[cache_key]
        return (datetime.now() - cached_item['timestamp']).seconds < self.cache_ttl
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get data from cache if valid."""
        if self._is_cache_valid(cache_key):
            self.stats['cache_hits'] += 1
            return self.cache[cache_key]['data']
        return None
    
    def _store_in_cache(self, cache_key: str, data: Any):
        """Store data in cache with timestamp."""
        self.cache[cache_key] = {
            'data': data,
            'timestamp': datetime.now()
        }
    
    def start_comprehensive_scraping(self, teams: List[str] = None, mode: str = 'comprehensive') -> int:
        """
        Start comprehensive scraping for specified teams.
        
        Args:
            teams: List of team names to scrape (default: all teams)
            mode: Scraping mode ('fast', 'comprehensive', 'social_only')
        
        Returns:
            Job ID for tracking progress
        """
        if teams is None:
            teams = self.nfl_teams
        
        logger.info(f"🚀 Starting {mode} scraping for {len(teams)} teams")
        
        # Start database job tracking
        job_id = self.db.start_scraping_job(
            job_type=mode,
            team=','.join(teams) if len(teams) <= 5 else f"{len(teams)} teams",
            config={
                'mode': mode,
                'teams': teams,
                'max_workers': self.max_workers,
                'requests_per_second': self.requests_per_second
            }
        )
        
        # Generate scraping tasks
        self._generate_scraping_tasks(teams, mode)
        
        # Start scraping
        self.stats['start_time'] = datetime.now()
        self.stats['total_tasks'] = len(self.task_queue)
        
        # Process tasks in parallel
        self._process_tasks_parallel(job_id)
        
        return job_id
    
    def _generate_scraping_tasks(self, teams: List[str], mode: str):
        """Generate scraping tasks based on teams and mode."""
        self.task_queue = []
        
        for team in teams:
            # Always start with roster scraping (highest priority)
            self.task_queue.append(ScrapingTask(
                task_id=f"roster_{team}",
                task_type='roster',
                team=team,
                priority=10
            ))
            
            if mode in ['comprehensive', 'social_only']:
                # Get players that need social media updates
                players_needing_update = self.db.get_players_needing_update(hours_threshold=24)
                team_players = [p for p in players_needing_update if p.get('team_name', '').lower() == team.lower()]
                
                for player in team_players[:20]:  # Limit to 20 players per team for speed
                    if mode == 'comprehensive':
                        # Add detailed player scraping task
                        self.task_queue.append(ScrapingTask(
                            task_id=f"player_{team}_{player['name'].replace(' ', '_')}",
                            task_type='player_detail',
                            team=team,
                            player_name=player['name'],
                            priority=5
                        ))
                    
                    # Add social media scraping task
                    self.task_queue.append(ScrapingTask(
                        task_id=f"social_{team}_{player['name'].replace(' ', '_')}",
                        task_type='social_media',
                        team=team,
                        player_name=player['name'],
                        priority=3
                    ))
        
        # Sort tasks by priority (higher number = higher priority)
        self.task_queue.sort(key=lambda x: x.priority, reverse=True)
        logger.info(f"Generated {len(self.task_queue)} scraping tasks")
    
    def _process_tasks_parallel(self, job_id: int):
        """Process tasks in parallel using thread pool."""
        logger.info(f"Processing {len(self.task_queue)} tasks with {self.max_workers} workers")
        
        # Process roster tasks first (they create the player data)
        roster_tasks = [task for task in self.task_queue if task.task_type == 'roster']
        other_tasks = [task for task in self.task_queue if task.task_type != 'roster']
        
        # Process roster tasks sequentially to avoid conflicts
        self._process_task_batch(roster_tasks, job_id, workers=1)
        
        # Process other tasks in parallel
        self._process_task_batch(other_tasks, job_id, workers=self.max_workers)
        
        # Finalize job
        self._finalize_scraping_job(job_id)
    
    def _process_task_batch(self, tasks: List[ScrapingTask], job_id: int, workers: int):
        """Process a batch of tasks with specified number of workers."""
        if not tasks:
            return
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self._execute_task, task, job_id): task 
                for task in tasks
            }
            
            # Process completed tasks
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    if result:
                        self.completed_tasks.append(task)
                        self.stats['completed_tasks'] += 1
                    else:
                        self.failed_tasks.append(task)
                        self.stats['failed_tasks'] += 1
                        
                    # Update progress every 10 tasks
                    if (self.stats['completed_tasks'] + self.stats['failed_tasks']) % 10 == 0:
                        self._update_job_progress(job_id)
                        
                except Exception as e:
                    logger.error(f"Task {task.task_id} failed with exception: {e}")
                    self.failed_tasks.append(task)
                    self.stats['failed_tasks'] += 1
    
    def _execute_task(self, task: ScrapingTask, job_id: int) -> bool:
        """Execute a single scraping task."""
        try:
            logger.debug(f"Executing task: {task.task_id}")
            
            if task.task_type == 'roster':
                return self._scrape_team_roster(task, job_id)
            elif task.task_type == 'player_detail':
                return self._scrape_player_details(task, job_id)
            elif task.task_type == 'social_media':
                return self._scrape_social_media(task, job_id)
            else:
                logger.warning(f"Unknown task type: {task.task_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing task {task.task_id}: {e}")
            return False
    
    def _scrape_team_roster(self, task: ScrapingTask, job_id: int) -> bool:
        """Scrape team roster and save to database."""
        try:
            # Check cache first
            cache_key = self._get_cache_key('roster', task.team)
            cached_data = self._get_from_cache(cache_key)
            
            if cached_data:
                logger.debug(f"Using cached roster data for {task.team}")
                players_data = cached_data
            else:
                # Apply rate limiting
                self._rate_limit()
                
                # Scrape roster data
                logger.info(f"🏈 Scraping roster for {task.team}")
                players_data = self.nfl_scraper.scrape_team_roster_comprehensive(task.team)
                
                if not players_data:
                    logger.warning(f"No roster data found for {task.team}")
                    return False
                
                # Cache the results
                self._store_in_cache(cache_key, players_data)
            
            # Prepare players for database
            prepared_players = []
            for player in players_data:
                player_data = {
                    'name': player.get('name', ''),
                    'team': task.team,
                    'position': player.get('position', ''),
                    'jersey_number': player.get('jersey', ''),
                    'height': player.get('height', ''),
                    'weight': self._parse_weight(player.get('weight', '')),
                    'age': self._parse_age(player.get('age', '')),
                    'college': player.get('college', ''),
                    'experience': player.get('experience', ''),
                    'status': 'Active',
                    'data_sources': ['nfl.com']
                }
                prepared_players.append(player_data)
            
            # Bulk upsert to database
            stats = self.db.upsert_player_bulk(prepared_players, job_id)
            
            self.stats['players_processed'] += len(prepared_players)
            self.stats['players_updated'] += stats['inserted'] + stats['updated']
            self.stats['players_skipped'] += stats['skipped']
            
            logger.info(f"✅ {task.team}: {len(prepared_players)} players processed")
            return True
            
        except Exception as e:
            logger.error(f"Error scraping roster for {task.team}: {e}")
            return False
    
    def _scrape_player_details(self, task: ScrapingTask, job_id: int) -> bool:
        """Scrape detailed player information."""
        try:
            # Check if player needs updating (not updated in last 24 hours)
            cache_key = self._get_cache_key('player_detail', f"{task.team}_{task.player_name}")
            cached_data = self._get_from_cache(cache_key)
            
            if cached_data:
                logger.debug(f"Using cached player details for {task.player_name}")
                return True
            
            # Apply rate limiting
            self._rate_limit()
            
            logger.debug(f"📊 Scraping details for {task.player_name} ({task.team})")
            
            # Here you would integrate with existing detailed scrapers
            # For now, we'll use a placeholder that gets basic stats
            player_details = self._get_player_stats_placeholder(task.player_name, task.team)
            
            if player_details:
                # Cache the results
                self._store_in_cache(cache_key, player_details)
                
                # Update database with detailed info
                stats = self.db.upsert_player_bulk([player_details], job_id)
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error scraping details for {task.player_name}: {e}")
            return False
    
    def _scrape_social_media(self, task: ScrapingTask, job_id: int) -> bool:
        """Scrape social media data for a player."""
        try:
            # Check cache
            cache_key = self._get_cache_key('social_media', f"{task.team}_{task.player_name}")
            cached_data = self._get_from_cache(cache_key)
            
            if cached_data:
                logger.debug(f"Using cached social media data for {task.player_name}")
                return True
            
            # Apply rate limiting (social media scraping needs more careful rate limiting)
            self._rate_limit()
            time.sleep(random.uniform(0.5, 1.5))  # Additional delay for social media
            
            logger.debug(f"📱 Scraping social media for {task.player_name} ({task.team})")
            
            # Use existing social media agent
            social_profiles = self.social_scraper.search_google_for_social_profiles(
                task.player_name, task.team
            )
            
            if social_profiles:
                # Cache the results
                self._store_in_cache(cache_key, social_profiles)
                
                # Here you would save social media data to the social_media_metrics table
                # For now, we'll just log the success
                logger.debug(f"Found social profiles for {task.player_name}: {list(social_profiles.keys())}")
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error scraping social media for {task.player_name}: {e}")
            return False
    
    def _parse_weight(self, weight_str: str) -> Optional[int]:
        """Parse weight string to integer."""
        if not weight_str:
            return None
        try:
            # Extract numbers from string like "230 lbs" or "230"
            import re
            match = re.search(r'(\d+)', str(weight_str))
            return int(match.group(1)) if match else None
        except:
            return None
    
    def _parse_age(self, age_str: str) -> Optional[int]:
        """Parse age string to integer."""
        if not age_str:
            return None
        try:
            return int(str(age_str).strip())
        except:
            return None
    
    def _get_player_stats_placeholder(self, player_name: str, team: str) -> Dict:
        """Placeholder for detailed player stats (replace with actual scraper)."""
        return {
            'name': player_name,
            'team': team,
            'data_sources': ['detailed_scraper'],
            'games_played': None,  # Would be filled by actual scraper
            'passing_yards': None,
            'rushing_yards': None,
            'receiving_yards': None
        }
    
    def _update_job_progress(self, job_id: int):
        """Update scraping job progress in database."""
        try:
            self.db.update_scraping_job_progress(
                job_id,
                self.stats['completed_tasks'] + self.stats['failed_tasks'],
                self.stats['completed_tasks'],
                self.stats['failed_tasks']
            )
        except Exception as e:
            logger.error(f"Error updating job progress: {e}")
    
    def _finalize_scraping_job(self, job_id: int):
        """Finalize scraping job with results."""
        end_time = datetime.now()
        duration = (end_time - self.stats['start_time']).total_seconds()
        
        results = {
            'total_tasks': self.stats['total_tasks'],
            'completed_tasks': self.stats['completed_tasks'],
            'failed_tasks': self.stats['failed_tasks'],
            'players_processed': self.stats['players_processed'],
            'players_updated': self.stats['players_updated'],
            'players_skipped': self.stats['players_skipped'],
            'duration_seconds': duration,
            'requests_made': self.stats['requests_made'],
            'cache_hits': self.stats['cache_hits'],
            'avg_time_per_task': duration / max(self.stats['total_tasks'], 1)
        }
        
        try:
            self.db.complete_scraping_job(job_id, results)
            logger.info(f"🎉 Scraping job {job_id} completed successfully")
            logger.info(f"📊 Results: {results}")
        except Exception as e:
            logger.error(f"Error finalizing job: {e}")
    
    def get_scraping_status(self, job_id: int = None) -> Dict:
        """Get current scraping status."""
        if job_id:
            return self.db.get_scraping_stats(job_id)
        else:
            return {
                'current_stats': self.stats,
                'task_queue_size': len(self.task_queue),
                'completed_tasks': len(self.completed_tasks),
                'failed_tasks': len(self.failed_tasks),
                'cache_size': len(self.cache)
            }
    
    def scrape_single_team_fast(self, team: str) -> Dict:
        """Quick scrape of a single team (for testing/immediate use)."""
        logger.info(f"🚀 Fast scraping for {team}")
        
        job_id = self.db.start_scraping_job('fast_single', team)
        
        try:
            # Create and execute roster task
            roster_task = ScrapingTask(
                task_id=f"roster_{team}",
                task_type='roster',
                team=team,
                priority=10
            )
            
            success = self._execute_task(roster_task, job_id)
            
            results = {
                'success': success,
                'team': team,
                'players_processed': self.stats.get('players_processed', 0),
                'requests_made': self.stats.get('requests_made', 0)
            }
            
            self.db.complete_scraping_job(job_id, results)
            return results
            
        except Exception as e:
            error_msg = f"Error in fast scrape for {team}: {e}"
            logger.error(error_msg)
            self.db.complete_scraping_job(job_id, error_log=error_msg)
            return {'success': False, 'error': str(e)}
    
    def cleanup_cache(self):
        """Clean up expired cache entries."""
        current_time = datetime.now()
        expired_keys = []
        
        for key, item in self.cache.items():
            if (current_time - item['timestamp']).seconds > self.cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def close(self):
        """Clean up resources."""
        try:
            self.session.close()
            self.db.close()
            logger.info("Fast scraper system closed")
        except Exception as e:
            logger.error(f"Error closing scraper system: {e}")

# Example usage and testing
if __name__ == "__main__":
    # Initialize fast scraper
    scraper = FastScraperSystem(max_workers=8, requests_per_second=3)
    
    # Test single team scraping
    result = scraper.scrape_single_team_fast('chiefs')
    print(f"Single team scrape result: {result}")
    
    # Test comprehensive scraping for a few teams
    job_id = scraper.start_comprehensive_scraping(['chiefs', 'bills'], mode='fast')
    print(f"Started comprehensive scraping job: {job_id}")
    
    # Get status
    status = scraper.get_scraping_status(job_id)
    print(f"Scraping status: {status}")
    
    # Cleanup
    scraper.close()