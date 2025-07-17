"""
NFL Gravity Database Pipeline
Complete data collection pipeline that scrapes comprehensive NFL player data
and stores it in PostgreSQL database with all required fields
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from sqlalchemy import create_engine, text
from enhanced_nfl_scraper import EnhancedNFLScraper
from social_media_agent import SocialMediaAgent
from comprehensive_nfl_collector import ComprehensiveNFLCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('nfl_gravity_pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class NFLGravityDatabasePipeline:
    """Complete NFL data pipeline with database integration."""
    
    def __init__(self):
        """Initialize the pipeline with database connection."""
        self.db_url = os.getenv('DATABASE_URL')
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        self.engine = create_engine(self.db_url)
        
        # Initialize scrapers
        self.nfl_scraper = EnhancedNFLScraper()
        self.social_agent = SocialMediaAgent()
        self.comprehensive_collector = ComprehensiveNFLCollector()
        
        # Create database tables
        self.create_database_tables()
        
    def create_database_tables(self):
        """Create comprehensive database tables for NFL data."""
        logger.info("Creating database tables...")
        
        try:
            with self.engine.connect() as conn:
                # Drop existing table if it exists
                conn.execute(text("DROP TABLE IF EXISTS nfl_players_comprehensive"))
                
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
                
                conn.execute(text(create_table_sql))
                conn.commit()
                
                logger.info("Database tables created successfully")
                
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    def collect_team_data(self, team_name: str) -> List[Dict]:
        """Collect comprehensive data for all players on a team."""
        logger.info(f"Starting comprehensive data collection for {team_name}")
        
        try:
            # 1. Get basic roster data
            logger.info("Collecting basic roster data...")
            basic_players = self.nfl_scraper.scrape_team_roster(team_name)
            
            if not basic_players:
                logger.warning(f"No players found for {team_name}")
                return []
            
            logger.info(f"Found {len(basic_players)} players for {team_name}")
            
            # 2. Enhance each player with comprehensive data
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
                    logger.info(f"Collecting social media data for {player_name}")
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
                    
                    # Add delay to be respectful to servers
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error processing player {player_name}: {e}")
                    continue
            
            logger.info(f"Successfully collected comprehensive data for {len(comprehensive_players)} players")
            return comprehensive_players
            
        except Exception as e:
            logger.error(f"Error collecting team data for {team_name}: {e}")
            return []
    
    def save_to_database(self, players_data: List[Dict], team_name: str):
        """Save comprehensive player data to database."""
        logger.info(f"Saving {len(players_data)} players to database...")
        
        try:
            with self.engine.connect() as conn:
                for player in players_data:
                    # Map player data to database columns
                    db_data = {
                        'player_name': player.get('Player_Name', player.get('name', '')),
                        'jersey_number': self._safe_int(player.get('Jersey_Number', player.get('jersey_number'))),
                        'position': player.get('Position', player.get('position', '')),
                        'current_team': player.get('Current_Team', team_name),
                        'team_city': player.get('Team_City', ''),
                        'team_full_name': player.get('Team_Full_Name', ''),
                        'birth_date': self._safe_date(player.get('Birth_Date')),
                        'height': player.get('Height', player.get('height', '')),
                        'weight': self._safe_int(player.get('Weight', player.get('weight'))),
                        'college': player.get('College', player.get('college', '')),
                        'draft_year': self._safe_int(player.get('Draft_Year')),
                        'career_pass_yards': self._safe_int(player.get('Career_Pass_Yards')),
                        'career_pass_tds': self._safe_int(player.get('Career_Pass_TDs')),
                        'career_pass_ints': self._safe_int(player.get('Career_Pass_INTs')),
                        'career_pass_rating': self._safe_float(player.get('Career_Pass_Rating')),
                        'career_rush_yards': self._safe_int(player.get('Career_Rush_Yards')),
                        'career_rush_tds': self._safe_int(player.get('Career_Rush_TDs')),
                        'career_receptions': self._safe_int(player.get('Career_Receptions')),
                        'career_rec_yards': self._safe_int(player.get('Career_Rec_Yards')),
                        'career_rec_tds': self._safe_int(player.get('Career_Rec_TDs')),
                        'news_headlines_count': self._safe_int(player.get('News_Headlines_Count')),
                        'recent_headlines': json.dumps(player.get('Recent_Headlines', [])),
                        'pro_bowls': self._safe_int(player.get('Pro_Bowls')),
                        'super_bowl_wins': self._safe_int(player.get('Super_Bowl_Wins')),
                        'all_pro_first_team': self._safe_int(player.get('All_Pro_First_Team')),
                        'all_pro_second_team': self._safe_int(player.get('All_Pro_Second_Team')),
                        'career_earnings_total': self._safe_bigint(player.get('Career_Earnings_Total')),
                        'career_earnings_source': player.get('Career_Earnings_Source', ''),
                        'career_earnings_confidence': player.get('Career_Earnings_Confidence', ''),
                        'current_contract_value': self._safe_bigint(player.get('Current_Contract_Value')),
                        'twitter_followers': self._safe_int(player.get('twitter_followers', 0)),
                        'twitter_following': self._safe_int(player.get('twitter_following', 0)),
                        'instagram_followers': self._safe_int(player.get('instagram_followers', 0)),
                        'instagram_following': self._safe_int(player.get('instagram_following', 0)),
                        'tiktok_followers': self._safe_int(player.get('tiktok_followers', 0)),
                        'tiktok_following': self._safe_int(player.get('tiktok_following', 0)),
                        'youtube_subscribers': self._safe_int(player.get('youtube_subscribers', 0)),
                        'twitter_url': player.get('twitter_url', ''),
                        'instagram_url': player.get('instagram_url', ''),
                        'tiktok_url': player.get('tiktok_url', ''),
                        'youtube_url': player.get('youtube_url', ''),
                        'wikipedia_url': player.get('Wikipedia_URL', ''),
                        'data_collection_date': datetime.now(),
                        'data_quality_score': self._safe_float(player.get('Data_Quality_Score', 0)),
                        'data_sources_used': json.dumps(player.get('Data_Sources_Used', [])),
                        'collection_method': player.get('Collection_Method', 'automated_comprehensive_scraping')
                    }
                    
                    # Insert or update player data
                    insert_sql = """
                    INSERT INTO nfl_players_comprehensive (
                        player_name, jersey_number, position, current_team, team_city, team_full_name,
                        birth_date, height, weight, college, draft_year,
                        career_pass_yards, career_pass_tds, career_pass_ints, career_pass_rating,
                        career_rush_yards, career_rush_tds, career_receptions, career_rec_yards, career_rec_tds,
                        news_headlines_count, recent_headlines, pro_bowls, super_bowl_wins,
                        all_pro_first_team, all_pro_second_team, career_earnings_total, career_earnings_source,
                        career_earnings_confidence, current_contract_value, twitter_followers, twitter_following,
                        instagram_followers, instagram_following, tiktok_followers, tiktok_following,
                        youtube_subscribers, twitter_url, instagram_url, tiktok_url, youtube_url,
                        wikipedia_url, data_collection_date, data_quality_score, data_sources_used, collection_method
                    ) VALUES (
                        :player_name, :jersey_number, :position, :current_team, :team_city, :team_full_name,
                        :birth_date, :height, :weight, :college, :draft_year,
                        :career_pass_yards, :career_pass_tds, :career_pass_ints, :career_pass_rating,
                        :career_rush_yards, :career_rush_tds, :career_receptions, :career_rec_yards, :career_rec_tds,
                        :news_headlines_count, :recent_headlines, :pro_bowls, :super_bowl_wins,
                        :all_pro_first_team, :all_pro_second_team, :career_earnings_total, :career_earnings_source,
                        :career_earnings_confidence, :current_contract_value, :twitter_followers, :twitter_following,
                        :instagram_followers, :instagram_following, :tiktok_followers, :tiktok_following,
                        :youtube_subscribers, :twitter_url, :instagram_url, :tiktok_url, :youtube_url,
                        :wikipedia_url, :data_collection_date, :data_quality_score, :data_sources_used, :collection_method
                    )
                    ON CONFLICT (player_name, current_team) DO UPDATE SET
                        jersey_number = EXCLUDED.jersey_number,
                        position = EXCLUDED.position,
                        team_city = EXCLUDED.team_city,
                        team_full_name = EXCLUDED.team_full_name,
                        birth_date = EXCLUDED.birth_date,
                        height = EXCLUDED.height,
                        weight = EXCLUDED.weight,
                        college = EXCLUDED.college,
                        draft_year = EXCLUDED.draft_year,
                        career_pass_yards = EXCLUDED.career_pass_yards,
                        career_pass_tds = EXCLUDED.career_pass_tds,
                        career_pass_ints = EXCLUDED.career_pass_ints,
                        career_pass_rating = EXCLUDED.career_pass_rating,
                        career_rush_yards = EXCLUDED.career_rush_yards,
                        career_rush_tds = EXCLUDED.career_rush_tds,
                        career_receptions = EXCLUDED.career_receptions,
                        career_rec_yards = EXCLUDED.career_rec_yards,
                        career_rec_tds = EXCLUDED.career_rec_tds,
                        news_headlines_count = EXCLUDED.news_headlines_count,
                        recent_headlines = EXCLUDED.recent_headlines,
                        pro_bowls = EXCLUDED.pro_bowls,
                        super_bowl_wins = EXCLUDED.super_bowl_wins,
                        all_pro_first_team = EXCLUDED.all_pro_first_team,
                        all_pro_second_team = EXCLUDED.all_pro_second_team,
                        career_earnings_total = EXCLUDED.career_earnings_total,
                        career_earnings_source = EXCLUDED.career_earnings_source,
                        career_earnings_confidence = EXCLUDED.career_earnings_confidence,
                        current_contract_value = EXCLUDED.current_contract_value,
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
                        wikipedia_url = EXCLUDED.wikipedia_url,
                        data_collection_date = EXCLUDED.data_collection_date,
                        data_quality_score = EXCLUDED.data_quality_score,
                        data_sources_used = EXCLUDED.data_sources_used,
                        collection_method = EXCLUDED.collection_method
                    """
                    
                    conn.execute(text(insert_sql), db_data)
                
                conn.commit()
                logger.info(f"Successfully saved {len(players_data)} players to database")
                
        except Exception as e:
            logger.error(f"Error saving to database: {e}")
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
    
    def _safe_date(self, value) -> Optional[str]:
        """Safely convert value to date string."""
        if value is None or value == '':
            return None
        try:
            # If it's already a date string, return it
            if isinstance(value, str):
                return value
            return str(value)
        except:
            return None
    
    def run_complete_pipeline(self, team_name: str):
        """Run the complete data collection pipeline for a team."""
        logger.info(f"Starting complete NFL Gravity pipeline for {team_name}")
        
        try:
            # Collect comprehensive data
            players_data = self.collect_team_data(team_name)
            
            if not players_data:
                logger.warning(f"No data collected for {team_name}")
                return
            
            # Save to database
            self.save_to_database(players_data, team_name)
            
            # Generate summary report
            self.generate_summary_report(team_name)
            
            logger.info(f"Pipeline completed successfully for {team_name}")
            
        except Exception as e:
            logger.error(f"Pipeline failed for {team_name}: {e}")
            raise
    
    def generate_summary_report(self, team_name: str):
        """Generate a summary report of collected data."""
        logger.info("Generating summary report...")
        
        try:
            with self.engine.connect() as conn:
                # Get summary statistics
                summary_sql = """
                SELECT 
                    COUNT(*) as total_players,
                    AVG(data_quality_score) as avg_quality_score,
                    COUNT(CASE WHEN twitter_followers > 0 THEN 1 END) as players_with_twitter,
                    COUNT(CASE WHEN instagram_followers > 0 THEN 1 END) as players_with_instagram,
                    COUNT(CASE WHEN tiktok_followers > 0 THEN 1 END) as players_with_tiktok,
                    COUNT(CASE WHEN youtube_subscribers > 0 THEN 1 END) as players_with_youtube,
                    SUM(twitter_followers) as total_twitter_followers,
                    SUM(instagram_followers) as total_instagram_followers,
                    SUM(tiktok_followers) as total_tiktok_followers,
                    SUM(youtube_subscribers) as total_youtube_subscribers
                FROM nfl_players_comprehensive 
                WHERE current_team = :team_name
                """
                
                result = conn.execute(text(summary_sql), {'team_name': team_name}).fetchone()
                
                report = f"""
                
