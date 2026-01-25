#!/usr/bin/env python3
"""
Fast Top Player Enrichment
============================
Enrich only the top players with social + contract data for immediate validation
"""

import pandas as pd
import logging
import sys
from pathlib import Path
from tqdm import tqdm
import time

from gravity.free_apis import get_free_data_collector
from gravity.contract_collector import ContractCollector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def enrich_player(row, collector, contract_col):
    """Enrich a single player with social + contract data"""
    player_name = row['player_name']
    team = row.get('team', '')
    
    result = {}
    
    try:
        # Try common handle patterns
        name_clean = player_name.lower().replace('.', '').replace("'", '').replace('-', '')
        parts = name_clean.split()
        
        if len(parts) >= 2:
            first, last = parts[0], parts[-1]
            handles_to_try = [
                f"{first}{last}",
                f"{first}_{last}",
                f"{first}.{last}",
                f"_{first}{last}",
            ]
            
            # Instagram
            for handle in handles_to_try:
                try:
                    ig_stats = collector.social.get_instagram_stats(handle)
                    if ig_stats.get('followers', 0) > 1000:  # Minimum threshold for stars
                        result['instagram_followers'] = ig_stats['followers']
                        result['instagram_verified'] = ig_stats.get('verified', False)
                        result['instagram_handle'] = f"@{handle}"
                        logger.info(f"✅ {player_name}: {ig_stats['followers']:,} Instagram")
                        break
                except:
                    pass
                time.sleep(0.05)
            
            # Twitter
            for handle in handles_to_try:
                try:
                    tw_stats = collector.social.get_twitter_stats(handle)
                    if tw_stats.get('followers', 0) > 1000:
                        result['twitter_followers'] = tw_stats['followers']
                        result['twitter_verified'] = tw_stats.get('verified', False)
                        result['twitter_handle'] = f"@{handle}"
                        logger.info(f"✅ {player_name}: {tw_stats['followers']:,} Twitter")
                        break
                except:
                    pass
                time.sleep(0.05)
        
        # Contract
        try:
            contract_data = contract_col.collect_contract_data(player_name, team, 'nfl')
            if contract_data:
                result['contract_value'] = contract_data.get('contract_value')
                result['current_contract_length'] = contract_data.get('contract_years')
                result['guaranteed_money'] = contract_data.get('guaranteed_money')
                if result.get('contract_value'):
                    logger.info(f"💰 {player_name}: ${result['contract_value']:,}")
        except:
            pass
            
    except Exception as e:
        logger.debug(f"Failed for {player_name}: {e}")
    
    return result


def main():
    if len(sys.argv) < 3:
        print("Usage: python enrich_top_players.py input.csv output.csv [top_n]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    top_n = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    
    print(f"\n{'='*80}")
    print(f"🚀 FAST TOP PLAYER ENRICHMENT")
    print(f"{'='*80}")
    print(f"\n📂 Input: {input_file}")
    print(f"📂 Output: {output_file}")
    print(f"🎯 Top N: {top_n} players")
    
    # Load data
    logger.info("Loading data...")
    df = pd.read_csv(input_file)
    
    # Sort by some metric to get "top" players (use existing stats or just first N)
    # Prioritize players with high career stats
    if 'career_touchdowns' in df.columns:
        df['_priority'] = df['career_touchdowns'].fillna(0) + df['career_yards'].fillna(0)/1000
        df = df.sort_values('_priority', ascending=False)
        df = df.drop('_priority', axis=1)
    
    # Take top N
    df_top = df.head(top_n).copy()
    logger.info(f"Processing top {len(df_top)} players...")
    
    # Add columns if they don't exist
    for col in ['instagram_followers', 'instagram_verified', 'instagram_handle',
                'twitter_followers', 'twitter_verified', 'twitter_handle',
                'contract_value', 'current_contract_length', 'guaranteed_money']:
        if col not in df_top.columns:
            df_top[col] = None
    
    # Initialize collectors
    collector = get_free_data_collector()
    contract_col = ContractCollector()
    
    # Enrich players
    logger.info("Enriching players...")
    for idx, row in tqdm(df_top.iterrows(), total=len(df_top), desc="Processing"):
        result = enrich_player(row, collector, contract_col)
        for key, value in result.items():
            df_top.at[idx, key] = value
        time.sleep(0.2)  # Rate limit
    
    # Save
    df_top.to_csv(output_file, index=False)
    
    # Summary
    social_count = len(df_top[df_top['instagram_followers'].notna()])
    contract_count = len(df_top[df_top['contract_value'].notna()])
    
    print(f"\n{'='*80}")
    print(f"✅ ENRICHMENT COMPLETE!")
    print(f"{'='*80}")
    print(f"\n📊 Results:")
    print(f"   Social Success: {social_count}/{len(df_top)} ({social_count/len(df_top)*100:.1f}%)")
    print(f"   Contract Success: {contract_count}/{len(df_top)} ({contract_count/len(df_top)*100:.1f}%)")
    
    # Show top enriched players
    print(f"\n🏆 Top 10 Enriched Players:")
    enriched = df_top[(df_top['instagram_followers'].notna()) | (df_top['contract_value'].notna())].head(10)
    for _, row in enriched.iterrows():
        print(f"   • {row['player_name']:25s} ", end='')
        if pd.notna(row.get('instagram_followers')):
            print(f"📸 {int(row['instagram_followers']):8,} ", end='')
        if pd.notna(row.get('twitter_followers')):
            print(f"🐦 {int(row['twitter_followers']):8,} ", end='')
        if pd.notna(row.get('contract_value')):
            print(f"💰 ${int(row['contract_value']):,}", end='')
        print()
    
    print(f"\n{'='*80}\n")
    print(f"💡 Next: Run the pipeline to compute Gravity Scores with this enriched data!")
    print(f"   python score_all_sports.py {output_file} final_scores/NFL_TOP_ENRICHED.csv nfl")


if __name__ == '__main__':
    main()

