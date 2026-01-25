#!/usr/bin/env python3
"""
Automated Handle Finder for NFL Players
========================================
Uses DuckDuckGo + Wikipedia to find social media handles for players 101-200
"""

import pandas as pd
import time
import logging
from tqdm import tqdm
from typing import Dict, Optional
import requests
from bs4 import BeautifulSoup

from gravity.free_apis import DuckDuckGoSocialFinder, get_free_data_collector
from gravity.contract_collector import ContractCollector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutomatedHandleFinder:
    """Automated social handle finder with validation"""
    
    def __init__(self):
        self.ddg_finder = DuckDuckGoSocialFinder()
        self.social_api = get_free_data_collector().social
        self.contract_collector = ContractCollector()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def find_player_handles(self, player_name: str, team: str = None) -> Dict:
        """
        Find all social handles for a player with validation
        
        Returns dict with handles and follower counts
        """
        result = {
            'instagram_handle': None,
            'instagram_followers': None,
            'instagram_verified': False,
            'twitter_handle': None,
            'twitter_followers': None,
            'twitter_verified': False,
            'contract_value': None,
            'free_agency_year': None
        }
        
        try:
            # Find Instagram
            ig_handle = self.ddg_finder.find_social_handle(player_name, 'instagram')
            if ig_handle:
                try:
                    ig_stats = self.social_api.get_instagram_stats(ig_handle)
                    if ig_stats.get('followers', 0) > 50000:  # Minimum 50K threshold
                        result['instagram_handle'] = ig_handle
                        result['instagram_followers'] = ig_stats.get('followers', 0)
                        result['instagram_verified'] = ig_stats.get('verified', False)
                        logger.info(f"✅ {player_name}: Instagram @{ig_handle} ({ig_stats.get('followers', 0):,} followers)")
                except Exception as e:
                    logger.debug(f"Instagram stats failed for {ig_handle}: {e}")
            
            time.sleep(0.5)  # Rate limit
            
            # Find Twitter
            tw_handle = self.ddg_finder.find_social_handle(player_name, 'twitter')
            if tw_handle:
                try:
                    tw_stats = self.social_api.get_twitter_stats(tw_handle)
                    if tw_stats.get('followers', 0) > 50000:  # Minimum 50K threshold
                        result['twitter_handle'] = tw_handle
                        result['twitter_followers'] = tw_stats.get('followers', 0)
                        result['twitter_verified'] = tw_stats.get('verified', False)
                        logger.info(f"✅ {player_name}: Twitter @{tw_handle} ({tw_stats.get('followers', 0):,} followers)")
                except Exception as e:
                    logger.debug(f"Twitter stats failed for {tw_handle}: {e}")
            
            time.sleep(0.5)  # Rate limit
            
            # Get contract data if team provided
            if team:
                try:
                    contract_data = self.contract_collector.collect_contract_data(
                        player_name=player_name,
                        team=team,
                        sport='nfl'
                    )
                    if contract_data:
                        result['contract_value'] = contract_data.get('contract_value')
                        result['free_agency_year'] = contract_data.get('free_agency_year')
                except Exception as e:
                    logger.debug(f"Contract collection failed for {player_name}: {e}")
        
        except Exception as e:
            logger.error(f"Error finding handles for {player_name}: {e}")
        
        return result
    
    def find_from_wikipedia(self, player_name: str) -> Optional[str]:
        """Fallback: Try to find Instagram handle from Wikipedia infobox"""
        try:
            # Clean name for Wikipedia URL
            wiki_name = player_name.replace(' ', '_')
            url = f"https://en.wikipedia.org/wiki/{wiki_name}"
            
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for Instagram in infobox
                infobox = soup.find('table', class_='infobox')
                if infobox:
                    for row in infobox.find_all('tr'):
                        header = row.find('th')
                        if header and 'instagram' in header.get_text().lower():
                            link = row.find('a', href=lambda x: x and 'instagram.com' in x)
                            if link:
                                handle = link.get('href', '').split('/')[-1]
                                return handle.replace('@', '')
        except Exception as e:
            logger.debug(f"Wikipedia lookup failed for {player_name}: {e}")
        
        return None


