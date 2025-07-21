#!/usr/bin/env python3
"""
Comprehensive All Teams Scraper
Scrapes all 32 NFL teams with full social media data and database integration
"""

import os
import time
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any
import logging

# Import our existing modules
from real_data_collector import RealDataCollector
from enhanced_comprehensive_collector import EnhancedComprehensiveCollector
from enhanced_db_manager import EnhancedDatabaseManager
from gravity_score_system import GravityScoreCalculator
from enhanced_nfl_scraper import EnhancedNFLScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/comprehensive_scraping.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ComprehensiveAllTeamsScraper:
    """
    Comprehensive scraper for all NFL teams with database integration
    """
    
    def __init__(self):
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
        
        self.scrapers = {
            'standard': EnhancedNFLScraper(),
            'comprehensive': EnhancedComprehensiveCollector(),
            'real_data': RealDataCollector()
        }
        
        self.gravity_calculator = GravityScoreCalculator()
        self.db_manager = EnhancedDatabaseManager()
        
        # Statistics tracking
        self.stats = {
            'teams_processed': 0,
            'players_scraped': 0,
            'players_with_social_media': 0,
            'database_records_created': 0,
            'database_records_updated': 0,
            'start_time': None,
            'errors': []
        }
    
    def scrape_team_comprehensive(self, team: str) -> List[Dict[str, Any]]:
        """
        Scrape a single team with comprehensive data collection
        """
        logger.info(f"🏈 Starting comprehensive scraping for {team.upper()}")
        
        try:
            # Step 1: Get basic roster from enhanced NFL scraper
            basic_players = self.scrapers['standard'].extract_complete_team_roster(team)
            logger.info(f"   ✓ Found {len(basic_players)} players in {team} roster")
            
            # Step 2: Enhance each player with comprehensive data
            enhanced_players = []
            
            for i, player in enumerate(basic_players, 1):
                logger.info(f"   📊 Processing player {i}/{len(basic_players)}: {player.get('name', 'Unknown')}")
                
                try:
                    # Use enhanced comprehensive collector for maximum data
                    enhanced_data = self.scrapers['comprehensive'].collect_comprehensive_data(
                        player_name=player.get('name', ''),
                        team=team,
                        position=player.get('position', '')
                    )
                    
                    # Merge base player data
                    for key, value in player.items():
                        if key not in enhanced_data or enhanced_data[key] is None:
                            enhanced_data[key] = value
                    
                    # Ensure we have all 70+ fields by merging with real data collector
                    if len([k for k, v in enhanced_data.items() if v is not None and v != ""]) < 35:
                        logger.info(f"     🔄 Enhancing with additional sources for {player.get('name')}")
                        additional_data = self.scrapers['real_data'].collect_player_data(
                            player_name=player.get('name', ''),
                            team=team,
                            position=player.get('position', ''),
                            jersey_number=player.get('jersey_number', ''),
                            base_data=enhanced_data
                        )
                        # Merge the data, preferring non-empty values
                        for key, value in additional_data.items():
                            if value is not None and value != "" and (key not in enhanced_data or enhanced_data[key] in [None, ""]):
                                enhanced_data[key] = value
                    
                    # Calculate gravity score
                    gravity_components = self.gravity_calculator.calculate_total_gravity(enhanced_data)
                    enhanced_data.update({
                        'brand_power': gravity_components.brand_power,
                        'proof': gravity_components.proof,
                        'proximity': gravity_components.proximity,
                        'velocity': gravity_components.velocity,
                        'risk': gravity_components.risk,
                        'total_gravity': gravity_components.total_gravity
                    })
                    
                    enhanced_players.append(enhanced_data)
                    
                    # Track social media success
                    if any([enhanced_data.get('twitter_handle'), enhanced_data.get('instagram_handle'), 
                           enhanced_data.get('tiktok_handle'), enhanced_data.get('youtube_handle')]):
                        self.stats['players_with_social_media'] += 1
                    
                    self.stats['players_scraped'] += 1
                    
                    # Small delay to be respectful
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"   ❌ Error processing {player.get('name')}: {str(e)}")
                    self.stats['errors'].append(f"{team} - {player.get('name')}: {str(e)}")
                    # Still add basic player data
                    enhanced_players.append(player)
            
            logger.info(f"   ✅ Completed {team}: {len(enhanced_players)} players enhanced")
            return enhanced_players
            
        except Exception as e:
            logger.error(f"❌ Error scraping team {team}: {str(e)}")
            self.stats['errors'].append(f"Team {team}: {str(e)}")
            return []
    
    def save_to_database(self, players_data: List[Dict[str, Any]], team: str) -> None:
        """
        Save or update player data in the database
        """
        logger.info(f"💾 Saving {len(players_data)} players to database for {team}")
        
        try:
            for player in players_data:
                try:
                    # Check if player exists
                    existing_player = self.db_manager.get_player_by_name_team(
                        player.get('name', ''), 
                        team
                    )
                    
                    if existing_player:
                        # Update existing player with comprehensive data
                        success = self.db_manager.update_player_by_name_team(player)
                        if success:
                            self.stats['database_records_updated'] += 1
                            logger.info(f"   🔄 Updated: {player.get('name')}")
                    else:
                        # Create new player with comprehensive data
                        success = self.db_manager.insert_player(player)
                        if success:
                            self.stats['database_records_created'] += 1
                            logger.info(f"   ➕ Created: {player.get('name')}")
                        
                except Exception as e:
                    logger.error(f"   ❌ Database error for {player.get('name')}: {str(e)}")
                    self.stats['errors'].append(f"DB {team} - {player.get('name')}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"❌ Database connection error for team {team}: {str(e)}")
            self.stats['errors'].append(f"DB Team {team}: {str(e)}")
    
    def save_to_csv(self, all_players_data: List[Dict[str, Any]]) -> str:
        """
        Save all collected data to CSV file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/comprehensive_all_teams_{timestamp}.csv"
        
        try:
            df = pd.DataFrame(all_players_data)
            df.to_csv(filename, index=False)
            logger.info(f"💾 Saved {len(all_players_data)} players to {filename}")
            return filename
        except Exception as e:
            logger.error(f"❌ Error saving CSV: {str(e)}")
            return ""
    
    def scrape_all_teams(self) -> Dict[str, Any]:
        """
        Main method to scrape all NFL teams comprehensively
        """
        logger.info("🚀 Starting comprehensive scraping of ALL 32 NFL TEAMS")
        logger.info("=" * 80)
        
        self.stats['start_time'] = datetime.now()
        all_players_data = []
        
        # Initialize database
        try:
            self.db_manager.create_tables()
            logger.info("✅ Database tables initialized")
        except Exception as e:
            logger.error(f"❌ Database initialization error: {str(e)}")
        
        # Process each team
        for team_index, team in enumerate(self.nfl_teams, 1):
            logger.info(f"\n🏈 TEAM {team_index}/32: {team.upper()}")
            logger.info("-" * 50)
            
            # Scrape team data
            team_players = self.scrape_team_comprehensive(team)
            
            if team_players:
                # Save to database
                self.save_to_database(team_players, team)
                
                # Add to master list
                all_players_data.extend(team_players)
                
                self.stats['teams_processed'] += 1
                
                logger.info(f"✅ Team {team} completed: {len(team_players)} players")
            else:
                logger.warning(f"⚠️  No data collected for team {team}")
            
            # Progress update
            progress = (team_index / len(self.nfl_teams)) * 100
            logger.info(f"📈 Overall Progress: {progress:.1f}% ({team_index}/{len(self.nfl_teams)} teams)")
            
            # Small delay between teams
            time.sleep(2)
        
        # Save comprehensive CSV
        csv_file = self.save_to_csv(all_players_data)
        
        # Final statistics
        end_time = datetime.now()
        duration = end_time - self.stats['start_time']
        
        final_stats = {
            'total_teams': len(self.nfl_teams),
            'teams_processed': self.stats['teams_processed'],
            'total_players': len(all_players_data),
            'players_with_social_media': self.stats['players_with_social_media'],
            'database_records_created': self.stats['database_records_created'],
            'database_records_updated': self.stats['database_records_updated'],
            'total_errors': len(self.stats['errors']),
            'duration_minutes': duration.total_seconds() / 60,
            'csv_file': csv_file,
            'completion_rate': (self.stats['teams_processed'] / len(self.nfl_teams)) * 100
        }
        
        logger.info("\n🎉 COMPREHENSIVE SCRAPING COMPLETED!")
        logger.info("=" * 80)
        logger.info(f"📊 Final Statistics:")
        logger.info(f"   Teams Processed: {final_stats['teams_processed']}/{final_stats['total_teams']}")
        logger.info(f"   Total Players: {final_stats['total_players']}")
        logger.info(f"   Players with Social Media: {final_stats['players_with_social_media']}")
        logger.info(f"   Database Records Created: {final_stats['database_records_created']}")
        logger.info(f"   Database Records Updated: {final_stats['database_records_updated']}")
        logger.info(f"   Total Errors: {final_stats['total_errors']}")
        logger.info(f"   Duration: {final_stats['duration_minutes']:.1f} minutes")
        logger.info(f"   Completion Rate: {final_stats['completion_rate']:.1f}%")
        logger.info(f"   CSV File: {final_stats['csv_file']}")
        
        return final_stats

def main():
    """
    Main execution function
    """
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    
    # Initialize and run scraper
    scraper = ComprehensiveAllTeamsScraper()
    results = scraper.scrape_all_teams()
    
    return results

if __name__ == "__main__":
    main()