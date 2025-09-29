#!/usr/bin/env python3
"""
Enhanced Database Schema for NFL Gravity Pipeline
Supports incremental updates, historical data preservation, and fast scraping
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
import pandas as pd
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedNFLDatabase:
    """
    Enhanced database manager with incremental updates and historical preservation.
    
    Key Features:
    - Incremental data updates (only new/changed data)
    - Historical data preservation with versioning
    - Fast bulk operations
    - Data integrity validation
    - Conflict resolution for duplicate data
    """
    
    def __init__(self):
        self.database_url = os.environ.get('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not found")
        
        self.connection = None
        self.connect()
        self.create_enhanced_schema()
    
    def connect(self):
        """Connect to PostgreSQL database with optimized settings."""
        try:
            self.connection = psycopg2.connect(
                self.database_url,
                cursor_factory=RealDictCursor
            )
            # Optimize connection for bulk operations
            self.connection.autocommit = False
            with self.connection.cursor() as cursor:
                cursor.execute("SET synchronous_commit = off")
                cursor.execute("SET work_mem = '256MB'")
            self.connection.commit()
            logger.info("Successfully connected to PostgreSQL database with optimized settings")
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise
    
    def create_enhanced_schema(self):
        """Create enhanced database schema with incremental update support."""
        
        schema_sql = {
            # Core teams table
            'teams': '''
                CREATE TABLE IF NOT EXISTS teams (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    full_name VARCHAR(150),
                    city VARCHAR(100),
                    abbreviation VARCHAR(10),
                    conference VARCHAR(10),
                    division VARCHAR(20),
                    slug VARCHAR(50) UNIQUE,
                    logo_url TEXT,
                    primary_color VARCHAR(7),
                    secondary_color VARCHAR(7),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            
            # Enhanced players table with comprehensive data
            'players': '''
                CREATE TABLE IF NOT EXISTS players (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    team_id INTEGER REFERENCES teams(id),
                    
                    -- Basic Information
                    jersey_number VARCHAR(10),
                    position VARCHAR(20),
                    height VARCHAR(20),
                    weight INTEGER,
                    age INTEGER,
                    birth_date DATE,
                    birth_place VARCHAR(200),
                    
                    -- Career Information
                    college VARCHAR(200),
                    draft_year INTEGER,
                    draft_round INTEGER,
                    draft_pick INTEGER,
                    experience VARCHAR(50),
                    years_pro INTEGER,
                    
                    -- Status
                    status VARCHAR(50) DEFAULT 'Active',
                    injury_status VARCHAR(200),
                    contract_status VARCHAR(100),
                    
                    -- Professional Stats (Latest Season)
                    games_played INTEGER,
                    games_started INTEGER,
                    passing_yards INTEGER,
                    passing_tds INTEGER,
                    rushing_yards INTEGER,
                    rushing_tds INTEGER,
                    receiving_yards INTEGER,
                    receiving_tds INTEGER,
                    tackles INTEGER,
                    sacks DECIMAL(5,1),
                    interceptions INTEGER,
                    fumbles INTEGER,
                    
                    -- Awards and Recognition
                    pro_bowls INTEGER DEFAULT 0,
                    all_pro_selections INTEGER DEFAULT 0,
                    rookie_of_year BOOLEAN DEFAULT FALSE,
                    mvp_awards INTEGER DEFAULT 0,
                    hall_of_fame BOOLEAN DEFAULT FALSE,
                    
                    -- Financial Data
                    current_salary BIGINT,
                    contract_value BIGINT,
                    contract_years INTEGER,
                    signing_bonus BIGINT,
                    guaranteed_money BIGINT,
                    
                    -- Metadata
                    nfl_id VARCHAR(50),
                    espn_id VARCHAR(50),
                    pfr_id VARCHAR(50),
                    
                    -- Data Quality and Tracking
                    data_completeness_score DECIMAL(5,2),
                    last_scraped TIMESTAMP,
                    scrape_count INTEGER DEFAULT 1,
                    data_sources TEXT[], -- Array of sources used
                    
                    -- Timestamps
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Unique constraint
                    UNIQUE(name, team_id)
                )
            ''',
            
            # Social Media Metrics (Historical tracking)
            'social_media_metrics': '''
                CREATE TABLE IF NOT EXISTS social_media_metrics (
                    id SERIAL PRIMARY KEY,
                    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
                    
                    -- Platform URLs
                    twitter_url TEXT,
                    instagram_url TEXT,
                    tiktok_url TEXT,
                    youtube_url TEXT,
                    facebook_url TEXT,
                    
                    -- Twitter Metrics
                    twitter_handle VARCHAR(100),
                    twitter_followers INTEGER,
                    twitter_following INTEGER,
                    twitter_tweets INTEGER,
                    twitter_verified BOOLEAN DEFAULT FALSE,
                    twitter_engagement_rate DECIMAL(5,2),
                    
                    -- Instagram Metrics
                    instagram_handle VARCHAR(100),
                    instagram_followers INTEGER,
                    instagram_following INTEGER,
                    instagram_posts INTEGER,
                    instagram_verified BOOLEAN DEFAULT FALSE,
                    instagram_engagement_rate DECIMAL(5,2),
                    
                    -- TikTok Metrics
                    tiktok_handle VARCHAR(100),
                    tiktok_followers INTEGER,
                    tiktok_following INTEGER,
                    tiktok_likes INTEGER,
                    tiktok_videos INTEGER,
                    tiktok_verified BOOLEAN DEFAULT FALSE,
                    
                    -- YouTube Metrics
                    youtube_handle VARCHAR(100),
                    youtube_subscribers INTEGER,
                    youtube_views BIGINT,
                    youtube_videos INTEGER,
                    youtube_verified BOOLEAN DEFAULT FALSE,
                    
                    -- Aggregated Metrics
                    total_social_followers BIGINT,
                    social_media_score DECIMAL(8,2),
                    
                    -- Metadata
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            
            # Scraping Jobs (Track scraping operations)
            'scraping_jobs': '''
                CREATE TABLE IF NOT EXISTS scraping_jobs (
                    id SERIAL PRIMARY KEY,
                    job_type VARCHAR(50) NOT NULL, -- 'roster', 'social', 'stats', 'comprehensive'
                    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
                    team VARCHAR(100),
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    
                    -- Progress Tracking
                    total_players INTEGER DEFAULT 0,
                    processed_players INTEGER DEFAULT 0,
                    successful_updates INTEGER DEFAULT 0,
                    failed_updates INTEGER DEFAULT 0,
                    
                    -- Performance Metrics
                    avg_time_per_player DECIMAL(8,2),
                    requests_made INTEGER DEFAULT 0,
                    cache_hits INTEGER DEFAULT 0,
                    
                    -- Configuration
                    config JSONB,
                    
                    -- Results
                    results JSONB,
                    error_log TEXT,
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            
            # Data Change Log (Track all changes for incremental updates)
            'data_changes': '''
                CREATE TABLE IF NOT EXISTS data_changes (
                    id SERIAL PRIMARY KEY,
                    table_name VARCHAR(100) NOT NULL,
                    record_id INTEGER NOT NULL,
                    change_type VARCHAR(20) NOT NULL, -- 'INSERT', 'UPDATE', 'DELETE'
                    old_values JSONB,
                    new_values JSONB,
                    changed_fields TEXT[],
                    change_source VARCHAR(100), -- 'scraper', 'manual', 'api'
                    scraping_job_id INTEGER REFERENCES scraping_jobs(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            
            # Gravity Scores (Historical tracking)
            'gravity_scores': '''
                CREATE TABLE IF NOT EXISTS gravity_scores (
                    id SERIAL PRIMARY KEY,
                    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
                    
                    -- Gravity Components
                    brand_power DECIMAL(8,2),
                    proof DECIMAL(8,2),
                    proximity DECIMAL(8,2),
                    velocity DECIMAL(8,2),
                    risk DECIMAL(8,2),
                    total_gravity DECIMAL(8,2),
                    
                    -- Calculation Metadata
                    calculation_version VARCHAR(20),
                    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_current BOOLEAN DEFAULT TRUE,
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            
            # Performance Cache (For fast dashboard queries)
            'performance_cache': '''
                CREATE TABLE IF NOT EXISTS performance_cache (
                    id SERIAL PRIMARY KEY,
                    cache_key VARCHAR(200) UNIQUE NOT NULL,
                    cache_data JSONB NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''
        }
        
        # Create indexes for performance
        indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_players_team_id ON players(team_id)",
            "CREATE INDEX IF NOT EXISTS idx_players_position ON players(position)",
            "CREATE INDEX IF NOT EXISTS idx_players_status ON players(status)",
            "CREATE INDEX IF NOT EXISTS idx_players_last_scraped ON players(last_scraped)",
            "CREATE INDEX IF NOT EXISTS idx_social_media_player_id ON social_media_metrics(player_id)",
            "CREATE INDEX IF NOT EXISTS idx_social_media_scraped_at ON social_media_metrics(scraped_at)",
            "CREATE INDEX IF NOT EXISTS idx_scraping_jobs_status ON scraping_jobs(status)",
            "CREATE INDEX IF NOT EXISTS idx_scraping_jobs_job_type ON scraping_jobs(job_type)",
            "CREATE INDEX IF NOT EXISTS idx_data_changes_table_record ON data_changes(table_name, record_id)",
            "CREATE INDEX IF NOT EXISTS idx_data_changes_created_at ON data_changes(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_gravity_scores_player_id ON gravity_scores(player_id)",
            "CREATE INDEX IF NOT EXISTS idx_gravity_scores_current ON gravity_scores(is_current)",
            "CREATE INDEX IF NOT EXISTS idx_performance_cache_key ON performance_cache(cache_key)",
            "CREATE INDEX IF NOT EXISTS idx_performance_cache_expires ON performance_cache(expires_at)"
        ]
        
        try:
            with self.connection.cursor() as cursor:
                # Create tables
                for table_name, table_sql in schema_sql.items():
                    cursor.execute(table_sql)
                    logger.info(f"✅ Created/verified table: {table_name}")
                
                # Create indexes
                for index_sql in indexes_sql:
                    cursor.execute(index_sql)
                
                # Create or update triggers for automatic timestamp updates
                cursor.execute('''
                    CREATE OR REPLACE FUNCTION update_updated_at_column()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        NEW.updated_at = CURRENT_TIMESTAMP;
                        RETURN NEW;
                    END;
                    $$ language 'plpgsql';
                ''')
                
                # Apply triggers to relevant tables
                trigger_tables = ['teams', 'players']
                for table in trigger_tables:
                    cursor.execute(f'''
                        DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};
                        CREATE TRIGGER update_{table}_updated_at 
                        BEFORE UPDATE ON {table}
                        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
                    ''')
                
                self.connection.commit()
                logger.info("🚀 Enhanced database schema created successfully with performance optimizations")
                
        except Exception as e:
            logger.error(f"Error creating enhanced schema: {e}")
            self.connection.rollback()
            raise
    
    def start_scraping_job(self, job_type: str, team: str = None, config: Dict = None) -> int:
        """Start a new scraping job and return job ID."""
        insert_sql = '''
            INSERT INTO scraping_jobs (job_type, team, config)
            VALUES (%s, %s, %s)
            RETURNING id
        '''
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(insert_sql, (job_type, team, json.dumps(config or {})))
                job_id = cursor.fetchone()['id']
                self.connection.commit()
                logger.info(f"Started scraping job {job_id}: {job_type} for {team or 'all teams'}")
                return job_id
        except Exception as e:
            logger.error(f"Error starting scraping job: {e}")
            self.connection.rollback()
            raise
    
    def update_scraping_job_progress(self, job_id: int, processed: int, successful: int, failed: int):
        """Update scraping job progress."""
        update_sql = '''
            UPDATE scraping_jobs 
            SET processed_players = %s, successful_updates = %s, failed_updates = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        '''
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(update_sql, (processed, successful, failed, job_id))
                self.connection.commit()
        except Exception as e:
            logger.error(f"Error updating scraping job {job_id}: {e}")
            self.connection.rollback()
    
    def complete_scraping_job(self, job_id: int, results: Dict = None, error_log: str = None):
        """Mark scraping job as completed."""
        status = 'failed' if error_log else 'completed'
        update_sql = '''
            UPDATE scraping_jobs 
            SET status = %s, end_time = CURRENT_TIMESTAMP, results = %s, error_log = %s
            WHERE id = %s
        '''
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(update_sql, (status, json.dumps(results or {}), error_log, job_id))
                self.connection.commit()
                logger.info(f"Completed scraping job {job_id} with status: {status}")
        except Exception as e:
            logger.error(f"Error completing scraping job {job_id}: {e}")
            self.connection.rollback()
    
    def upsert_player_bulk(self, players_data: List[Dict], job_id: int = None) -> Dict[str, int]:
        """
        Bulk insert/update players with incremental data preservation.
        Returns statistics about operations performed.
        """
        if not players_data:
            return {"inserted": 0, "updated": 0, "skipped": 0}
        
        stats = {"inserted": 0, "updated": 0, "skipped": 0}
        
        try:
            with self.connection.cursor() as cursor:
                for player_data in players_data:
                    # Check if player exists and needs updating
                    existing_player = self._get_existing_player(cursor, player_data['name'], player_data.get('team'))
                    
                    if existing_player:
                        # Check if data has actually changed
                        if self._has_significant_changes(existing_player, player_data):
                            player_id = self._update_player(cursor, existing_player['id'], player_data, job_id)
                            stats["updated"] += 1
                        else:
                            # Update last_scraped timestamp only
                            cursor.execute(
                                "UPDATE players SET last_scraped = CURRENT_TIMESTAMP WHERE id = %s",
                                (existing_player['id'],)
                            )
                            stats["skipped"] += 1
                    else:
                        # Insert new player
                        player_id = self._insert_player(cursor, player_data, job_id)
                        stats["inserted"] += 1
                
                self.connection.commit()
                logger.info(f"Bulk upsert completed: {stats}")
                return stats
                
        except Exception as e:
            logger.error(f"Error in bulk upsert: {e}")
            self.connection.rollback()
            raise
    
    def _get_existing_player(self, cursor, name: str, team: str) -> Optional[Dict]:
        """Get existing player by name and team."""
        cursor.execute('''
            SELECT p.*, t.name as team_name
            FROM players p
            LEFT JOIN teams t ON p.team_id = t.id
            WHERE p.name = %s AND (t.name = %s OR %s IS NULL)
        ''', (name, team, team))
        
        result = cursor.fetchone()
        return dict(result) if result else None
    
    def _has_significant_changes(self, existing: Dict, new_data: Dict) -> bool:
        """Check if new data has significant changes worth updating."""
        # Fields to check for changes (ignore timestamps and metadata)
        check_fields = [
            'jersey_number', 'position', 'height', 'weight', 'age', 'status',
            'games_played', 'passing_yards', 'rushing_yards', 'receiving_yards',
            'tackles', 'sacks', 'interceptions'
        ]
        
        for field in check_fields:
            if field in new_data:
                existing_value = existing.get(field)
                new_value = new_data.get(field)
                
                # Handle None values and type differences
                if existing_value != new_value:
                    # Special handling for numeric fields
                    if isinstance(existing_value, (int, float)) and isinstance(new_value, (int, float)):
                        if abs(existing_value - new_value) > 0.01:  # Threshold for float comparison
                            return True
                    elif str(existing_value) != str(new_value):
                        return True
        
        return False
    
    def _insert_player(self, cursor, player_data: Dict, job_id: int = None) -> int:
        """Insert new player and log the change."""
        # Get or create team ID
        team_id = self._get_or_create_team_id(cursor, player_data.get('team'))
        
        # Prepare player data
        insert_data = self._prepare_player_data(player_data, team_id)
        
        # Insert player
        columns = list(insert_data.keys())
        values = list(insert_data.values())
        placeholders = ', '.join(['%s'] * len(values))
        
        insert_sql = f'''
            INSERT INTO players ({', '.join(columns)})
            VALUES ({placeholders})
            RETURNING id
        '''
        
        cursor.execute(insert_sql, values)
        player_id = cursor.fetchone()['id']
        
        # Log the change
        self._log_data_change(cursor, 'players', player_id, 'INSERT', None, insert_data, job_id)
        
        return player_id
    
    def _update_player(self, cursor, player_id: int, player_data: Dict, job_id: int = None) -> int:
        """Update existing player and log the changes."""
        # Get current player data for change tracking
        cursor.execute("SELECT * FROM players WHERE id = %s", (player_id,))
        old_data = dict(cursor.fetchone())
        
        # Get or create team ID
        team_id = self._get_or_create_team_id(cursor, player_data.get('team'))
        
        # Prepare update data
        update_data = self._prepare_player_data(player_data, team_id)
        update_data['scrape_count'] = old_data.get('scrape_count', 0) + 1
        
        # Build update SQL
        set_clauses = []
        values = []
        changed_fields = []
        
        for column, value in update_data.items():
            if column != 'id' and old_data.get(column) != value:
                set_clauses.append(f"{column} = %s")
                values.append(value)
                changed_fields.append(column)
        
        if set_clauses:
            values.append(player_id)
            update_sql = f"UPDATE players SET {', '.join(set_clauses)} WHERE id = %s"
            cursor.execute(update_sql, values)
            
            # Log the changes
            self._log_data_change(cursor, 'players', player_id, 'UPDATE', old_data, update_data, job_id, changed_fields)
        
        return player_id
    
    def _get_or_create_team_id(self, cursor, team_name: str) -> int:
        """Get existing team ID or create new team."""
        if not team_name:
            return None
        
        # Try to get existing team
        cursor.execute("SELECT id FROM teams WHERE name = %s", (team_name,))
        result = cursor.fetchone()
        
        if result:
            return result['id']
        
        # Create new team
        cursor.execute('''
            INSERT INTO teams (name, full_name, slug)
            VALUES (%s, %s, %s)
            RETURNING id
        ''', (team_name, team_name, team_name.lower().replace(' ', '-')))
        
        return cursor.fetchone()['id']
    
    def _prepare_player_data(self, raw_data: Dict, team_id: int) -> Dict:
        """Prepare and clean player data for database insertion."""
        # Map common field variations to standard names
        field_mapping = {
            'Player': 'name',
            'Jersey': 'jersey_number',
            'Position': 'position',
            'Height': 'height',
            'Weight': 'weight',
            'Age': 'age',
            'College': 'college',
            'Experience': 'experience',
            'Status': 'status'
        }
        
        prepared_data = {}
        
        # Apply field mapping
        for old_key, new_key in field_mapping.items():
            if old_key in raw_data:
                prepared_data[new_key] = raw_data[old_key]
        
        # Direct mapping for fields that match
        direct_fields = [
            'name', 'jersey_number', 'position', 'height', 'weight', 'age', 'college', 
            'experience', 'status', 'injury_status', 'contract_status', 'games_played',
            'games_started', 'passing_yards', 'passing_tds', 'rushing_yards', 'rushing_tds',
            'receiving_yards', 'receiving_tds', 'tackles', 'sacks', 'interceptions',
            'pro_bowls', 'all_pro_selections', 'current_salary', 'contract_value'
        ]
        
        for field in direct_fields:
            if field in raw_data and raw_data[field] is not None:
                prepared_data[field] = raw_data[field]
        
        # Add metadata
        prepared_data['team_id'] = team_id
        prepared_data['last_scraped'] = datetime.now()
        prepared_data['data_sources'] = raw_data.get('data_sources', ['scraper'])
        
        # Calculate data completeness score
        total_fields = len(direct_fields)
        filled_fields = sum(1 for field in direct_fields if field in prepared_data and prepared_data[field] is not None)
        prepared_data['data_completeness_score'] = round((filled_fields / total_fields) * 100, 2)
        
        return prepared_data
    
    def _log_data_change(self, cursor, table_name: str, record_id: int, change_type: str, 
                        old_values: Dict, new_values: Dict, job_id: int = None, changed_fields: List = None):
        """Log data changes for audit and incremental update tracking."""
        cursor.execute('''
            INSERT INTO data_changes 
            (table_name, record_id, change_type, old_values, new_values, changed_fields, 
             change_source, scraping_job_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            table_name, record_id, change_type,
            json.dumps(old_values, default=str) if old_values else None,
            json.dumps(new_values, default=str) if new_values else None,
            changed_fields or [],
            'scraper',
            job_id
        ))
    
    def get_players_needing_update(self, hours_threshold: int = 24) -> List[Dict]:
        """Get players that haven't been scraped recently."""
        query = '''
            SELECT p.*, t.name as team_name
            FROM players p
            LEFT JOIN teams t ON p.team_id = t.id
            WHERE p.last_scraped IS NULL 
               OR p.last_scraped < NOW() - INTERVAL '%s hours'
            ORDER BY p.last_scraped ASC NULLS FIRST
        '''
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, (hours_threshold,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting players needing update: {e}")
            return []
    
    def get_scraping_stats(self, job_id: int = None) -> Dict:
        """Get scraping statistics."""
        if job_id:
            query = "SELECT * FROM scraping_jobs WHERE id = %s"
            params = (job_id,)
        else:
            query = '''
                SELECT 
                    COUNT(*) as total_jobs,
                    SUM(total_players) as total_players_processed,
                    SUM(successful_updates) as total_successful,
                    SUM(failed_updates) as total_failed,
                    AVG(avg_time_per_player) as avg_time_per_player
                FROM scraping_jobs 
                WHERE status = 'completed'
            '''
            params = None
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone()
                return dict(result) if result else {}
        except Exception as e:
            logger.error(f"Error getting scraping stats: {e}")
            return {}
    
    def clean_old_data(self, days_to_keep: int = 30):
        """Clean old data changes and expired cache entries."""
        try:
            with self.connection.cursor() as cursor:
                # Clean old data changes
                cursor.execute('''
                    DELETE FROM data_changes 
                    WHERE created_at < NOW() - INTERVAL '%s days'
                ''', (days_to_keep,))
                
                # Clean expired cache entries
                cursor.execute('''
                    DELETE FROM performance_cache 
                    WHERE expires_at < NOW()
                ''')
                
                # Clean old social media metrics (keep only latest 5 per player)
                cursor.execute('''
                    DELETE FROM social_media_metrics 
                    WHERE id NOT IN (
                        SELECT id FROM (
                            SELECT id, ROW_NUMBER() OVER (
                                PARTITION BY player_id ORDER BY scraped_at DESC
                            ) as rn
                            FROM social_media_metrics
                        ) ranked WHERE rn <= 5
                    )
                ''')
                
                self.connection.commit()
                logger.info(f"Cleaned old data (keeping {days_to_keep} days)")
                
        except Exception as e:
            logger.error(f"Error cleaning old data: {e}")
            self.connection.rollback()
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

# Example usage and testing
if __name__ == "__main__":
    # Initialize enhanced database
    db = EnhancedNFLDatabase()
    
    # Test with sample data
    sample_players = [
        {
            'name': 'Patrick Mahomes',
            'team': 'Kansas City Chiefs',
            'position': 'QB',
            'jersey_number': '15',
            'age': 28,
            'height': '6-3',
            'weight': 230,
            'college': 'Texas Tech',
            'passing_yards': 4839,
            'passing_tds': 41,
            'data_sources': ['nfl.com', 'espn.com']
        },
        {
            'name': 'Travis Kelce',
            'team': 'Kansas City Chiefs',
            'position': 'TE',
            'jersey_number': '87',
            'age': 34,
            'height': '6-5',
            'weight': 260,
            'college': 'Cincinnati',
            'receiving_yards': 984,
            'receiving_tds': 5,
            'data_sources': ['nfl.com']
        }
    ]
    
    # Start a test scraping job
    job_id = db.start_scraping_job('test', 'chiefs', {'test': True})
    
    # Bulk upsert players
    stats = db.upsert_player_bulk(sample_players, job_id)
    print(f"Upsert stats: {stats}")
    
    # Complete the job
    db.complete_scraping_job(job_id, stats)
    
    # Get scraping stats
    job_stats = db.get_scraping_stats(job_id)
    print(f"Job stats: {job_stats}")
    
    # Close connection
    db.close()