def expand_nfl_database(input_csv: str, output_csv: str, start_idx: int = 50, end_idx: int = 200):
    """
    Expand NFL player database from start_idx to end_idx using automated finding
    
    Args:
        input_csv: Existing database (e.g., nfl_top_players_social.csv)
        output_csv: Output file for expanded database
        start_idx: Starting index (50 = continue from existing 50)
        end_idx: Ending index (200 = top 200 total)
    """
    print(f"\n{'='*100}")
    print(f"🚀 EXPANDING NFL PLAYER DATABASE: Players {start_idx+1} to {end_idx}")
    print(f"{'='*100}\n")
    
    # Load existing data
    existing_df = pd.read_csv(input_csv)
    print(f"📂 Loaded {len(existing_df)} existing players")
    
    # Load full NFL roster to get players 51-200
    try:
        full_roster = pd.read_csv('scrapes/NFL/20251209_113136/nfl_players_20251209_123629.csv')
        print(f"📂 Loaded {len(full_roster)} total NFL players")
        
        # Get top players by stats (career touchdowns, yards, etc.)
        # Prioritize QBs, WRs, RBs, TEs, Edge, CB
        priority_positions = ['QB', 'WR', 'RB', 'TE', 'EDGE', 'CB', 'LB', 'S', 'DT', 'DE']
        
        # Calculate priority score
        full_roster['_priority'] = 0
        if 'career_touchdowns' in full_roster.columns:
            full_roster['_priority'] += full_roster['career_touchdowns'].fillna(0) * 10
        if 'career_yards' in full_roster.columns:
            full_roster['_priority'] += full_roster['career_yards'].fillna(0) / 100
        if 'pro_bowls' in full_roster.columns:
            full_roster['_priority'] += full_roster['pro_bowls'].fillna(0) * 100
        
        # Boost priority for key positions
        for pos in priority_positions:
            mask = full_roster['position'].str.contains(pos, case=False, na=False)
            full_roster.loc[mask, '_priority'] *= 1.5
        
        # Sort and get players not already in database
        full_roster = full_roster.sort_values('_priority', ascending=False)
        existing_names = set(existing_df['player_name'].str.lower())
        new_players = full_roster[~full_roster['player_name'].str.lower().isin(existing_names)]
        
        # Get players 51-200 (need 150 more)
        players_to_process = new_players.head(end_idx - start_idx)
        print(f"🎯 Found {len(players_to_process)} new players to process\n")
        
    except FileNotFoundError:
        print("⚠️  Full roster not found. Will use manual list.")
        players_to_process = pd.DataFrame()  # Empty, will need manual entry
    
    # Initialize finder
    finder = AutomatedHandleFinder()
    
    # Process players
    new_entries = []
    
    for idx, row in tqdm(players_to_process.iterrows(), total=len(players_to_process), desc="Finding handles"):
        player_name = row['player_name']
        team = row.get('team', '')
        
        logger.info(f"\n🔍 Processing: {player_name} ({team})")
        
        result = finder.find_player_handles(player_name, team)
        
        # Only add if we found at least one handle or contract
        if (result['instagram_handle'] or result['twitter_handle'] or result['contract_value']):
            entry = {
                'player_name': player_name,
                'instagram_handle': result['instagram_handle'],
                'instagram_followers': result['instagram_followers'],
                'instagram_verified': result['instagram_verified'],
                'twitter_handle': result['twitter_handle'],
                'twitter_followers': result['twitter_followers'],
                'twitter_verified': result['twitter_verified'],
                'contract_value': result['contract_value'],
                'free_agency_year': result['free_agency_year']
            }
            new_entries.append(entry)
            logger.info(f"✅ Added: {player_name}")
        else:
            logger.warning(f"⚠️  No handles found for {player_name}")
        
        time.sleep(1)  # Rate limit between players
    
    # Combine with existing
    if new_entries:
        new_df = pd.DataFrame(new_entries)
        expanded_df = pd.concat([existing_df, new_df], ignore_index=True)
        
        # Save
        expanded_df.to_csv(output_csv, index=False)
        print(f"\n💾 Saved {len(expanded_df)} players to {output_csv}")
        print(f"   - Existing: {len(existing_df)}")
        print(f"   - New: {len(new_df)}")
    else:
        print("\n⚠️  No new entries found. Output file not created.")
    
    return len(new_entries)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python automated_handle_finder.py input.csv output.csv [start_idx] [end_idx]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    start = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    end = int(sys.argv[4]) if len(sys.argv) > 4 else 200
    
    expand_nfl_database(input_file, output_file, start, end)

