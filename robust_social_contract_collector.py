#!/usr/bin/env python3
"""
Robust Social & Contract Data Collector
========================================
Production-grade collector with proper error handling and validation.
"""

import pandas as pd
import logging
import sys
from pathlib import Path
from tqdm import tqdm
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import collectors
try:
    from gravity.free_apis import SocialMediaAPI
    from gravity.contract_collector import ContractCollector
    import requests
    from bs4 import BeautifulSoup
except ImportError as e:
    logger.error(f"Import error: {e}")
    sys.exit(1)


class RobustDataCollector:
    """Robust collector with fallback strategies"""
    
    def __init__(self):
        self.social_api = SocialMediaAPI()
        self.contract_collector = ContractCollector()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_social_data(self, player_name, position=None):
        """Collect social media data with multiple strategies"""
        result = {
            'instagram_followers': None,
            'instagram_verified': False,
            'instagram_handle': None,
            'twitter_followers': None,
            'twitter_verified': False,
            'twitter_handle': None,
            'tiktok_followers': None,
            'tiktok_handle': None
        }
        
        try:
            # Strategy 1: Try common handle patterns
            handles = self._generate_handle_patterns(player_name)
            
            for handle in handles[:3]:  # Try top 3 patterns
                # Instagram
                try:
                    ig_stats = self.social_api.get_instagram_stats(handle)
                    if ig_stats and ig_stats.get('followers', 0) > 100:  # Minimum threshold
                        result['instagram_followers'] = ig_stats['followers']
                        result['instagram_verified'] = ig_stats.get('verified', False)
                        result['instagram_handle'] = f"@{handle}"
                        logger.info(f"✅ {player_name}: Instagram {ig_stats['followers']:,} followers")
                        break
                except Exception as e:
                    logger.debug(f"Instagram failed for {handle}: {e}")
                
                time.sleep(0.05)  # Rate limit
            
            # Twitter
            for handle in handles[:3]:
                try:
                    tw_stats = self.social_api.get_twitter_stats(handle)
                    if tw_stats and tw_stats.get('followers', 0) > 100:
                        result['twitter_followers'] = tw_stats['followers']
                        result['twitter_verified'] = tw_stats.get('verified', False)
                        result['twitter_handle'] = f"@{handle}"
                        logger.info(f"✅ {player_name}: Twitter {tw_stats['followers']:,} followers")
                        break
                except Exception as e:
                    logger.debug(f"Twitter failed for {handle}: {e}")
                
                time.sleep(0.05)
            
            # TikTok (less common for athletes, try just first handle)
            try:
                tt_stats = self.social_api.get_tiktok_stats(handles[0])
                if tt_stats and tt_stats.get('followers', 0) > 100:
                    result['tiktok_followers'] = tt_stats['followers']
                    result['tiktok_handle'] = f"@{handles[0]}"
            except:
                pass
                
        except Exception as e:
            logger.debug(f"Social collection failed for {player_name}: {e}")
        
        return result
    
    def get_contract_data(self, player_name, team, sport='nfl'):
        """Collect contract data with fallbacks"""
        result = {
            'contract_value': None,
            'contract_length': None,
            'guaranteed_money': None,
            'apy': None,
            'free_agency_year': None
        }
        
        try:
            contract_data = self.contract_collector.collect_contract_data(
                player_name=player_name,
                team=team,
                sport=sport
            )
            
            if contract_data:
                result['contract_value'] = contract_data.get('contract_value')
                result['contract_length'] = contract_data.get('contract_years')
                result['guaranteed_money'] = contract_data.get('guaranteed_money')
                result['apy'] = contract_data.get('apy')
                result['free_agency_year'] = contract_data.get('free_agency_year')
                
                if result['contract_value']:
                    logger.info(f"💰 {player_name}: ${result['contract_value']:,} contract")
        
        except Exception as e:
            logger.debug(f"Contract collection failed for {player_name}: {e}")
        
        return result
    
    def _generate_handle_patterns(self, player_name):
        """Generate common social media handle patterns"""
        # Clean name
        name = player_name.lower().strip()
        name = name.replace('.', '').replace("'", '').replace('-', '')
        
        parts = name.split()
        if len(parts) < 2:
            return [name.replace(' ', '')]
        
        first = parts[0]
        last = parts[-1]
        
        # Common patterns for athletes
        patterns = [
            f"{first}{last}",           # johndoe
            f"{first}_{last}",          # john_doe
            f"{first}.{last}",          # john.doe
            f"{first[0]}{last}",        # jdoe
            f"{first}{last[0]}",        # johnd
            f"{last}{first}",           # doejohn
            f"_{first}{last}",          # _johndoe
            f"{first}{last}_",          # johndoe_
            name.replace(' ', ''),       # full name no space
            name.replace(' ', '_'),      # full_name
        ]
        
        return patterns


