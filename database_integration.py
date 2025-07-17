#!/usr/bin/env python3
"""
Database integration for NFL Gravity Pipeline
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NFLDatabase:
    """Database manager for NFL Gravity data."""
    
    def __init__(self):
        self.database_url = os.environ.get('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not found")
        
        self.connection = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        """Connect to PostgreSQL database."""
        try:
            self.connection = psycopg2.connect(self.database_url)
            logger.info("Successfully connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise
    
    def create_tables(self):
        """Create necessary tables for NFL data."""
        
        tables = {
            'teams': '''
                CREATE TABLE IF NOT EXISTS teams (
                    id SERIAL PRIMARY KEY,
                    team_full VARCHAR(100) NOT NULL,
                    location VARCHAR(50),
                    nickname VARCHAR(50),
                    slug VARCHAR(50) UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            
            'players': '''
                CREATE TABLE IF NOT EXISTS players (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    jersey_number VARCHAR(10),
                    team_id INTEGER REFERENCES teams(id),
                    
                    -- Wikipedia data
                    age INTEGER,
                    nationality VARCHAR(50),
                    position VARCHAR(20),
                    current_team VARCHAR(100),
                    college VARCHAR(100),
                    draft_year INTEGER,
                    trophies INTEGER,
                    injury_status VARCHAR(100),
                    accomplishments INTEGER,
                    
                    -- Social media URLs
                    instagram_url TEXT,
                    twitter_url TEXT,
                    tiktok_url TEXT,
                    youtube_url TEXT,
                    
                    -- Instagram metrics
                    instagram_followers INTEGER,
                    instagram_likes_avg DECIMAL(10,2),
                    instagram_comments_avg DECIMAL(10,2),
                    instagram_posts_per_week DECIMAL(5,2),
                    
                    -- Twitter metrics
                    twitter_followers INTEGER,
                    twitter_likes_avg DECIMAL(10,2),
                    twitter_retweets_avg DECIMAL(10,2),
                    twitter_replies_avg DECIMAL(10,2),
                    
                    -- TikTok metrics
                    tiktok_followers INTEGER,
                    tiktok_likes_avg DECIMAL(10,2),
                    tiktok_comments_avg DECIMAL(10,2),
                    tiktok_shares_avg DECIMAL(10,2),
                    
                    -- YouTube metrics
                    youtube_subscribers INTEGER,
                    youtube_views_avg DECIMAL(12,2),
                    
                    -- Professional stats
                    pfr_pass_yds INTEGER,
                    pfr_pass_td INTEGER,
                    pfr_rush_rec_yds INTEGER,
                    pfr_tackles INTEGER,
                    pfr_sacks DECIMAL(5,1),
                    pfr_int INTEGER,
                    pfr_fg INTEGER,
                    pfr_punt_yds INTEGER,
                    
                    -- Financial data
                    career_earnings BIGINT,
                    
                    -- News presence
                    news_headlines_count INTEGER,
                    
                    -- Metadata
                    data_source VARCHAR(50),
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(name, team_id)
                )
            ''',
            
            'scraping_runs': '''
                CREATE TABLE IF NOT EXISTS scraping_runs (
                    id SERIAL PRIMARY KEY,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    total_players INTEGER,
                    successful_enrichments INTEGER,
                    failed_enrichments INTEGER,
                    status VARCHAR(20) DEFAULT 'running',
                    notes TEXT
                )
            '''
        }
        
        try:
            with self.connection.cursor() as cursor:
                for table_name, table_sql in tables.items():
                    cursor.execute(table_sql)
                    logger.info(f"Created/verified table: {table_name}")
                
                self.connection.commit()
                logger.info("All database tables created successfully")
                
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            self.connection.rollback()
            raise
    
    def insert_team(self, team_data: Dict[str, Any]) -> int:
        """Insert or update team data and return team ID."""
        
        insert_sql = '''
            INSERT INTO teams (team_full, location, nickname, slug)
            VALUES (%(team_full)s, %(location)s, %(nickname)s, %(slug)s)
            ON CONFLICT (slug) DO UPDATE SET
                team_full = EXCLUDED.team_full,
                location = EXCLUDED.location,
                nickname = EXCLUDED.nickname,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        '''
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(insert_sql, team_data)
                team_id = cursor.fetchone()[0]
                self.connection.commit()
                logger.debug(f"Inserted/updated team: {team_data['team_full']}")
                return team_id
                
        except Exception as e:
            logger.error(f"Error inserting team {team_data}: {e}")
            self.connection.rollback()
            raise
    
    def insert_player(self, player_data: Dict[str, Any]) -> int:
        """Insert or update player data and return player ID."""
        
        # Map DataFrame column names to database column names
        column_mapping = {
            'Player': 'name',
            'Jersey': 'jersey_number',
            'Age': 'age',
            'Nationality': 'nationality',
            'Position': 'position',
            'CurrentTeam': 'current_team',
            'College': 'college',
            'DraftYear': 'draft_year',
            'Trophies': 'trophies',
            'Injury_Status': 'injury_status',
            'Accomplishments': 'accomplishments',
            'IG_URL': 'instagram_url',
            'Twitter_URL': 'twitter_url',
            'TikTok_URL': 'tiktok_url',
            'YouTube_URL': 'youtube_url',
            'Instagram_Followers': 'instagram_followers',
            'Instagram_Likes_Avg': 'instagram_likes_avg',
            'Instagram_Comments_Avg': 'instagram_comments_avg',
            'Instagram_Posts_per_Week': 'instagram_posts_per_week',
            'Twitter_Followers': 'twitter_followers',
            'Twitter_Likes_Avg': 'twitter_likes_avg',
            'Twitter_Retweets_Avg': 'twitter_retweets_avg',
            'Twitter_Replies_Avg': 'twitter_replies_avg',
            'TikTok_Followers': 'tiktok_followers',
            'TikTok_Likes_Avg': 'tiktok_likes_avg',
            'TikTok_Comments_Avg': 'tiktok_comments_avg',
            'TikTok_Shares_Avg': 'tiktok_shares_avg',
            'YouTube_Subscribers': 'youtube_subscribers',
            'YouTube_Views_Avg': 'youtube_views_avg',
            'PFR_PassYds': 'pfr_pass_yds',
            'PFR_PassTD': 'pfr_pass_td',
            'PFR_RushRecYds': 'pfr_rush_rec_yds',
            'PFR_Tackles': 'pfr_tackles',
            'PFR_Sacks': 'pfr_sacks',
            'PFR_Int': 'pfr_int',
            'PFR_FG': 'pfr_fg',
            'PFR_PuntYds': 'pfr_punt_yds',
            'Career_Earnings': 'career_earnings',
            'News_Headlines_Count': 'news_headlines_count'
        }
        
        # Convert data using mapping
        db_data = {}
        for original_key, db_key in column_mapping.items():
            if original_key in player_data:
                value = player_data[original_key]
                # Handle None values and convert to appropriate types
                if value is not None and value != '':
                    if db_key.endswith('_id') or db_key in ['age', 'trophies', 'accomplishments', 'draft_year']:
                        try:
                            db_data[db_key] = int(value)
                        except (ValueError, TypeError):
                            db_data[db_key] = None
                    elif '_avg' in db_key or db_key == 'pfr_sacks':
                        try:
                            db_data[db_key] = float(value)
                        except (ValueError, TypeError):
                            db_data[db_key] = None
                    else:
                        db_data[db_key] = str(value)
                else:
                    db_data[db_key] = None
        
        # Add required fields
        db_data['team_id'] = player_data.get('team_id')
        db_data['scraped_at'] = datetime.now()
        
        # Build dynamic insert SQL
        columns = list(db_data.keys())
        placeholders = [f'%({col})s' for col in columns]
        
        insert_sql = f'''
            INSERT INTO players ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            ON CONFLICT (name, team_id) DO UPDATE SET
                {', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col not in ['name', 'team_id']])},
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        '''
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(insert_sql, db_data)
                player_id = cursor.fetchone()[0]
                self.connection.commit()
                logger.debug(f"Inserted/updated player: {db_data.get('name')}")
                return player_id
                
        except Exception as e:
            logger.error(f"Error inserting player {db_data.get('name')}: {e}")
            self.connection.rollback()
            raise
    
    def start_scraping_run(self) -> int:
        """Start a new scraping run and return run ID."""
        
        insert_sql = '''
            INSERT INTO scraping_runs (start_time, status)
            VALUES (CURRENT_TIMESTAMP, 'running')
            RETURNING id
        '''
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(insert_sql)
                run_id = cursor.fetchone()[0]
                self.connection.commit()
                logger.info(f"Started scraping run with ID: {run_id}")
                return run_id
                
        except Exception as e:
            logger.error(f"Error starting scraping run: {e}")
            self.connection.rollback()
            raise
    
    def end_scraping_run(self, run_id: int, stats: Dict[str, Any]):
        """End a scraping run with statistics."""
        
        update_sql = '''
            UPDATE scraping_runs 
            SET end_time = CURRENT_TIMESTAMP,
                total_players = %(total_players)s,
                successful_enrichments = %(successful_enrichments)s,
                failed_enrichments = %(failed_enrichments)s,
                status = %(status)s,
                notes = %(notes)s
            WHERE id = %(run_id)s
        '''
        
        try:
            with self.connection.cursor() as cursor:
                stats['run_id'] = run_id
                cursor.execute(update_sql, stats)
                self.connection.commit()
                logger.info(f"Ended scraping run {run_id}")
                
        except Exception as e:
            logger.error(f"Error ending scraping run {run_id}: {e}")
            self.connection.rollback()
            raise
    
    def get_player_count(self) -> int:
        """Get total number of players in database."""
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM players")
                count = cursor.fetchone()[0]
                return count
                
        except Exception as e:
            logger.error(f"Error getting player count: {e}")
            return 0
    
    def get_team_stats(self) -> List[Dict]:
        """Get statistics by team."""
        
        query = '''
            SELECT 
                t.team_full,
                t.location,
                t.nickname,
                COUNT(p.id) as player_count,
                AVG(p.instagram_followers) as avg_instagram_followers,
                AVG(p.twitter_followers) as avg_twitter_followers,
                AVG(p.news_headlines_count) as avg_news_mentions
            FROM teams t
            LEFT JOIN players p ON t.id = p.team_id
            GROUP BY t.id, t.team_full, t.location, t.nickname
            ORDER BY player_count DESC
        '''
        
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
                return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"Error getting team stats: {e}")
            return []
    
    def export_to_csv(self, filename: str = "nfl_gravity_export.csv"):
        """Export all player data to CSV."""
        
        query = '''
            SELECT 
                t.team_full,
                t.location,
                t.nickname,
                p.*
            FROM players p
            JOIN teams t ON p.team_id = t.id
            ORDER BY t.team_full, p.name
        '''
        
        try:
            df = pd.read_sql_query(query, self.connection)
            df.to_csv(filename, index=False)
            logger.info(f"Exported {len(df)} players to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            raise
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

def test_database_connection():
    """Test database connection and basic operations."""
    print("Testing NFL Database Connection...")
    
    try:
        db = NFLDatabase()
        
        # Test basic connection
        print(f"✅ Connected to database successfully")
        
        # Test team insertion
        test_team = {
            'team_full': 'Test Team',
            'location': 'Test City',
            'nickname': 'Testers',
            'slug': 'test-team'
        }
        
        team_id = db.insert_team(test_team)
        print(f"✅ Inserted test team with ID: {team_id}")
        
        # Test player insertion
        test_player = {
            'Player': 'Test Player',
            'Jersey': '99',
            'team_id': team_id,
            'Age': 25,
            'Position': 'QB',
            'College': 'Test University',
            'Instagram_Followers': 1000,
            'News_Headlines_Count': 5
        }
        
        player_id = db.insert_player(test_player)
        print(f"✅ Inserted test player with ID: {player_id}")
        
        # Test statistics
        player_count = db.get_player_count()
        print(f"✅ Total players in database: {player_count}")
        
        # Test team stats
        team_stats = db.get_team_stats()
        print(f"✅ Found {len(team_stats)} teams in database")
        
        db.close()
        print("✅ Database test completed successfully!")
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")


# Helper functions for the web application
def get_db_connection():
    """Get a database connection."""
    return psycopg2.connect(
        host=os.getenv('PGHOST', 'localhost'),
        database=os.getenv('PGDATABASE', 'nfl_gravity'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', 'password'),
        port=os.getenv('PGPORT', '5432')
    )

def save_players_to_db(players_data):
    """Save players data to PostgreSQL database."""
    try:
        db = NFLDatabase()
        
        for player in players_data:
            # First, ensure team exists
            team_data = {
                'team_full': player.get('team', 'Unknown'),
                'location': player.get('team', 'Unknown'),
                'nickname': player.get('team', 'Unknown'),
                'slug': player.get('team', 'unknown').lower()
            }
            
            team_id = db.insert_team(team_data)
            
            # Prepare player data
            player_data = {
                'Player': player.get('name'),
                'Jersey': player.get('jersey_number'),
                'team_id': team_id,
                'Age': player.get('age'),
                'Position': player.get('position'),
                'CurrentTeam': player.get('team'),
                'College': player.get('college'),
                'Instagram_Followers': player.get('instagram_followers'),
                'Twitter_Followers': player.get('twitter_followers'),
                'News_Headlines_Count': player.get('news_headlines_count', 0)
            }
            
            db.insert_player(player_data)
        
        db.close()
        logger.info(f"Successfully saved {len(players_data)} players to database")
        
    except Exception as e:
        logger.error(f"Error saving players to database: {e}")
        raise

def get_all_players_from_db():
    """Get all players from the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT 
                p.name, p.position, p.jersey_number, p.age, p.current_team as team,
                p.college, p.data_source, p.scraped_at, p.updated_at,
                p.instagram_followers, p.twitter_followers, p.news_headlines_count
            FROM players p
            ORDER BY p.current_team, p.position, p.name
        """)
        
        players = cursor.fetchall()
        
        # Convert to list of dictionaries for JSON serialization
        result = []
        for player in players:
            player_dict = dict(player)
            # Convert datetime objects to ISO format
            if player_dict.get('scraped_at'):
                player_dict['scraped_at'] = player_dict['scraped_at'].isoformat()
            if player_dict.get('updated_at'):
                player_dict['updated_at'] = player_dict['updated_at'].isoformat()
            result.append(player_dict)
        
        logger.info(f"Retrieved {len(result)} players from database")
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving players from database: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_players_by_team(team_name):
    """Get players for a specific team."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT * FROM players 
            WHERE current_team = %s
            ORDER BY position, jersey_number
        """, (team_name,))
        
        players = cursor.fetchall()
        
        # Convert to list of dictionaries
        result = []
        for player in players:
            player_dict = dict(player)
            if player_dict.get('scraped_at'):
                player_dict['scraped_at'] = player_dict['scraped_at'].isoformat()
            if player_dict.get('updated_at'):
                player_dict['updated_at'] = player_dict['updated_at'].isoformat()
            result.append(player_dict)
        
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving players for team {team_name}: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_database_stats():
    """Get statistics about the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get total players
        cursor.execute("SELECT COUNT(*) FROM players")
        total_players = cursor.fetchone()[0]
        
        # Get players by team
        cursor.execute("""
            SELECT current_team, COUNT(*) as player_count 
            FROM players 
            GROUP BY current_team 
            ORDER BY player_count DESC
        """)
        team_stats = cursor.fetchall()
        
        # Get players by position
        cursor.execute("""
            SELECT position, COUNT(*) as player_count 
            FROM players 
            GROUP BY position 
            ORDER BY player_count DESC
        """)
        position_stats = cursor.fetchall()
        
        # Get latest update time
        cursor.execute("SELECT MAX(updated_at) FROM players")
        last_updated = cursor.fetchone()[0]
        
        return {
            "total_players": total_players,
            "teams": len(team_stats),
            "positions": len(position_stats),
            "team_stats": team_stats,
            "position_stats": position_stats,
            "last_updated": last_updated.isoformat() if last_updated else None
        }
        
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    test_database_connection()