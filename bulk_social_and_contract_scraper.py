#!/usr/bin/env python3
"""
Bulk Social Media & Contract Data Scraper
==========================================

Adds social media follower counts and contract data to existing player CSV.
Works on already-scraped data without re-scraping stats/awards.

Usage:
    python bulk_social_and_contract_scraper.py input.csv output.csv

Author: Gravity Score Team
"""

import pandas as pd
import logging
from pathlib import Path
from tqdm import tqdm
import sys
from datetime import datetime
import time

# Import collectors
from gravity.free_apis import get_free_data_collector
from gravity.contract_collector import ContractCollector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def collect_social_data_for_player(player_name: str, free_collector) -> dict:
    """
    Collect social media data for a single player
    
    Returns dict with instagram_followers, twitter_followers, etc.
    """
    result = {
        'instagram_followers': None,
        'instagram_verified': False,
        'instagram_handle': None,
        'twitter_followers': None,
        'twitter_verified': False,
        'twitter_handle': None,
        'tiktok_followers': None,
        'tiktok_handle': None,
    }
    
    try:
        # Find handles first
        handles = free_collector.ddg_finder.find_all_social_handles(player_name)
        
        # Get Instagram stats
        ig_handle = handles.get('instagram')
        if not ig_handle:
            # Try common patterns
            ig_handle = player_name.lower().replace(' ', '')
        
        if ig_handle:
            ig_stats = free_collector.social.get_instagram_stats(ig_handle)
            if ig_stats.get('followers', 0) > 0:
                result['instagram_followers'] = ig_stats['followers']
                result['instagram_verified'] = ig_stats.get('verified', False)
                result['instagram_handle'] = f"@{ig_handle}"
        
        # Get Twitter stats
        tw_handle = handles.get('twitter')
        if not tw_handle:
            # Try common patterns
            tw_handle = player_name.replace(' ', '')
        
        if tw_handle:
            tw_stats = free_collector.social.get_twitter_stats(tw_handle)
            if tw_stats.get('followers', 0) > 0:
                result['twitter_followers'] = tw_stats['followers']
                result['twitter_verified'] = tw_stats.get('verified', False)
                result['twitter_handle'] = f"@{tw_handle}"
        
        # Get TikTok stats
        tt_handle = handles.get('tiktok')
        if tt_handle:
            tt_stats = free_collector.social.get_tiktok_stats(tt_handle)
            if tt_stats.get('followers', 0) > 0:
                result['tiktok_followers'] = tt_stats['followers']
                result['tiktok_handle'] = f"@{tt_handle}"
        
        # Rate limiting
        time.sleep(0.2)  # 5 requests per second max
        
    except Exception as e:
        logger.debug(f"Social collection failed for {player_name}: {e}")
    
    return result


def collect_contract_data_for_player(player_name: str, team: str, contract_collector) -> dict:
    """
    Collect contract data for a single player
    
    Returns dict with contract_value, current_contract_length, etc.
    """
    result = {
        'contract_value': None,
        'current_contract_length': None,
        'guaranteed_money': None,
    }
    
    try:
        contract_data = contract_collector.collect_contract_data(
            player_name=player_name,
            team=team,
            sport='nfl'
        )
        
        if contract_data:
            result['contract_value'] = contract_data.get('contract_value')
            result['current_contract_length'] = contract_data.get('contract_years')
            result['guaranteed_money'] = contract_data.get('guaranteed_money')
        
        # Rate limiting
        time.sleep(0.5)  # Be nice to Spotrac/OTC
        
    except Exception as e:
        logger.debug(f"Contract collection failed for {player_name}: {e}")
    
    return result


def main():
    if len(sys.argv) != 3:
        print("Usage: python bulk_social_and_contract_scraper.py input.csv output.csv")
        print("\nExample:")
        print("  python bulk_social_and_contract_scraper.py \\")
        print("    scrapes/NFL/20251209_113136/nfl_players_20251209_123629.csv \\")
        print("    nfl_players_WITH_SOCIAL_AND_CONTRACTS.csv")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    print("\n" + "="*100)
    print("🚀 BULK SOCIAL MEDIA & CONTRACT DATA COLLECTION")
    print("="*100)
    print(f"\nInput:  {input_file}")
    print(f"Output: {output_file}")
    
    # Load existing data
    print(f"\n📂 Loading existing player data...")
    df = pd.read_csv(input_file)
    print(f"   Loaded {len(df)} players")
    
    # Initialize collectors
    print(f"\n🔧 Initializing collectors...")
    free_collector = get_free_data_collector()
    contract_collector = ContractCollector()
    print(f"   ✅ Free APIs collector ready (Instagram, Twitter, TikTok)")
    print(f"   ✅ Contract collector ready (Spotrac, OverTheCap)")
    
    # Prepare new columns
    social_columns = [
        'instagram_followers', 'instagram_verified', 'instagram_handle',
        'twitter_followers', 'twitter_verified', 'twitter_handle',
        'tiktok_followers', 'tiktok_handle'
    ]
    contract_columns = ['contract_value', 'current_contract_length', 'guaranteed_money']
    
    for col in social_columns + contract_columns:
        if col not in df.columns:
            df[col] = None
    
    # Collect data
    print(f"\n📊 Collecting social media & contract data...")
    print(f"   This will take ~30-45 minutes for {len(df)} players")
    print(f"   Rate limited to avoid blocking")
    
    social_success = 0
    contract_success = 0
    
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Processing players"):
        player_name = row['player_name']
        team = row.get('team', '')
        
        # Collect social data
        social_data = collect_social_data_for_player(player_name, free_collector)
        for key, value in social_data.items():
            if value is not None:
                df.at[idx, key] = value
        
        if social_data['instagram_followers'] or social_data['twitter_followers']:
            social_success += 1
        
        # Collect contract data
        if team:
            contract_data = collect_contract_data_for_player(player_name, team, contract_collector)
            for key, value in contract_data.items():
                if value is not None:
                    df.at[idx, key] = value
            
            if contract_data['contract_value']:
                contract_success += 1
    
    # Save results
    print(f"\n💾 Saving results...")
    df.to_csv(output_file, index=False)
    
    # Summary
    print("\n" + "="*100)
    print("✅ COLLECTION COMPLETE!")
    print("="*100)
    print(f"\n📊 Results:")
    print(f"   Total Players: {len(df)}")
    print(f"   Social Media Success: {social_success}/{len(df)} ({social_success/len(df)*100:.1f}%)")
    print(f"   Contract Success: {contract_success}/{len(df)} ({contract_success/len(df)*100:.1f}%)")
    
    # Show sample data for top players
    print(f"\n🏆 Sample Data (Top 10 players with social data):")
    sample = df[df['instagram_followers'].notna() | df['twitter_followers'].notna()].head(10)
    for _, row in sample.iterrows():
        print(f"\n   {row['player_name']} ({row.get('position', 'N/A')}) - {row.get('team', 'N/A')}")
        if row.get('instagram_followers'):
            print(f"     📸 Instagram: {int(row['instagram_followers']):,} followers")
        if row.get('twitter_followers'):
            print(f"     🐦 Twitter: {int(row['twitter_followers']):,} followers")
        if row.get('contract_value'):
            print(f"     💰 Contract: ${int(row['contract_value']):,}")
    
    print(f"\n💡 Next Steps:")
    print(f"   1. Run pipeline on new CSV:")
    print(f"      python batch_pipeline.py {output_file} final_scores/NFL_COMPLETE.csv")
    print(f"\n   2. Check updated gravity scores - social & market components should now be non-zero!")
    print("\n" + "="*100)


if __name__ == '__main__':
    main()

