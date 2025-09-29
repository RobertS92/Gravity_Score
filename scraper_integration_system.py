#!/usr/bin/env python3
"""
Scraper Integration System
Connects fast scrapers with database and dashboard, provides API endpoints
"""

import os
import threading
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from flask import Blueprint, request, jsonify
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Import our systems
from fast_scraper_system import FastScraperSystem
from enhanced_db_schema import EnhancedNFLDatabase
from enhanced_nfl_scraper import EnhancedNFLScraper

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ScraperIntegrationSystem:
    """
    Integration system that connects all scraping components:
    - Fast scraper system
    - Database with incremental updates
    - Dashboard integration
    - API endpoints for control
    - Real-time progress tracking
    """
    
    def __init__(self):
        # Initialize core systems
        self.db = EnhancedNFLDatabase()
        self.fast_scraper = FastScraperSystem(max_workers=6, requests_per_second=4)
        self.nfl_scraper = EnhancedNFLScraper()
        
        # Job management
        self.active_jobs = {}
        self.job_lock = threading.Lock()
        
        # Background job executor
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Statistics
        self.system_stats = {
            'total_jobs_run': 0,
            'total_players_processed': 0,
            'total_data_points_collected': 0,
            'last_full_scrape': None,
            'system_start_time': datetime.now()
        }
        
        logger.info("🚀 Scraper Integration System initialized")
    
    def start_incremental_scrape(self, teams: List[str] = None, mode: str = 'incremental') -> Dict:
        """
        Start incremental scraping that only updates new/changed data.
        
        Args:
            teams: List of teams to scrape (default: all teams)
            mode: 'incremental', 'full', 'social_only', 'stats_only'
        
        Returns:
            Job information with tracking ID
        """
        if teams is None:
            teams = self.fast_scraper.nfl_teams
        
        with self.job_lock:
            job_id = f"job_{int(time.time())}"
            
            # Get players that need updating based on incremental logic
            players_needing_update = self._get_players_for_incremental_update(teams, mode)
            
            job_info = {
                'job_id': job_id,
                'job_type': mode,
                'teams': teams,
                'status': 'starting',
                'start_time': datetime.now(),
                'total_players_to_process': len(players_needing_update),
                'progress': {
                    'teams_completed': 0,
                    'players_processed': 0,
                    'players_updated': 0,
                    'players_skipped': 0,
                    'current_team': None,
                    'completion_percentage': 0
                },
                'database_job_id': None
            }
            
            self.active_jobs[job_id] = job_info
            
            # Start background scraping
            future = self.executor.submit(self._run_incremental_scrape, job_id, teams, mode)
            job_info['future'] = future
            
            logger.info(f"Started incremental scrape job {job_id} for {len(teams)} teams")
            return {
                'job_id': job_id,
                'status': 'started',
                'teams': teams,
                'mode': mode,
                'estimated_players': len(players_needing_update)
            }
    
    def _get_players_for_incremental_update(self, teams: List[str], mode: str) -> List[Dict]:
        """
        Intelligent selection of players that need updating based on:
        - Last scrape time
        - Data completeness
        - Player activity/importance
        - Mode requirements
        """
        logger.info(f"🔍 Analyzing players needing {mode} updates for {len(teams)} teams")
        
        # Get players needing updates based on mode
        if mode == 'incremental':
            # Players not updated in last 24 hours or with low data completeness
            threshold_hours = 24
        elif mode == 'social_only':
            # Social media data older than 12 hours
            threshold_hours = 12
        elif mode == 'stats_only':
            # Stats data older than 48 hours (less frequent updates needed)
            threshold_hours = 48
        else:  # full mode
            threshold_hours = 0  # All players
        
        players_needing_update = self.db.get_players_needing_update(threshold_hours)
        
        # Filter by teams
        if teams:
            team_names_lower = [team.lower() for team in teams]
            players_needing_update = [
                player for player in players_needing_update 
                if player.get('team_name', '').lower() in team_names_lower
            ]
        
        # Prioritize players based on importance factors
        prioritized_players = self._prioritize_players_for_update(players_needing_update, mode)
        
        logger.info(f"Selected {len(prioritized_players)} players for {mode} updates")
        return prioritized_players
    
    def _prioritize_players_for_update(self, players: List[Dict], mode: str) -> List[Dict]:
        """
        Prioritize players for updating based on various factors:
        - Star players (QB, skill positions)
        - Players with incomplete data
        - Players with recent activity
        - Team importance
        """
        def calculate_priority_score(player: Dict) -> float:
            score = 0.0
            
            # Position priority (QBs and skill positions are more important)
            position = player.get('position', '').upper()
            position_weights = {
                'QB': 10.0, 'RB': 8.0, 'WR': 8.0, 'TE': 7.0,
                'LB': 6.0, 'CB': 6.0, 'S': 6.0, 'DE': 5.0,
                'DT': 4.0, 'OL': 3.0, 'K': 2.0, 'P': 1.0
            }
            score += position_weights.get(position, 3.0)
            
            # Data completeness (lower completeness = higher priority)
            completeness = player.get('data_completeness_score', 50.0)
            score += (100 - completeness) / 10
            
            # Age factor (younger players change more frequently)
            age = player.get('age', 30)
            if age < 25:
                score += 3.0
            elif age < 30:
                score += 1.0
            
            # Last scraped time (older = higher priority)
            last_scraped = player.get('last_scraped')
            if last_scraped is None:
                score += 20.0  # Never scraped = highest priority
            else:
                hours_since_scraped = (datetime.now() - last_scraped).total_seconds() / 3600
                score += min(hours_since_scraped / 24, 10.0)  # Cap at 10 points
            
            return score
        
        # Calculate priorities and sort
        for player in players:
            player['priority_score'] = calculate_priority_score(player)
        
        # Sort by priority (highest first) and limit for performance
        prioritized = sorted(players, key=lambda x: x['priority_score'], reverse=True)
        
        # Limit based on mode
        if mode == 'incremental':
            return prioritized[:500]  # Limit to top 500 for incremental
        elif mode == 'social_only':
            return prioritized[:200]  # Social media updates for top 200
        else:
            return prioritized  # Full mode processes all
    
    def _run_incremental_scrape(self, job_id: str, teams: List[str], mode: str):
        """Run the incremental scraping job in background."""
        try:
            with self.job_lock:
                job_info = self.active_jobs[job_id]
                job_info['status'] = 'running'
            
            # Start database job
            db_job_id = self.fast_scraper.start_comprehensive_scraping(teams, mode)
            job_info['database_job_id'] = db_job_id
            
            # Track progress
            total_teams = len(teams)
            for i, team in enumerate(teams):
                with self.job_lock:
                    job_info['progress']['current_team'] = team
                    job_info['progress']['teams_completed'] = i
                    job_info['progress']['completion_percentage'] = int((i / total_teams) * 100)
                
                logger.info(f"Processing team {i+1}/{total_teams}: {team}")
                
                # Process team based on mode
                if mode == 'incremental':
                    self._process_team_incremental(team, job_info)
                elif mode == 'social_only':
                    self._process_team_social_only(team, job_info)
                elif mode == 'stats_only':
                    self._process_team_stats_only(team, job_info)
                else:  # full
                    self._process_team_full(team, job_info)
                
                # Small delay between teams to be respectful
                time.sleep(1)
            
            # Finalize job
            with self.job_lock:
                job_info['status'] = 'completed'
                job_info['end_time'] = datetime.now()
                job_info['progress']['completion_percentage'] = 100
                
                # Update system stats
                self.system_stats['total_jobs_run'] += 1
                self.system_stats['total_players_processed'] += job_info['progress']['players_processed']
                if mode == 'full':
                    self.system_stats['last_full_scrape'] = datetime.now()
            
            logger.info(f"✅ Incremental scrape job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error in incremental scrape job {job_id}: {e}")
            with self.job_lock:
                job_info['status'] = 'failed'
                job_info['error'] = str(e)
                job_info['end_time'] = datetime.now()
    
    def _process_team_incremental(self, team: str, job_info: Dict):
        """Process team with incremental logic - only update what's changed."""
        try:
            # Get current roster from NFL.com
            current_roster = self.nfl_scraper.scrape_team_roster_comprehensive(team)
            if not current_roster:
                logger.warning(f"No roster data found for {team}")
                return
            
            # Get existing players from database
            existing_players = self._get_existing_team_players(team)
            existing_names = {player['name'] for player in existing_players}
            
            # Identify new players (not in database)
            new_players = [p for p in current_roster if p.get('name') not in existing_names]
            
            # Identify players needing updates (data changes)
            players_to_update = []
            for roster_player in current_roster:
                name = roster_player.get('name')
                if name in existing_names:
                    existing_player = next(p for p in existing_players if p['name'] == name)
                    if self._player_needs_update(existing_player, roster_player):
                        players_to_update.append(roster_player)
            
            # Process new and updated players only
            all_changes = new_players + players_to_update
            
            if all_changes:
                # Use fast scraper for bulk processing
                result = self.fast_scraper.scrape_single_team_fast(team)
                
                with self.job_lock:
                    job_info['progress']['players_processed'] += len(all_changes)
                    job_info['progress']['players_updated'] += len(new_players)
                    job_info['progress']['players_skipped'] += len(current_roster) - len(all_changes)
                
                logger.info(f"🔄 {team}: {len(new_players)} new, {len(players_to_update)} updated, {len(current_roster) - len(all_changes)} skipped")
            else:
                logger.info(f"⏭️ {team}: No changes detected, skipping")
                
        except Exception as e:
            logger.error(f"Error processing team {team} incrementally: {e}")
    
    def _process_team_social_only(self, team: str, job_info: Dict):
        """Process team for social media updates only."""
        try:
            # Get players needing social media updates
            players = self.db.get_players_needing_update(hours_threshold=12)
            team_players = [p for p in players if p.get('team_name', '').lower() == team.lower()]
            
            # Limit to top 10 players per team for social media
            priority_players = sorted(team_players, key=lambda x: x.get('priority_score', 0), reverse=True)[:10]
            
            for player in priority_players:
                # Use social media scraper
                profiles = self.fast_scraper.social_scraper.search_google_for_social_profiles(
                    player['name'], team
                )
                
                if profiles:
                    # Update social media data in database
                    self._update_player_social_media(player['id'], profiles)
                    
                with self.job_lock:
                    job_info['progress']['players_processed'] += 1
                    if profiles:
                        job_info['progress']['players_updated'] += 1
                    else:
                        job_info['progress']['players_skipped'] += 1
                
                # Rate limiting for social media
                time.sleep(2)
            
            logger.info(f"📱 {team}: Processed social media for {len(priority_players)} players")
            
        except Exception as e:
            logger.error(f"Error processing social media for {team}: {e}")
    
    def _process_team_stats_only(self, team: str, job_info: Dict):
        """Process team for statistics updates only."""
        try:
            # Get current season stats (placeholder - integrate with actual stats scraper)
            stats_updated = self._update_team_stats_placeholder(team)
            
            with self.job_lock:
                job_info['progress']['players_processed'] += stats_updated
                job_info['progress']['players_updated'] += stats_updated
            
            logger.info(f"📊 {team}: Updated stats for {stats_updated} players")
            
        except Exception as e:
            logger.error(f"Error processing stats for {team}: {e}")
    
    def _process_team_full(self, team: str, job_info: Dict):
        """Process team with full comprehensive scraping."""
        try:
            result = self.fast_scraper.scrape_single_team_fast(team)
            
            with self.job_lock:
                if result.get('success'):
                    job_info['progress']['players_processed'] += result.get('players_processed', 0)
                    job_info['progress']['players_updated'] += result.get('players_processed', 0)
                
            logger.info(f"🏈 {team}: Full scrape completed")
            
        except Exception as e:
            logger.error(f"Error in full processing for {team}: {e}")
    
    def _get_existing_team_players(self, team: str) -> List[Dict]:
        """Get existing players for a team from database."""
        try:
            query = '''
                SELECT p.*, t.name as team_name
                FROM players p
                JOIN teams t ON p.team_id = t.id
                WHERE LOWER(t.name) = LOWER(%s)
            '''
            
            with self.db.connection.cursor() as cursor:
                cursor.execute(query, (team,))
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting existing players for {team}: {e}")
            return []
    
    def _player_needs_update(self, existing: Dict, current: Dict) -> bool:
        """Check if a player's data has changed and needs updating."""
        # Check key fields for changes
        check_fields = ['position', 'jersey', 'height', 'weight', 'status']
        
        for field in check_fields:
            existing_value = existing.get(field, '')
            current_value = current.get(field, '')
            
            if str(existing_value).strip() != str(current_value).strip():
                return True
        
        # Check if last scraped was more than 24 hours ago
        last_scraped = existing.get('last_scraped')
        if last_scraped is None:
            return True
        
        hours_since = (datetime.now() - last_scraped).total_seconds() / 3600
        return hours_since > 24
    
    def _update_player_social_media(self, player_id: int, profiles: Dict):
        """Update player's social media data in database."""
        try:
            # Insert into social_media_metrics table
            insert_sql = '''
                INSERT INTO social_media_metrics 
                (player_id, twitter_url, instagram_url, tiktok_url, youtube_url,
                 twitter_handle, instagram_handle, tiktok_handle, youtube_handle)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            '''
            
            with self.db.connection.cursor() as cursor:
                cursor.execute(insert_sql, (
                    player_id,
                    profiles.get('twitter'),
                    profiles.get('instagram'),
                    profiles.get('tiktok'),
                    profiles.get('youtube'),
                    self._extract_handle(profiles.get('twitter', '')),
                    self._extract_handle(profiles.get('instagram', '')),
                    self._extract_handle(profiles.get('tiktok', '')),
                    self._extract_handle(profiles.get('youtube', ''))
                ))
                self.db.connection.commit()
                
        except Exception as e:
            logger.error(f"Error updating social media for player {player_id}: {e}")
            self.db.connection.rollback()
    
    def _extract_handle(self, url: str) -> str:
        """Extract social media handle from URL."""
        if not url:
            return ''
        
        try:
            # Extract handle from URL (basic implementation)
            parts = url.rstrip('/').split('/')
            return parts[-1] if parts else ''
        except:
            return ''
    
    def _update_team_stats_placeholder(self, team: str) -> int:
        """Placeholder for stats updates (integrate with actual stats scraper)."""
        # This would integrate with Pro Football Reference or ESPN stats scraper
        # For now, return a placeholder count
        return 5
    
    def get_job_status(self, job_id: str) -> Dict:
        """Get status of a specific scraping job."""
        with self.job_lock:
            job_info = self.active_jobs.get(job_id, {})
            
            if not job_info:
                return {'error': 'Job not found'}
            
            # Calculate additional metrics
            if job_info.get('start_time'):
                elapsed = (datetime.now() - job_info['start_time']).total_seconds()
                job_info['elapsed_seconds'] = elapsed
                
                # Estimate completion time
                progress = job_info['progress']['completion_percentage']
                if progress > 5:  # Avoid division by zero
                    estimated_total = elapsed * (100 / progress)
                    job_info['estimated_total_seconds'] = estimated_total
                    job_info['estimated_remaining_seconds'] = estimated_total - elapsed
            
            return job_info
    
    def get_all_active_jobs(self) -> Dict:
        """Get status of all active jobs."""
        with self.job_lock:
            return {
                'active_jobs': {job_id: self.get_job_status(job_id) for job_id in self.active_jobs},
                'system_stats': self.system_stats
            }
    
    def stop_job(self, job_id: str) -> Dict:
        """Stop a running scraping job."""
        with self.job_lock:
            job_info = self.active_jobs.get(job_id)
            
            if not job_info:
                return {'error': 'Job not found'}
            
            if job_info['status'] in ['completed', 'failed']:
                return {'error': 'Job already finished'}
            
            # Try to cancel the future
            future = job_info.get('future')
            if future:
                future.cancel()
            
            job_info['status'] = 'cancelled'
            job_info['end_time'] = datetime.now()
            
            return {'success': True, 'message': f'Job {job_id} cancelled'}
    
    def cleanup_old_jobs(self, hours_old: int = 24):
        """Clean up completed jobs older than specified hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours_old)
        
        with self.job_lock:
            jobs_to_remove = []
            
            for job_id, job_info in self.active_jobs.items():
                end_time = job_info.get('end_time')
                if end_time and end_time < cutoff_time:
                    jobs_to_remove.append(job_id)
            
            for job_id in jobs_to_remove:
                del self.active_jobs[job_id]
            
            logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")
    
    def get_system_status(self) -> Dict:
        """Get overall system status and health."""
        try:
            # Database health check
            with self.db.connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM players")
                total_players = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM teams")
                total_teams = cursor.fetchone()[0]
                
                cursor.execute('''
                    SELECT COUNT(*) FROM players 
                    WHERE last_scraped > NOW() - INTERVAL '24 hours'
                ''')
                recently_updated = cursor.fetchone()[0]
            
            return {
                'system_health': 'healthy',
                'database': {
                    'total_players': total_players,
                    'total_teams': total_teams,
                    'recently_updated_players': recently_updated,
                    'update_percentage': round((recently_updated / max(total_players, 1)) * 100, 1)
                },
                'scraper': {
                    'cache_size': len(self.fast_scraper.cache),
                    'active_jobs': len(self.active_jobs),
                    'total_requests_made': self.fast_scraper.stats.get('requests_made', 0)
                },
                'system_stats': self.system_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                'system_health': 'error',
                'error': str(e)
            }
    
    def close(self):
        """Clean up all resources."""
        try:
            # Cancel all active jobs
            with self.job_lock:
                for job_id in list(self.active_jobs.keys()):
                    self.stop_job(job_id)
            
            # Shutdown executor
            self.executor.shutdown(wait=True)
            
            # Close scraper systems
            self.fast_scraper.close()
            self.db.close()
            
            logger.info("Scraper integration system closed")
            
        except Exception as e:
            logger.error(f"Error closing integration system: {e}")

# Flask Blueprint for API endpoints
scraper_api = Blueprint('scraper_api', __name__)

# Global integration system instance
integration_system = None

def get_integration_system():
    """Get or create integration system instance."""
    global integration_system
    if integration_system is None:
        integration_system = ScraperIntegrationSystem()
    return integration_system

@scraper_api.route('/api/scraping/start', methods=['POST'])
def start_scraping():
    """Start a scraping job."""
    try:
        data = request.get_json() or {}
        teams = data.get('teams', [])
        mode = data.get('mode', 'incremental')
        
        system = get_integration_system()
        result = system.start_incremental_scrape(teams, mode)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@scraper_api.route('/api/scraping/status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get status of a specific job."""
    try:
        system = get_integration_system()
        status = system.get_job_status(job_id)
        return jsonify(status)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@scraper_api.route('/api/scraping/jobs', methods=['GET'])
