#!/usr/bin/env python3
"""
Collect Social Data for All Athletes
====================================
Automated collection of social media handles and follower counts for all players
across NFL, NBA, and CFB using hybrid approach (DuckDuckGo + manual database)
"""

import pandas as pd
import numpy as np
import time
import logging
from tqdm import tqdm
from pathlib import Path
from typing import Dict, Optional
import requests
from bs4 import BeautifulSoup

from gravity.free_apis import DuckDuckGoSocialFinder, get_free_data_collector
from gravity.contract_collector import ContractCollector

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ComprehensiveSocialCollector:
    """Collect social data for all athletes with rate limiting and error handling"""
    
    def __init__(self):
        self.ddg_finder = DuckDuckGoSocialFinder()
        self.social_api = get_free_data_collector().social
        self.contract_collector = ContractCollector()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.stats = {
            'total_processed': 0,
            'instagram_found': 0,
            'twitter_found': 0,
            'contract_found': 0,
            'errors': 0
        }
    
    def find_player_social_data(self, player_name: str, team: str = None, 
                                 sport: str = 'nfl') -> Dict:
        """
        Find all social handles and contract data for a player
        
        Returns dict with handles, followers, and contract info
        """
        result = {
            'instagram_handle': None,
            'instagram_followers': None,
            'instagram_verified': False,
            'twitter_handle': None,
            'twitter_followers': None,
            'twitter_verified': False,
            'tiktok_handle': None,
            'tiktok_followers': None,
            'contract_value': None,
            'free_agency_year': None
        }
        
        try:
            # Find Instagram
            ig_handle = self.ddg_finder.find_social_handle(player_name, 'instagram')
            if ig_handle:
                try:
                    time.sleep(0.5)  # Rate limit
                    ig_stats = self.social_api.get_instagram_stats(ig_handle)
                    if ig_stats.get('followers', 0) > 0:
                        result['instagram_handle'] = ig_handle
                        result['instagram_followers'] = ig_stats.get('followers', 0)
                        result['instagram_verified'] = ig_stats.get('verified', False)
                        self.stats['instagram_found'] += 1
                except Exception as e:
                    logger.debug(f"Instagram stats failed for {ig_handle}: {e}")
            
            # Find Twitter
            tw_handle = self.ddg_finder.find_social_handle(player_name, 'twitter')
            if tw_handle:
                try:
                    time.sleep(0.5)  # Rate limit
                    tw_stats = self.social_api.get_twitter_stats(tw_handle)
                    if tw_stats.get('followers', 0) > 0:
                        result['twitter_handle'] = tw_handle
                        result['twitter_followers'] = tw_stats.get('followers', 0)
                        result['twitter_verified'] = tw_stats.get('verified', False)
                        self.stats['twitter_found'] += 1
                except Exception as e:
                    logger.debug(f"Twitter stats failed for {tw_handle}: {e}")
            
            # Find TikTok
            tt_handle = self.ddg_finder.find_social_handle(player_name, 'tiktok')
            if tt_handle:
                try:
                    time.sleep(0.5)  # Rate limit
                    tt_stats = self.social_api.get_tiktok_stats(tt_handle)
                    if tt_stats.get('followers', 0) > 0:
                        result['tiktok_handle'] = tt_handle
                        result['tiktok_followers'] = tt_stats.get('followers', 0)
                except Exception as e:
                    logger.debug(f"TikTok stats failed for {tt_handle}: {e}")
            
            # Get contract data if team provided
            if team:
                try:
                    time.sleep(1)  # Rate limit for contract scraping
                    contract_data = self.contract_collector.collect_contract_data(
                        player_name=player_name,
                        team=team,
                        sport=sport
                    )
                    if contract_data:
                        result['contract_value'] = contract_data.get('contract_value')
                        result['free_agency_year'] = contract_data.get('free_agency_year')
                        self.stats['contract_found'] += 1
                except Exception as e:
                    logger.debug(f"Contract collection failed for {player_name}: {e}")
        
        except Exception as e:
            logger.error(f"Error finding social data for {player_name}: {e}")
            self.stats['errors'] += 1
        
        self.stats['total_processed'] += 1
        return result
    
    def process_roster(self, df: pd.DataFrame, sport: str = 'nfl', 
                      max_players: Optional[int] = None, 
                      start_from: int = 0) -> pd.DataFrame:
        """
        Process entire roster and add social data
        
        Args:
            df: DataFrame with player data
            sport: 'nfl', 'nba', or 'cfb'
            max_players: Limit number of players to process (None = all)
            start_from: Start from this index (for resuming)
        """
        logger.info(f"\n{'='*100}")
        logger.info(f"🚀 COLLECTING SOCIAL DATA FOR {sport.upper()} PLAYERS")
        logger.info(f"{'='*100}\n")
        logger.info(f"   Total players: {len(df)}")
        logger.info(f"   Starting from index: {start_from}")
        if max_players:
            logger.info(f"   Processing up to: {max_players} players")
        
        # Initialize social columns if they don't exist
        for col in ['instagram_handle', 'instagram_followers', 'instagram_verified',
                   'twitter_handle', 'twitter_followers', 'twitter_verified',
                   'tiktok_handle', 'tiktok_followers',
                   'contract_value', 'free_agency_year']:
            if col not in df.columns:
                df[col] = None
        
        # Determine which players to process
        players_to_process = df.iloc[start_from:]
        if max_players:
            players_to_process = players_to_process.head(max_players)
        
        logger.info(f"   Processing {len(players_to_process)} players\n")
        
        # Process each player
        for idx, row in tqdm(players_to_process.iterrows(), total=len(players_to_process), 
                            desc="Collecting social data"):
            player_name = row.get('player_name', '')
            team = row.get('team', '')
            
            # Skip if already has social data
            if pd.notna(row.get('instagram_followers')) or pd.notna(row.get('twitter_followers')):
                continue
            
            # Collect social data
            social_data = self.find_player_social_data(player_name, team, sport)
            
            # Update dataframe
            for key, value in social_data.items():
                if value is not None:
                    df.at[idx, key] = value
            
            # Progress update every 50 players
            if self.stats['total_processed'] % 50 == 0:
                logger.info(f"   Progress: {self.stats['total_processed']} processed | "
                          f"Instagram: {self.stats['instagram_found']} | "
                          f"Twitter: {self.stats['twitter_found']} | "
                          f"Contract: {self.stats['contract_found']}")
            
            time.sleep(1)  # Rate limit between players
        
        # Final stats
        logger.info(f"\n{'='*100}")
        logger.info(f"✅ COLLECTION COMPLETE")
        logger.info(f"{'='*100}\n")
        logger.info(f"📊 Final Statistics:")
        logger.info(f"   Total Processed: {self.stats['total_processed']}")
        logger.info(f"   Instagram Found: {self.stats['instagram_found']} ({self.stats['instagram_found']/self.stats['total_processed']*100:.1f}%)")
        logger.info(f"   Twitter Found: {self.stats['twitter_found']} ({self.stats['twitter_found']/self.stats['total_processed']*100:.1f}%)")
        logger.info(f"   Contract Found: {self.stats['contract_found']} ({self.stats['contract_found']/self.stats['total_processed']*100:.1f}%)")
        logger.info(f"   Errors: {self.stats['errors']}")
        
        return df


