#!/usr/bin/env python3
"""
Enhanced Database Manager for NFL Player Data with Social Media Integration
Handles comprehensive player data with all 70+ fields including social media
"""

import os
import logging
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy import create_engine, text, MetaData, Table, Column, String, Integer, Float, DateTime, Text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import insert

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class EnhancedDatabaseManager:
    """
    Enhanced database manager for comprehensive NFL player data
    """
    
    def __init__(self):
        self.database_url = os.environ.get('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not found")
        
        # Create engine and session
        self.engine = create_engine(self.database_url)
        self.Session = sessionmaker(bind=self.engine)
        self.metadata = MetaData()
        
        # Define the comprehensive players table
        self.players_table = Table(
            'comprehensive_nfl_players',
            self.metadata,
            # Basic Information
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('name', String(100), nullable=False),
            Column('jersey_number', String(10)),
            Column('position', String(10)),
            Column('status', String(20)),
            Column('height', String(10)),
            Column('weight', Integer),
            Column('age', Integer),
            Column('experience', Integer),
            Column('college', String(100)),
            Column('team', String(50), nullable=False),
            Column('current_team', String(50)),
            
            # Social Media Information
            Column('twitter_handle', String(100)),
            Column('instagram_handle', String(100)),
            Column('tiktok_handle', String(100)),
            Column('youtube_handle', String(100)),
            Column('twitter_followers', String(50)),
            Column('instagram_followers', String(50)),
            Column('tiktok_followers', String(50)),
            Column('youtube_subscribers', String(50)),
            Column('twitter_following', String(50)),
            Column('instagram_following', String(50)),
            Column('tiktok_following', String(50)),
            Column('twitter_verified', String(10)),
            Column('instagram_verified', String(10)),
            Column('twitter_url', String(200)),
            Column('instagram_url', String(200)),
            Column('tiktok_url', String(200)),
            Column('youtube_url', String(200)),
            
            # Draft Information
            Column('draft_pick', Integer),
            Column('draft_round', Integer),
            Column('draft_team', String(50)),
            Column('draft_year', Integer),
            
            # Contract Information
            Column('contract_value', String(50)),
            Column('contract_years', Integer),
            Column('current_salary', String(50)),
            Column('cap_hit', String(50)),
            Column('guaranteed_money', String(50)),
            
            # Awards and Recognition
            Column('championships', Integer),
            Column('all_pros', Integer),
            Column('pro_bowls', Integer),
            Column('awards', Text),
            
            # Career Statistics
            Column('career_pass_yards', Integer),
            Column('career_pass_tds', Integer),
            Column('career_pass_ints', Integer),
            Column('career_pass_rating', Float),
            Column('career_rush_yards', Integer),
            Column('career_rush_tds', Integer),
            Column('career_receptions', Integer),
            Column('career_rec_yards', Integer),
            Column('career_rec_tds', Integer),
            Column('career_tackles', Integer),
            Column('career_sacks', Float),
            Column('career_interceptions', Integer),
            Column('career_games', Integer),
            Column('career_starts', Integer),
            Column('career_pass_attempts', Integer),
            Column('career_pass_completions', Integer),
            
            # 2023 Season Statistics
            Column('passing_yards_2023', Integer),
            Column('passing_tds_2023', Integer),
            Column('rushing_yards_2023', Integer),
            Column('rushing_tds_2023', Integer),
            Column('receiving_yards_2023', Integer),
            Column('receiving_tds_2023', Integer),
            Column('tackles_2023', Integer),
            Column('sacks_2023', Float),
            Column('interceptions_2023', Integer),
            
            # Biographical Information
            Column('birth_date', String(50)),
            Column('birth_place', String(100)),
            Column('high_school', String(100)),
            Column('rookie_of_year', String(10)),
            Column('mvp_awards', Integer),
            Column('hall_of_fame', String(10)),
            
            # Financial Information
            Column('signing_bonus', String(50)),
            Column('dead_money', String(50)),
            
            # URLs and References
            Column('wikipedia_url', String(200)),
            Column('nfl_com_url', String(200)),
            Column('espn_url', String(200)),
            Column('pff_url', String(200)),
            Column('spotrac_url', String(200)),
            Column('google_news_url', String(200)),
            
            # Meta Information
            Column('news_headline_count', Integer),
            Column('recent_headlines', Text),
            Column('news_bio_snippets', Text),
            Column('data_sources', Text),
            Column('last_updated', DateTime),
            Column('data_quality_score', Float),
            Column('comprehensive_enhanced', String(10)),
            
            # Gravity Score Components
            Column('brand_power', Float),
            Column('proof', Float),
            Column('proximity', Float),
            Column('velocity', Float),
            Column('risk', Float),
            Column('total_gravity', Float),
            
            # Data Processing Fields
            Column('data_source', String(50)),
            Column('scraped_at', DateTime),
            Column('created_at', DateTime, default=datetime.utcnow),
            Column('updated_at', DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        )
    
    def create_tables(self):
        """Create all database tables"""
        try:
            self.metadata.create_all(self.engine)
            logger.info("✅ Database tables created successfully")
        except Exception as e:
            logger.error(f"❌ Error creating tables: {str(e)}")
            raise
    
    def insert_player(self, player_data: Dict[str, Any]) -> bool:
        """Insert a new player into the database"""
        try:
            # Clean and prepare data
            cleaned_data = self._clean_player_data(player_data)
            
            with self.engine.begin() as conn:
                conn.execute(self.players_table.insert().values(**cleaned_data))
            
            logger.info(f"✅ Inserted player: {player_data.get('name', 'Unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error inserting player {player_data.get('name', 'Unknown')}: {str(e)}")
            return False
    
    def upsert_player(self, player_data: Dict[str, Any]) -> bool:
        """Insert or update player data (PostgreSQL UPSERT)"""
        try:
            # Clean and prepare data
            cleaned_data = self._clean_player_data(player_data)
            
            with self.engine.begin() as conn:
                # PostgreSQL upsert using ON CONFLICT
                stmt = insert(self.players_table).values(**cleaned_data)
                stmt = stmt.on_conflict_do_update(
                    constraint='comprehensive_nfl_players_pkey',
                    set_=dict(stmt.excluded)
                )
                conn.execute(stmt)
            
            logger.info(f"✅ Upserted player: {player_data.get('name', 'Unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error upserting player {player_data.get('name', 'Unknown')}: {str(e)}")
            return False
    
    def update_player_by_name_team(self, player_data: Dict[str, Any]) -> bool:
        """Update existing player by name and team"""
        try:
            # Clean and prepare data
            cleaned_data = self._clean_player_data(player_data)
            player_name = cleaned_data.get('name')
            team = cleaned_data.get('team')
            
            if not player_name or not team:
                logger.error("❌ Player name and team are required for update")
                return False
            
            with self.engine.begin() as conn:
                result = conn.execute(
                    self.players_table.update()
                    .where(self.players_table.c.name == player_name)
                    .where(self.players_table.c.team == team)
                    .values(**cleaned_data)
                )
                
                if result.rowcount > 0:
                    logger.info(f"✅ Updated player: {player_name}")
                    return True
                else:
                    logger.warning(f"⚠️ No existing player found to update: {player_name}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error updating player {player_data.get('name', 'Unknown')}: {str(e)}")
            return False
    
    def get_player_by_name_team(self, name: str, team: str) -> Optional[Dict[str, Any]]:
        """Get player by name and team"""
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    self.players_table.select()
                    .where(self.players_table.c.name == name)
                    .where(self.players_table.c.team == team)
                ).fetchone()
                
                if result:
                    return dict(result._mapping)
                return None
                
        except Exception as e:
            logger.error(f"❌ Error fetching player {name}: {str(e)}")
            return None
    
    def get_all_players(self) -> List[Dict[str, Any]]:
        """Get all players from database"""
        try:
            with self.engine.begin() as conn:
                result = conn.execute(self.players_table.select()).fetchall()
                return [dict(row._mapping) for row in result]
                
        except Exception as e:
            logger.error(f"❌ Error fetching all players: {str(e)}")
            return []
    
    def get_team_players(self, team: str) -> List[Dict[str, Any]]:
        """Get all players for a specific team"""
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    self.players_table.select()
                    .where(self.players_table.c.team == team)
                ).fetchall()
                return [dict(row._mapping) for row in result]
                
        except Exception as e:
            logger.error(f"❌ Error fetching team {team} players: {str(e)}")
            return []
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with self.engine.begin() as conn:
                # Total players
                total_result = conn.execute(
                    text("SELECT COUNT(*) FROM comprehensive_nfl_players")
                ).scalar()
                
                # Players with social media
                social_result = conn.execute(
                    text("""
                    SELECT COUNT(*) FROM comprehensive_nfl_players 
                    WHERE twitter_handle IS NOT NULL 
                    OR instagram_handle IS NOT NULL 
                    OR tiktok_handle IS NOT NULL 
                    OR youtube_handle IS NOT NULL
                    """)
                ).scalar()
                
                # Average gravity score
                gravity_result = conn.execute(
                    text("SELECT AVG(total_gravity) FROM comprehensive_nfl_players WHERE total_gravity IS NOT NULL")
                ).scalar()
                
                # Teams count
                teams_result = conn.execute(
                    text("SELECT COUNT(DISTINCT team) FROM comprehensive_nfl_players")
                ).scalar()
                
                return {
                    'total_players': total_result or 0,
                    'players_with_social_media': social_result or 0,
                    'average_gravity_score': round(gravity_result or 0, 2),
                    'teams_count': teams_result or 0,
                    'social_media_coverage': round((social_result or 0) / max(total_result or 1, 1) * 100, 1)
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting database stats: {str(e)}")
            return {}
    
    def _clean_player_data(self, player_data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and prepare player data for database insertion"""
        cleaned = {}
        
        # Get all column names from the table
        column_names = [col.name for col in self.players_table.columns if col.name != 'id']
        
        for col_name in column_names:
            value = player_data.get(col_name)
            
            # Handle different data types
            if value is not None:
                # Convert lists to strings
                if isinstance(value, list):
                    cleaned[col_name] = ', '.join(str(v) for v in value)
                # Handle datetime fields
                elif col_name in ['scraped_at', 'last_updated']:
                    if isinstance(value, str):
                        try:
                            cleaned[col_name] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        except:
                            cleaned[col_name] = datetime.utcnow()
                    elif isinstance(value, datetime):
                        cleaned[col_name] = value
                    else:
                        cleaned[col_name] = datetime.utcnow()
                # Handle numeric fields
                elif col_name in ['age', 'experience', 'jersey_number', 'weight', 'championships', 'all_pros', 'pro_bowls']:
                    try:
                        cleaned[col_name] = int(float(str(value)))
                    except:
                        cleaned[col_name] = None
                # Handle float fields
                elif col_name in ['brand_power', 'proof', 'proximity', 'velocity', 'risk', 'total_gravity', 'data_quality_score']:
                    try:
                        cleaned[col_name] = float(value)
                    except:
                        cleaned[col_name] = None
                # Handle string fields
                else:
                    cleaned[col_name] = str(value)[:500]  # Truncate long strings
        
        # Set timestamps
        cleaned['updated_at'] = datetime.utcnow()
        if 'created_at' not in cleaned:
            cleaned['created_at'] = datetime.utcnow()
        
        return cleaned
    
    def export_to_csv(self, filename: str = None) -> str:
        """Export all data to CSV"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data/nfl_players_database_export_{timestamp}.csv"
        
        try:
            players = self.get_all_players()
            df = pd.DataFrame(players)
            df.to_csv(filename, index=False)
            logger.info(f"✅ Exported {len(players)} players to {filename}")
            return filename
        except Exception as e:
            logger.error(f"❌ Error exporting to CSV: {str(e)}")
            return ""

def test_database_connection():
    """Test database connection and functionality"""
    try:
        db = EnhancedDatabaseManager()
        db.create_tables()
        stats = db.get_database_stats()
        print(f"Database connection successful. Stats: {stats}")
        return True
    except Exception as e:
        print(f"Database connection failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_database_connection()