def get_all_jobs():
    """Get all active jobs."""
    try:
        system = get_integration_system()
        jobs = system.get_all_active_jobs()
        return jsonify(jobs)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@scraper_api.route('/api/scraping/stop/<job_id>', methods=['POST'])
def stop_job(job_id):
    """Stop a running job."""
    try:
        system = get_integration_system()
        result = system.stop_job(job_id)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@scraper_api.route('/api/system/status', methods=['GET'])
def get_system_status():
    """Get overall system status."""
    try:
        system = get_integration_system()
        status = system.get_system_status()
        return jsonify(status)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@scraper_api.route('/api/scraping/quick/<team>', methods=['POST'])
def quick_scrape_team(team):
    """Quick scrape of a single team."""
    try:
        system = get_integration_system()
        result = system.fast_scraper.scrape_single_team_fast(team)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Example usage
if __name__ == "__main__":
    # Initialize system
    system = ScraperIntegrationSystem()
    
    # Start incremental scrape for a few teams
    result = system.start_incremental_scrape(['chiefs', 'bills'], 'incremental')
    print(f"Started job: {result}")
    
    # Monitor progress
    job_id = result['job_id']
    time.sleep(5)
    
    status = system.get_job_status(job_id)
    print(f"Job status: {status}")
    
    # Get system status
    sys_status = system.get_system_status()
    print(f"System status: {sys_status}")
    
    # Cleanup
    system.close()