def collect_all_social_data(sport: str, input_file: str, output_file: str,
                            max_players: Optional[int] = None,
                            start_from: int = 0):
    """
    Main function to collect social data for all athletes
    
    Args:
        sport: 'nfl', 'nba', or 'cfb'
        input_file: Input CSV with player data
        output_file: Output CSV with social data added
        max_players: Limit number of players (None = all)
        start_from: Start from this index (for resuming)
    """
    # Load data
    logger.info(f"📂 Loading {input_file}...")
    df = pd.read_csv(input_file)
    logger.info(f"   Loaded {len(df)} players")
    
    # Collect social data
    collector = ComprehensiveSocialCollector()
    df_enriched = collector.process_roster(df, sport=sport, max_players=max_players, 
                                           start_from=start_from)
    
    # Save
    logger.info(f"\n💾 Saving to {output_file}...")
    df_enriched.to_csv(output_file, index=False)
    logger.info(f"✅ Saved {len(df_enriched)} players with social data")
    
    # Summary
    ig_count = df_enriched['instagram_followers'].notna().sum()
    tw_count = df_enriched['twitter_followers'].notna().sum()
    contract_count = df_enriched['contract_value'].notna().sum()
    
    logger.info(f"\n📊 Final Data Quality:")
    logger.info(f"   Players with Instagram: {ig_count} ({ig_count/len(df_enriched)*100:.1f}%)")
    logger.info(f"   Players with Twitter: {tw_count} ({tw_count/len(df_enriched)*100:.1f}%)")
    logger.info(f"   Players with Contract: {contract_count} ({contract_count/len(df_enriched)*100:.1f}%)")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 4:
        print("Usage: python collect_all_social_data.py sport input.csv output.csv [max_players] [start_from]")
        print("Example: python collect_all_social_data.py nfl scrapes/NFL/.../nfl_players.csv nfl_with_social.csv")
        sys.exit(1)
    
    sport = sys.argv[1]
    input_file = sys.argv[2]
    output_file = sys.argv[3]
    max_players = int(sys.argv[4]) if len(sys.argv) > 4 else None
    start_from = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    
    collect_all_social_data(sport, input_file, output_file, max_players, start_from)

