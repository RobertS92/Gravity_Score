#!/usr/bin/env python3
"""
NBA Complete Pipeline - Collection + ML Scoring
Uses ESPN API for reliable roster collection
"""
import os
import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from gravity.nba_scraper import NBAPlayerCollector
from gravity.data_pipeline import GravityScoreCalculator, DataImputer
from verified_nba_rosters_2024_25 import get_all_verified_rosters, count_total_players
import pandas as pd
from datetime import datetime
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print("="*70)
    print("🏀 NBA COMPLETE PIPELINE - VERIFIED Rosters + ML Scoring")
    print("="*70)
    print()
    print("⚠️  NOTE: Using VERIFIED rosters (ESPN API has data corruption)")
    print()

    # Check for Perplexity API
    has_perplexity = bool(os.getenv('PERPLEXITY_API_KEY'))
    if has_perplexity:
        print("✅ Perplexity AI fallback ENABLED")
    else:
        print("ℹ️  Perplexity AI fallback DISABLED (set PERPLEXITY_API_KEY to enable)")
    print()

    # Initialize
    firecrawl_key = os.getenv('FIRECRAWL_API_KEY', 'fc-test')
    
    # PHASE 1: Collect Data using ESPN API
    print("PHASE 1: Collecting NBA players via ESPN API (FAST_MODE)...")
    print("-"*70)

    # Get all NBA teams using VERIFIED rosters (ESPN API is broken)
    all_rosters = get_all_verified_rosters()
    print(f"Found {len(all_rosters)} NBA teams (VERIFIED rosters)")
    print()

    # Step 1: Load verified rosters
    print("📋 Step 1: Loading VERIFIED team rosters (ESPN API corrupted)...")
    all_roster_entries = []
    
    for team_name, roster in tqdm(all_rosters.items(), desc="🏀 Rosters", unit="team"):
        logger.info(f"📋 {team_name}: {len(roster)} players (verified)")
        
        for player_info in roster:
            player_name = player_info.get('name', '')
            if player_name:
                all_roster_entries.append({
                    'name': player_name,
                    'position': player_info.get('position', 'F'),
                    'team': team_name
                })
    
    print(f"✅ Loaded {len(all_roster_entries)} total players across {len(all_rosters)} teams")
    print()

    # Step 2: Collect player data in parallel with THREAD-SAFE collectors
    print("🚀 Step 2: Collecting player data in PARALLEL (thread-safe)...")
    max_workers = int(os.getenv('MAX_CONCURRENT_PLAYERS', '10'))
    print(f"Using {max_workers} parallel workers with isolated collectors")
    print()
    
    def collect_player(player_info):
        """Collect data for a single player using a THREAD-LOCAL collector"""
        try:
            # Create a NEW collector instance for THIS thread to avoid shared state
            thread_collector = NBAPlayerCollector(firecrawl_key)
            
            player_data = thread_collector.collect_player_data(
                player_info['name'],
                player_info['team'],
                player_info['position']
            )
            return player_data
        except Exception as e:
            logger.warning(f"✗ Failed {player_info['name']}: {e}")
            return None
    
    all_players_data = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {executor.submit(collect_player, entry): entry for entry in all_roster_entries}
        
        # Process results as they complete
        for future in tqdm(as_completed(futures), total=len(futures), desc="🏀 Players", unit="player"):
            player_data = future.result()
            if player_data:
                all_players_data.append(player_data)
    
    print(f"\n✅ Collected {len(all_players_data)} players successfully")
    print()

    # Convert to DataFrame format for scoring
    print("PHASE 2: Preparing data for ML scoring...")
    print("-"*70)
    records = []
    for player in all_players_data:
        record = {
            'player_name': player.player_name,
            'team': player.team,
            'position': player.position,
            'data_quality_score': player.data_quality_score,
        }
        
        # Add all fields from identity, proof, brand, proximity, velocity, risk
        if player.identity:
            for field, value in vars(player.identity).items():
                record[f'identity.{field}'] = value
        
        if player.proof:
            for field, value in vars(player.proof).items():
                record[f'proof.{field}'] = value
        
        if player.brand:
            for field, value in vars(player.brand).items():
                record[f'brand.{field}'] = value
        
        if player.proximity:
            for field, value in vars(player.proximity).items():
                if not isinstance(value, list):
                    record[f'proximity.{field}'] = value
                else:
                    record[f'proximity.{field}'] = len(value)
        
        if player.velocity:
            for field, value in vars(player.velocity).items():
                record[f'velocity.{field}'] = value
        
        if player.risk:
            for field, value in vars(player.risk).items():
                if not isinstance(value, list):
                    record[f'risk.{field}'] = value
                else:
                    record[f'risk.{field}'] = len(value)
        
        records.append(record)

    df = pd.DataFrame(records)
    print(f"✅ Prepared {len(df)} players with {len(df.columns)} features")
    print()

    # PHASE 3: Apply ML/Neural Network Scoring
    print("PHASE 3: Calculating Gravity Scores (ML/NN-based)...")
    print("-"*70)

    # Impute missing values
    imputer = DataImputer()
    df = imputer.impute_data(df)
    print("✅ Imputation complete")

    # Calculate gravity scores using ML/NN models
    calculator = GravityScoreCalculator()
    df = calculator.calculate_gravity_scores(df)
    print("✅ Gravity scores calculated")
    print()

    # PHASE 4: Save Results
    print("PHASE 4: Saving results...")
    print("-"*70)
    output_dir = "/Users/robcseals/Gravity_Score/Gravity_Final_Scores/NBA"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_file = f"{output_dir}/nba_gravity_scores_{timestamp}.csv"

    df.to_csv(output_file, index=False)
    print(f"✅ Saved to: {output_file}")
    print()

    # PHASE 5: Summary
    print("="*70)
    print("📊 FINAL SUMMARY")
    print("="*70)
    print(f"Total Players: {len(df)}")
    print(f"Avg Gravity Score: {df['gravity_score'].mean():.2f}")
    print(f"Score Range: {df['gravity_score'].min():.2f} - {df['gravity_score'].max():.2f}")
    print()

    print("🏆 Top 10 NBA Players by Gravity Score:")
    print("-"*70)
    top_10 = df.nlargest(10, 'gravity_score')[['player_name', 'team', 'position', 'gravity_score', 'gravity_tier']]
    for idx, row in top_10.iterrows():
        tier = row.get('gravity_tier', '?')
        print(f"  {row['player_name']:25s} ({row['position']:3s} - {row.get('team', 'N/A'):20s}) - {row['gravity_score']:.2f} [{tier}]")

    print()
    print("="*70)
    print("✅ NBA PIPELINE COMPLETE!")
    print("="*70)
    print()
    print(f"Output file: {output_file}")
    print(f"  - {len(df)} players scored")
    print(f"  - Uses ML/Neural Network models")
    print(f"  - Performance, Market, Social, Velocity, Risk scores")
    print(f"  - Equal treatment for all positions (no multipliers)")

if __name__ == '__main__':
    main()