def collect_player_enrichment(args):
    """Worker function for parallel processing"""
    idx, row, collector = args
    
    player_name = row['player_name']
    team = row.get('team', '')
    position = row.get('position', '')
    
    logger.info(f"🔄 Processing: {player_name} ({team})")
    
    result = {'idx': idx}
    
    # Collect social data
    social_data = collector.get_social_data(player_name, position)
    result.update(social_data)
    
    # Collect contract data
    contract_data = collector.get_contract_data(player_name, team)
    result.update(contract_data)
    
    time.sleep(0.2)  # Rate limiting
    
    return result


def main():
    if len(sys.argv) < 3:
        print("Usage: python robust_social_contract_collector.py input.csv output.csv [max_workers]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    max_workers = int(sys.argv[3]) if len(sys.argv) > 3 else 5  # Lower default for stability
    
    print(f"\n{'='*100}")
    print(f"🚀 ROBUST SOCIAL & CONTRACT COLLECTOR")
    print(f"{'='*100}")
    print(f"\n📂 Input:  {input_file}")
    print(f"📂 Output: {output_file}")
    print(f"⚙️  Workers: {max_workers}")
    
    # Load data
    logger.info("Loading player data...")
    df = pd.read_csv(input_file)
    logger.info(f"Loaded {len(df)} players")
    
    # Prepare columns
    new_columns = {
        'instagram_followers': None,
        'instagram_verified': False,
        'instagram_handle': None,
        'twitter_followers': None,
        'twitter_verified': False,
        'twitter_handle': None,
        'tiktok_followers': None,
        'tiktok_handle': None,
        'contract_value': None,
        'contract_length': None,
        'guaranteed_money': None,
        'apy': None,
        'free_agency_year': None
    }
    
    for col in new_columns:
        if col not in df.columns:
            df[col] = new_columns[col]
    
    # Prepare tasks - create ONE collector per worker
    logger.info(f"Preparing {len(df)} collection tasks...")
    collectors = [RobustDataCollector() for _ in range(max_workers)]
    tasks = []
    
    for idx, row in df.iterrows():
        # Assign collector based on worker
        collector = collectors[idx % max_workers]
        tasks.append((idx, row, collector))
    
    # Process with progress bar
    logger.info("Starting data collection...")
    social_success = 0
    contract_success = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(collect_player_enrichment, task): task for task in tasks}
        
        for future in tqdm(as_completed(futures), total=len(tasks), desc="Collecting"):
            try:
                result = future.result()
                idx = result.pop('idx')
                
                # Update dataframe
                for key, value in result.items():
                    if value is not None and value != False:
                        df.at[idx, key] = value
                
                # Count successes
                if result.get('instagram_followers') or result.get('twitter_followers'):
                    social_success += 1
                if result.get('contract_value'):
                    contract_success += 1
                    
            except Exception as e:
                logger.error(f"Task failed: {e}")
    
    # Save results
    logger.info("Saving enriched data...")
    df.to_csv(output_file, index=False)
    
    # Summary
    print(f"\n{'='*100}")
    print(f"✅ COLLECTION COMPLETE!")
    print(f"{'='*100}")
    print(f"\n📊 Success Rates:")
    print(f"   Social Media: {social_success}/{len(df)} ({social_success/len(df)*100:.1f}%)")
    print(f"   Contract Data: {contract_success}/{len(df)} ({contract_success/len(df)*100:.1f}%)")
    
    # Top performers
    print(f"\n🏆 Top 10 Players by Social Following:")
    social_df = df[df['instagram_followers'].notna()].copy()
    social_df['total_followers'] = social_df['instagram_followers'].fillna(0) + social_df['twitter_followers'].fillna(0)
    top_social = social_df.nlargest(10, 'total_followers')
    
    for _, row in top_social.iterrows():
        print(f"   • {row['player_name']:30s} ", end='')
        if pd.notna(row.get('instagram_followers')):
            print(f"📸 {int(row['instagram_followers']):,} ", end='')
        if pd.notna(row.get('twitter_followers')):
            print(f"🐦 {int(row['twitter_followers']):,} ", end='')
        if pd.notna(row.get('contract_value')):
            print(f"💰 ${int(row['contract_value']):,}", end='')
        print()
    
    print(f"\n💰 Top 10 Contracts:")
    contract_df = df[df['contract_value'].notna()].nlargest(10, 'contract_value')
    for _, row in contract_df.iterrows():
        print(f"   • {row['player_name']:30s} ${int(row['contract_value']):,}")
    
    print(f"\n{'='*100}\n")


if __name__ == '__main__':
    main()

