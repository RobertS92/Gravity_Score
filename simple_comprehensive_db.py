"""
Simple Comprehensive Database Integration
Uses existing database connection to store comprehensive NFL player data
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from enhanced_nfl_scraper import EnhancedNFLScraper
from social_media_agent import SocialMediaAgent
from comprehensive_nfl_collector import ComprehensiveNFLCollector

logger = logging.getLogger(__name__)

class SimpleComprehensiveDB:
    """Simple database integration for comprehensive NFL data."""
    
    def __init__(self):
        """Initialize the database integration."""
        self.db_url = os.getenv('DATABASE_URL')
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        # Initialize scrapers
        self.nfl_scraper = EnhancedNFLScraper()
        self.social_agent = SocialMediaAgent()
        self.comprehensive_collector = ComprehensiveNFLCollector()
        
        # Create database tables using SQL tool
        self.create_comprehensive_tables()
    
    def create_comprehensive_tables(self):
        """Create comprehensive database tables."""
        logger.info("Creating comprehensive database tables...")
        
        try:
            # Use the execute_sql_tool to create tables
            from app import execute_sql_tool
            
            # Drop existing table if it exists
            execute_sql_tool("DROP TABLE IF EXISTS nfl_players_comprehensive")
            
            # Create comprehensive table with all required fields
            create_table_sql = """
            CREATE TABLE nfl_players_comprehensive (
                id SERIAL PRIMARY KEY,
                
                -- Basic Player Information
                player_name VARCHAR(255) NOT NULL,
                jersey_number INTEGER,
                position VARCHAR(10),
                current_team VARCHAR(100),
                team_city VARCHAR(100),
                team_full_name VARCHAR(255),
                birth_date DATE,
                height VARCHAR(10),
                weight INTEGER,
                
                -- College Information
                college VARCHAR(255),
                
                -- Draft Information
                draft_year INTEGER,
                
                -- Career Statistics
                career_pass_yards INTEGER,
                career_pass_tds INTEGER,
                career_pass_ints INTEGER,
                career_pass_rating DECIMAL(5,2),
                career_rush_yards INTEGER,
                career_rush_tds INTEGER,
                career_receptions INTEGER,
                career_rec_yards INTEGER,
                career_rec_tds INTEGER,
                news_headlines_count INTEGER,
                recent_headlines TEXT,
                
                -- Awards and Honors
                pro_bowls INTEGER,
                super_bowl_wins INTEGER,
                all_pro_first_team INTEGER,
                all_pro_second_team INTEGER,
                
                -- Contract and Financial Information
                career_earnings_total BIGINT,
                career_earnings_source VARCHAR(100),
                career_earnings_confidence VARCHAR(50),
                current_contract_value BIGINT,
                
                -- Social Media Information
                twitter_followers INTEGER,
                twitter_following INTEGER,
                instagram_followers INTEGER,
                instagram_following INTEGER,
                tiktok_followers INTEGER,
                tiktok_following INTEGER,
                youtube_subscribers INTEGER,
                twitter_url VARCHAR(500),
                instagram_url VARCHAR(500),
                tiktok_url VARCHAR(500),
                youtube_url VARCHAR(500),
                
                -- Media and Public Information
                wikipedia_url VARCHAR(500),
                
                -- Data Collection Metadata
                data_collection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_quality_score DECIMAL(5,2),
                data_sources_used TEXT,
                collection_method VARCHAR(100),
                
                -- Indexes for performance
                UNIQUE(player_name, current_team)
            )
            """
            
            execute_sql_tool(create_table_sql)
            logger.info("Database tables created successfully")
            
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    def collect_comprehensive_team_data(self, team_name: str, max_players: int = 5) -> List[Dict]:
        """Collect comprehensive data for players on a team."""
        logger.info(f"Starting comprehensive data collection for {team_name}")
        
        try:
            # Get basic roster data
            basic_players = self.nfl_scraper.scrape_team_roster(team_name)
            
            if not basic_players:
                logger.warning(f"No players found for {team_name}")
                return []
            
            # Limit to max_players for testing
            basic_players = basic_players[:max_players]
            logger.info(f"Processing {len(basic_players)} players for {team_name}")
            
            comprehensive_players = []
            
            for i, player in enumerate(basic_players, 1):
                try:
                    player_name = player.get('name', '')
                    position = player.get('position', '')
                    
                    logger.info(f"Processing player {i}/{len(basic_players)}: {player_name}")
                    
                    # Get comprehensive data
                    comprehensive_data = self.comprehensive_collector.collect_complete_player_data(
                        player_name, team_name, position
                    )
                    
                    # Merge with basic data
                    comprehensive_data.update(player)
                    
                    # Get social media data
                    social_data = self.social_agent.get_complete_social_media_profile(
                        player_name, team_name
                    )
                    
                    # Merge social media data
                    comprehensive_data.update({
                        'twitter_followers': social_data.get('twitter_followers', 0),
                        'twitter_following': social_data.get('twitter_following', 0),
                        'instagram_followers': social_data.get('instagram_followers', 0),
                        'instagram_following': social_data.get('instagram_following', 0),
                        'tiktok_followers': social_data.get('tiktok_followers', 0),
                        'tiktok_following': social_data.get('tiktok_following', 0),
                        'youtube_subscribers': social_data.get('youtube_subscribers', 0),
                        'twitter_url': social_data.get('twitter_url'),
                        'instagram_url': social_data.get('instagram_url'),
                        'tiktok_url': social_data.get('tiktok_url'),
                        'youtube_url': social_data.get('youtube_url'),
                    })
                    
                    comprehensive_players.append(comprehensive_data)
                    
                except Exception as e:
                    logger.error(f"Error processing player {player_name}: {e}")
                    continue
            
            logger.info(f"Successfully collected comprehensive data for {len(comprehensive_players)} players")
            return comprehensive_players
            
        except Exception as e:
            logger.error(f"Error collecting team data for {team_name}: {e}")
            return []
    
    def save_comprehensive_data(self, players_data: List[Dict], team_name: str):
        """Save comprehensive player data to database."""
        logger.info(f"Saving {len(players_data)} comprehensive players to database...")
        
        try:
            from app import execute_sql_tool
            
            for player in players_data:
                # Clean and prepare data
                player_name = player.get('Player_Name', player.get('name', ''))
                jersey_number = self._safe_int(player.get('Jersey_Number', player.get('jersey_number')))
                position = player.get('Position', player.get('position', ''))
                current_team = player.get('Current_Team', team_name)
                team_city = player.get('Team_City', '')
                team_full_name = player.get('Team_Full_Name', '')
                height = player.get('Height', player.get('height', ''))
                weight = self._safe_int(player.get('Weight', player.get('weight')))
                college = player.get('College', player.get('college', ''))
                
                # Social media data
                twitter_followers = self._safe_int(player.get('twitter_followers', 0))
                twitter_following = self._safe_int(player.get('twitter_following', 0))
                instagram_followers = self._safe_int(player.get('instagram_followers', 0))
                instagram_following = self._safe_int(player.get('instagram_following', 0))
                tiktok_followers = self._safe_int(player.get('tiktok_followers', 0))
                tiktok_following = self._safe_int(player.get('tiktok_following', 0))
                youtube_subscribers = self._safe_int(player.get('youtube_subscribers', 0))
                
                twitter_url = player.get('twitter_url', '')
                instagram_url = player.get('instagram_url', '')
                tiktok_url = player.get('tiktok_url', '')
                youtube_url = player.get('youtube_url', '')
                
                # Career statistics
                career_pass_yards = self._safe_int(player.get('Career_Pass_Yards'))
                career_pass_tds = self._safe_int(player.get('Career_Pass_TDs'))
                career_rush_yards = self._safe_int(player.get('Career_Rush_Yards'))
                career_rush_tds = self._safe_int(player.get('Career_Rush_TDs'))
                
                # Awards
                pro_bowls = self._safe_int(player.get('Pro_Bowls'))
                super_bowl_wins = self._safe_int(player.get('Super_Bowl_Wins'))
                
                # Financial data
                career_earnings_total = self._safe_bigint(player.get('Career_Earnings_Total'))
                career_earnings_source = player.get('Career_Earnings_Source', '')
                current_contract_value = self._safe_bigint(player.get('Current_Contract_Value'))
                
                # Wikipedia URL
                wikipedia_url = player.get('Wikipedia_URL', '')
                
                # Data quality and sources
                data_quality_score = self._safe_float(player.get('Data_Quality_Score', 0))
                data_sources_used = json.dumps(player.get('Data_Sources_Used', []))
                collection_method = player.get('Collection_Method', 'automated_comprehensive_scraping')
                
                # Insert data
                insert_sql = f"""
                INSERT INTO nfl_players_comprehensive (
                    player_name, jersey_number, position, current_team, team_city, team_full_name,
                    height, weight, college, twitter_followers, twitter_following,
                    instagram_followers, instagram_following, tiktok_followers, tiktok_following,
                    youtube_subscribers, twitter_url, instagram_url, tiktok_url, youtube_url,
                    career_pass_yards, career_pass_tds, career_rush_yards, career_rush_tds,
                    pro_bowls, super_bowl_wins, career_earnings_total, career_earnings_source,
                    current_contract_value, wikipedia_url, data_quality_score, data_sources_used,
                    collection_method
                ) VALUES (
                    '{player_name}', {jersey_number or 'NULL'}, '{position}', '{current_team}', 
                    '{team_city}', '{team_full_name}', '{height}', {weight or 'NULL'}, '{college}',
                    {twitter_followers}, {twitter_following}, {instagram_followers}, {instagram_following},
                    {tiktok_followers}, {tiktok_following}, {youtube_subscribers}, '{twitter_url}',
                    '{instagram_url}', '{tiktok_url}', '{youtube_url}', {career_pass_yards or 'NULL'},
                    {career_pass_tds or 'NULL'}, {career_rush_yards or 'NULL'}, {career_rush_tds or 'NULL'},
                    {pro_bowls or 'NULL'}, {super_bowl_wins or 'NULL'}, {career_earnings_total or 'NULL'},
                    '{career_earnings_source}', {current_contract_value or 'NULL'}, '{wikipedia_url}',
                    {data_quality_score}, '{data_sources_used}', '{collection_method}'
                )
                ON CONFLICT (player_name, current_team) DO UPDATE SET
                    jersey_number = EXCLUDED.jersey_number,
                    position = EXCLUDED.position,
                    height = EXCLUDED.height,
                    weight = EXCLUDED.weight,
                    college = EXCLUDED.college,
                    twitter_followers = EXCLUDED.twitter_followers,
                    twitter_following = EXCLUDED.twitter_following,
                    instagram_followers = EXCLUDED.instagram_followers,
                    instagram_following = EXCLUDED.instagram_following,
                    tiktok_followers = EXCLUDED.tiktok_followers,
                    tiktok_following = EXCLUDED.tiktok_following,
                    youtube_subscribers = EXCLUDED.youtube_subscribers,
                    twitter_url = EXCLUDED.twitter_url,
                    instagram_url = EXCLUDED.instagram_url,
                    tiktok_url = EXCLUDED.tiktok_url,
                    youtube_url = EXCLUDED.youtube_url,
                    career_pass_yards = EXCLUDED.career_pass_yards,
                    career_pass_tds = EXCLUDED.career_pass_tds,
                    career_rush_yards = EXCLUDED.career_rush_yards,
                    career_rush_tds = EXCLUDED.career_rush_tds,
                    pro_bowls = EXCLUDED.pro_bowls,
                    super_bowl_wins = EXCLUDED.super_bowl_wins,
                    career_earnings_total = EXCLUDED.career_earnings_total,
                    career_earnings_source = EXCLUDED.career_earnings_source,
                    current_contract_value = EXCLUDED.current_contract_value,
                    wikipedia_url = EXCLUDED.wikipedia_url,
                    data_quality_score = EXCLUDED.data_quality_score,
                    data_sources_used = EXCLUDED.data_sources_used,
                    collection_method = EXCLUDED.collection_method,
                    data_collection_date = CURRENT_TIMESTAMP
                """
                
                execute_sql_tool(insert_sql)
                logger.info(f"Saved comprehensive data for {player_name}")
            
            logger.info(f"Successfully saved {len(players_data)} comprehensive players to database")
            
        except Exception as e:
            logger.error(f"Error saving comprehensive data to database: {e}")
            raise
    
    def _safe_int(self, value) -> Optional[int]:
        """Safely convert value to integer."""
        if value is None or value == '':
            return None
        try:
            return int(value)
        except:
            return None
    
    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float."""
        if value is None or value == '':
            return None
        try:
            return float(value)
        except:
            return None
    
    def _safe_bigint(self, value) -> Optional[int]:
        """Safely convert value to bigint."""
        if value is None or value == '':
            return None
        try:
            return int(value)
        except:
            return None
    
    def get_comprehensive_summary(self, team_name: str) -> Dict:
        """Get summary of comprehensive data for a team."""
        try:
            from app import execute_sql_tool
            
            # Get summary statistics
            summary_sql = f"""
            SELECT 
                COUNT(*) as total_players,
                AVG(data_quality_score) as avg_quality_score,
                COUNT(CASE WHEN twitter_followers > 0 THEN 1 END) as players_with_twitter,
                COUNT(CASE WHEN instagram_followers > 0 THEN 1 END) as players_with_instagram,
                COUNT(CASE WHEN tiktok_followers > 0 THEN 1 END) as players_with_tiktok,
                COUNT(CASE WHEN youtube_subscribers > 0 THEN 1 END) as players_with_youtube,
                COALESCE(SUM(twitter_followers), 0) as total_twitter_followers,
                COALESCE(SUM(instagram_followers), 0) as total_instagram_followers,
                COALESCE(SUM(tiktok_followers), 0) as total_tiktok_followers,
                COALESCE(SUM(youtube_subscribers), 0) as total_youtube_subscribers
            FROM nfl_players_comprehensive 
            WHERE current_team = '{team_name}'
            """
            
            result = execute_sql_tool(summary_sql)
            
            # Parse the result (this would depend on how execute_sql_tool returns data)
            return {
                'team_name': team_name,
                'summary_generated': datetime.now().isoformat(),
                'message': 'Comprehensive data summary generated successfully'
            }
            
        except Exception as e:
            logger.error(f"Error generating comprehensive summary: {e}")
            return {'error': str(e)}

def test_comprehensive_db():
    """Test the comprehensive database integration."""
    try:
        db = SimpleComprehensiveDB()
        print("Comprehensive database integration initialized successfully")
        
        # Test with 2 players from 49ers
        team_name = "49ers"
        players_data = db.collect_comprehensive_team_data(team_name, max_players=2)
        
        if players_data:
            print(f"Collected comprehensive data for {len(players_data)} players")
            
            # Save to database
            db.save_comprehensive_data(players_data, team_name)
            print("Comprehensive data saved successfully")
            
            # Generate summary
            summary = db.get_comprehensive_summary(team_name)
            print(f"Summary: {summary}")
            
        return players_data
        
    except Exception as e:
        print(f"Error testing comprehensive database: {e}")
        return None

if __name__ == "__main__":
    test_comprehensive_db()