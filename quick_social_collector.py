#!/usr/bin/env python3
"""
Quick Social & Contract Data Collector
========================================
Efficiently adds social media and contract data to existing NFL CSV.
Optimized for speed with parallel processing.
"""

import pandas as pd
import logging
from pathlib import Path
from tqdm import tqdm
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from gravity.free_apis import get_free_data_collector
from gravity.contract_collector import ContractCollector

logging.basicConfig(level=logging.WARNING)  # Reduce noise
logger = logging.getLogger(__name__)


def collect_player_data(args):
    """Collect social + contract data for one player"""
    idx, player_name, team, free_collector, contract_collector = args
    
    result = {
        'idx': idx,
        'instagram_followers': None,
        'instagram_verified': False,
        'instagram_handle': None,
        'twitter_followers': None,
        'twitter_verified': False,
        'twitter_handle': None,
        'tiktok_followers': None,
        'tiktok_handle': None,
        'contract_value': None,
        'current_contract_length': None,
        'guaranteed_money': None,
    }
    
    try:
        # Collect social data
        handles = free_collector.ddg_finder.find_all_social_handles(player_name)
        
        # Instagram
        ig_handle = handles.get('instagram') or player_name.lower().replace(' ', '')
        ig_stats = free_collector.social.get_instagram_stats(ig_handle)
        if ig_stats.get('followers', 0) > 0:
            result['instagram_followers'] = ig_stats['followers']
            result['instagram_verified'] = ig_stats.get('verified', False)
            result['instagram_handle'] = f"@{ig_handle}"
        
        # Twitter
        tw_handle = handles.get('twitter') or player_name.replace(' ', '')
        tw_stats = free_collector.social.get_twitter_stats(tw_handle)
        if tw_stats.get('followers', 0) > 0:
            result['twitter_followers'] = tw_stats['followers']
            result['twitter_verified'] = tw_stats.get('verified', False)
            result['twitter_handle'] = f"@{tw_handle}"
        
        # TikTok
        tt_handle = handles.get('tiktok')
        if tt_handle:
            tt_stats = free_collector.social.get_tiktok_stats(tt_handle)
            if tt_stats.get('followers', 0) > 0:
                result['tiktok_followers'] = tt_stats['followers']
                result['tiktok_handle'] = f"@{tt_handle}"
        
        # Contract data
        if team:
            contract_data = contract_collector.collect_contract_data(
                player_name=player_name,
                team=team,
                sport='nfl'
            )
            
            if contract_data:
                result['contract_value'] = contract_data.get('contract_value')
                result['current_contract_length'] = contract_data.get('contract_years')
                result['guaranteed_money'] = contract_data.get('guaranteed_money')
        
        time.sleep(0.1)  # Rate limiting
        
    except Exception as e:
        logger.debug(f"Collection failed for {player_name}: {e}")
    
    return result


def main():
    if len(sys.argv) < 3:
        print("Usage: python quick_social_collector.py input.csv output.csv [max_workers]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    max_workers = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    
    print(f"\n{'='*100}")
    print(f"🚀 QUICK SOCIAL & CONTRACT COLLECTOR")
    print(f"{'='*100}")
    print(f"\nInput:  {input_file}")
    print(f"Output: {output_file}")
    print(f"Workers: {max_workers}")
    
    # Load data
    print(f"\n📂 Loading players...")
    df = pd.read_csv(input_file)
    print(f"   Loaded {len(df)} players")
    
    # Initialize collectors (one per worker)
    print(f"\n🔧 Initializing collectors...")
    
    # Prepare columns
    new_columns = {
        'instagram_followers': None, 'instagram_verified': False, 'instagram_handle': None,
        'twitter_followers': None, 'twitter_verified': False, 'twitter_handle': None,
        'tiktok_followers': None, 'tiktok_handle': None,
        'contract_value': None, 'current_contract_length': None, 'guaranteed_money': None
    }
    
    for col in new_columns:
        if col not in df.columns:
            df[col] = new_columns[col]
    
    # Prepare tasks
    tasks = []
    for idx, row in df.iterrows():
        # Create fresh collectors for each task to avoid thread issues
        free_collector = get_free_data_collector()
        contract_collector = ContractCollector()
        tasks.append((idx, row['player_name'], row.get('team', ''), free_collector, contract_collector))
    
    # Collect data with parallel workers
    print(f"\n📊 Collecting data for {len(df)} players...")
    print(f"   ETA: ~{len(df) * 0.5 / max_workers / 60:.0f} minutes with {max_workers} workers")
    
    social_success = 0
    contract_success = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(collect_player_data, task): task for task in tasks}
        
        for future in tqdm(as_completed(futures), total=len(tasks), desc="Processing"):
            try:
                result = future.result()
                idx = result.pop('idx')
                
                # Update dataframe
                for key, value in result.items():
                    if value is not None:
                        df.at[idx, key] = value
                
                if result.get('instagram_followers') or result.get('twitter_followers'):
                    social_success += 1
                if result.get('contract_value'):
                    contract_success += 1
                    
            except Exception as e:
                logger.debug(f"Task failed: {e}")
    
    # Save results
    print(f"\n💾 Saving results...")
    df.to_csv(output_file, index=False)
    
    # Summary
    print(f"\n{'='*100}")
    print(f"✅ COLLECTION COMPLETE!")
    print(f"{'='*100}")
    print(f"\n📊 Results:")
    print(f"   Total Players: {len(df)}")
    print(f"   Social Media Success: {social_success}/{len(df)} ({social_success/len(df)*100:.1f}%)")
    print(f"   Contract Success: {contract_success}/{len(df)} ({contract_success/len(df)*100:.1f}%)")
    
    # Sample successful collections
    print(f"\n🏆 Sample Players with New Data:")
    sample = df[(df['instagram_followers'].notna()) | (df['contract_value'].notna())].head(10)
    for _, row in sample.iterrows():
        print(f"   • {row['player_name']:30s} ", end='')
        if pd.notna(row.get('instagram_followers')) and row['instagram_followers'] > 0:
            print(f"📸 {int(row['instagram_followers']):,} ", end='')
        if pd.notna(row.get('twitter_followers')) and row['twitter_followers'] > 0:
            print(f"🐦 {int(row['twitter_followers']):,} ", end='')
        if pd.notna(row.get('contract_value')) and row['contract_value'] > 0:
            print(f"💰 ${int(row['contract_value']):,}", end='')
        print()
    
    print(f"\n{'='*100}\n")


if __name__ == '__main__':
    main()

