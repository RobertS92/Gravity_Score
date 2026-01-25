"""
Social Media Growth Tracker - Track follower growth over time using SQLite
"""

import sqlite3
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class SocialGrowthTracker:
    """
    Track social media follower counts over time to calculate growth rates.
    Uses SQLite database for persistent storage.
    """
    
    def __init__(self, db_path: str = 'data/social_history.db'):
        """
        Initialize the social growth tracker.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Create database tables if they don't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create social_stats table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS social_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    followers INTEGER NOT NULL,
                    posts INTEGER,
                    engagement_rate REAL,
                    timestamp DATETIME NOT NULL,
                    UNIQUE(player_name, platform, timestamp)
                )
            ''')
            
            # Create index for faster queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_player_platform 
                ON social_stats(player_name, platform, timestamp DESC)
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Social growth tracker database initialized at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def record_current_stats(self, 
                            player_name: str, 
                            platform: str, 
                            followers: int, 
                            posts: Optional[int] = None,
                            engagement_rate: Optional[float] = None) -> bool:
        """
        Store current social media stats with timestamp.
        
        Args:
            player_name: Player's full name
            platform: Social media platform ('instagram', 'twitter', 'tiktok', etc.)
            followers: Current follower count
            posts: Number of posts (optional)
            engagement_rate: Engagement rate percentage (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            timestamp = datetime.now()
            
            cursor.execute('''
                INSERT OR REPLACE INTO social_stats 
                (player_name, platform, followers, posts, engagement_rate, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (player_name, platform, followers, posts, engagement_rate, timestamp))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Recorded {platform} stats for {player_name}: {followers:,} followers")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record stats: {e}")
            return False
    
    def get_latest_stats(self, player_name: str, platform: str) -> Optional[Dict]:
        """
        Get the most recent stats for a player on a platform.
        
        Args:
            player_name: Player's full name
            platform: Social media platform
            
        Returns:
            Dictionary with stats or None if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT followers, posts, engagement_rate, timestamp
                FROM social_stats
                WHERE player_name = ? AND platform = ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (player_name, platform))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'followers': row[0],
                    'posts': row[1],
                    'engagement_rate': row[2],
                    'timestamp': datetime.fromisoformat(row[3])
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get latest stats: {e}")
            return None
    
    def get_historical_stats(self, 
                            player_name: str, 
                            platform: str, 
                            days_ago: int) -> Optional[Dict]:
        """
        Get stats from N days ago.
        
        Args:
            player_name: Player's full name
            platform: Social media platform
            days_ago: Number of days in the past to retrieve
            
        Returns:
            Dictionary with stats or None if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            target_date = datetime.now() - timedelta(days=days_ago)
            
            # Find the closest record to the target date
            cursor.execute('''
                SELECT followers, posts, engagement_rate, timestamp
                FROM social_stats
                WHERE player_name = ? AND platform = ?
                AND timestamp <= ?
                ORDER BY ABS(JULIANDAY(timestamp) - JULIANDAY(?)) ASC
                LIMIT 1
            ''', (player_name, platform, target_date, target_date))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'followers': row[0],
                    'posts': row[1],
                    'engagement_rate': row[2],
                    'timestamp': datetime.fromisoformat(row[3])
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get historical stats: {e}")
            return None
    
    def calculate_growth(self, 
                        player_name: str, 
                        platform: str, 
                        days: int = 30) -> Optional[Dict]:
        """
        Calculate follower growth over a time period.
        
        Args:
            player_name: Player's full name
            platform: Social media platform
            days: Time period in days (default: 30)
            
        Returns:
            Dictionary with growth metrics:
            {
                'absolute_growth': int,  # Raw follower increase
                'percent_growth': float,  # Percentage growth
                'daily_avg_growth': float,  # Average daily growth
                'current_followers': int,
                'past_followers': int,
                'days_measured': int
            }
        """
        try:
            # Get current stats
            current = self.get_latest_stats(player_name, platform)
            if not current:
                logger.debug(f"No current stats for {player_name} on {platform}")
                return None
            
            # Get historical stats
            past = self.get_historical_stats(player_name, platform, days_ago=days)
            if not past:
                logger.debug(f"No historical stats for {player_name} on {platform} from {days} days ago")
                return None
            
            # Calculate growth metrics
            current_followers = current['followers']
            past_followers = past['followers']
            
            absolute_growth = current_followers - past_followers
            percent_growth = ((current_followers - past_followers) / past_followers * 100) if past_followers > 0 else 0
            
            # Calculate actual days between measurements
            days_measured = (current['timestamp'] - past['timestamp']).days
            if days_measured == 0:
                days_measured = 1
            
            daily_avg_growth = absolute_growth / days_measured
            
            return {
                'absolute_growth': absolute_growth,
                'percent_growth': round(percent_growth, 2),
                'daily_avg_growth': round(daily_avg_growth, 1),
                'current_followers': current_followers,
                'past_followers': past_followers,
                'days_measured': days_measured
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate growth: {e}")
            return None
    
    def get_growth_trend(self, 
                        player_name: str, 
                        platform: str, 
                        intervals: List[int] = [7, 30, 90]) -> Dict:
        """
        Get growth trends over multiple time intervals.
        
        Args:
            player_name: Player's full name
            platform: Social media platform
            intervals: List of day intervals to check (default: [7, 30, 90])
            
        Returns:
            Dictionary with growth data for each interval
        """
        trends = {}
        
        for days in intervals:
            growth = self.calculate_growth(player_name, platform, days)
            trends[f'{days}d'] = growth
        
        return trends
    
    def get_all_player_stats(self, player_name: str) -> Dict[str, Dict]:
        """
        Get current stats for a player across all platforms.
        
        Args:
            player_name: Player's full name
            
        Returns:
            Dictionary with stats by platform
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT DISTINCT platform FROM social_stats
                WHERE player_name = ?
            ''', (player_name,))
            
            platforms = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            stats = {}
            for platform in platforms:
                latest = self.get_latest_stats(player_name, platform)
                if latest:
                    stats[platform] = latest
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get all player stats: {e}")
            return {}
    
    def cleanup_old_records(self, days_to_keep: int = 365):
        """
        Remove records older than specified days to save space.
        
        Args:
            days_to_keep: Number of days of history to retain
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            cursor.execute('''
                DELETE FROM social_stats
                WHERE timestamp < ?
            ''', (cutoff_date,))
            
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted > 0:
                logger.info(f"🗑️  Cleaned up {deleted} old records (older than {days_to_keep} days)")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old records: {e}")