NFL Gravity Pipeline Summary Report
==================================
Team: {team_name}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Data Collection Summary:
- Total Players: {result.total_players}
- Average Data Quality Score: {result.avg_quality_score:.1f}%

Social Media Coverage:
- Players with Twitter: {result.players_with_twitter}
- Players with Instagram: {result.players_with_instagram}
- Players with TikTok: {result.players_with_tiktok}
- Players with YouTube: {result.players_with_youtube}

Social Media Totals:
- Total Twitter Followers: {result.total_twitter_followers:,}
- Total Instagram Followers: {result.total_instagram_followers:,}
- Total TikTok Followers: {result.total_tiktok_followers:,}
- Total YouTube Subscribers: {result.total_youtube_subscribers:,}

==================================
                """
                
                logger.info(report)
                
                # Save report to file
                with open(f'nfl_gravity_report_{team_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt', 'w') as f:
                    f.write(report)
                
        except Exception as e:
            logger.error(f"Error generating summary report: {e}")

def main():
    """Main function to run the pipeline."""
    if len(sys.argv) > 1:
        team_name = sys.argv[1]
    else:
        team_name = "49ers"  # Default team
    
    logger.info(f"Starting NFL Gravity Database Pipeline for {team_name}")
    
    try:
        pipeline = NFLGravityDatabasePipeline()
        pipeline.run_complete_pipeline(team_name)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()