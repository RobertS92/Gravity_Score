#!/usr/bin/env python3
"""
Test NBA Pipeline with VERIFIED Lakers Roster
ESPN API is corrupted, so using manually verified roster
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from gravity.nba_scraper import NBAPlayerCollector
from gravity.data_pipeline import GravityScoreCalculator, DataImputer
from verified_lakers_roster import get_verified_lakers_roster
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import os

# Set FAST_MODE for faster collection
os.environ['FAST_MODE'] = 'true'

print("="*70)
print("🏀 LA LAKERS PIPELINE TEST (VERIFIED ROSTER)")
print("="*70)
print()

firecrawl_key = os.getenv('FIRECRAWL_API_KEY', 'fc-test')

# PHASE 1: Use Verified Lakers Roster
print("PHASE 1: Using verified Lakers roster (ESPN API corrupted)...")
print("-"*70)

roster = get_verified_lakers_roster()
print(f"✅ Using {len(roster)} verified Lakers players")
print()

# Show first 5 players
print("Verified Roster (first 5):")
for i, player in enumerate(roster[:5], 1):
    print(f"  {i}. {player['name']:25s} - {player['position']}")
print()

# PHASE 2: Collect Player Data (Parallel with thread-safe collectors)
print("PHASE 2: Collecting player data in parallel...")
print("-"*70)

def collect_player(player_info):
    """Collect data with thread-local collector"""
    try:
        collector = NBAPlayerCollector(firecrawl_key)
        return collector.collect_player_data(
            player_info['name'],
            'Los Angeles Lakers',
            player_info.get('position', 'F')
        )
    except Exception as e:
        print(f"✗ Failed {player_info['name']}: {e}")
        return None

all_players_data = []
max_workers = 5  # Use 5 parallel workers

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = {executor.submit(collect_player, player): player for player in roster}
    
    for future in tqdm(as_completed(futures), total=len(futures), desc="🏀 Lakers", unit="player"):
        player_data = future.result()
        if player_data:
            all_players_data.append(player_data)

print(f"\n✅ Collected {len(all_players_data)}/{len(roster)} Lakers players")
print()

# PHASE 3: Verify Data Uniqueness
print("PHASE 3: Verifying data uniqueness...")
print("-"*70)

ages = [p.identity.age for p in all_players_data if p.identity and p.identity.age]
drafts = [p.identity.draft_year for p in all_players_data if p.identity and p.identity.draft_year]
names = [p.player_name for p in all_players_data]

print(f"Unique names: {len(set(names))}/{len(names)}")
print(f"Unique ages: {len(set(ages))}/{len(ages)}")
print(f"Unique draft years: {len(set(drafts))}/{len(drafts)}")
print()

if len(set(names)) == len(names):
    print("✅ All players have unique names")
else:
    print("⚠️  WARNING: Duplicate player names detected!")

# Show sample stats
print("\nSample Player Stats:")
for p in all_players_data[:3]:
    if p.identity and p.proof and p.proof.current_season_stats:
        stats = p.proof.current_season_stats
        ppg = stats.get('avgPoints', stats.get('Points Per Game', 'N/A'))
        print(f"  {p.player_name}: {p.identity.age}y, Draft {p.identity.draft_year}, {ppg} PPG")

print()

# PHASE 4: Convert to DataFrame
print("PHASE 4: Preparing data for ML scoring...")
print("-"*70)

records = []
for player in all_players_data:
    record = {
        'player_name': player.player_name,
        'team': player.team,
        'position': player.position,
        'data_quality_score': player.data_quality_score,
    }
    
    # Add identity fields
    if player.identity:
        for field, value in vars(player.identity).items():
            record[f'identity.{field}'] = value
    
    # Add proof fields
    if player.proof:
        for field, value in vars(player.proof).items():
            record[f'proof.{field}'] = value
    
    # Add brand fields
    if player.brand:
        for field, value in vars(player.brand).items():
            record[f'brand.{field}'] = value
    
    # Add proximity fields
    if player.proximity:
        for field, value in vars(player.proximity).items():
            if not isinstance(value, list):
                record[f'proximity.{field}'] = value
            else:
                record[f'proximity.{field}'] = len(value)
    
    # Add velocity fields
    if player.velocity:
        for field, value in vars(player.velocity).items():
            record[f'velocity.{field}'] = value
    
    # Add risk fields
    if player.risk:
        for field, value in vars(player.risk).items():
            if not isinstance(value, list):
                record[f'risk.{field}'] = value
            else:
                record[f'risk.{field}'] = len(value)
    
    records.append(record)

df = pd.DataFrame(records)
print(f"✅ DataFrame: {len(df)} players × {len(df.columns)} features")
print()

# PHASE 5: ML Scoring
print("PHASE 5: Calculating Gravity Scores (ML/Neural Networks)...")
print("-"*70)

# Impute missing values
imputer = DataImputer()
df = imputer.impute_data(df)
print("✅ Imputation complete")

# Calculate gravity scores
calculator = GravityScoreCalculator()
df = calculator.calculate_gravity_scores(df)
print("✅ Gravity scores calculated")
print()

# PHASE 6: Results
print("="*70)
print("📊 RESULTS")
print("="*70)
print()

print(f"Total Lakers Players: {len(df)}")
print(f"Avg Gravity Score: {df['gravity_score'].mean():.2f}")
print(f"Score Range: {df['gravity_score'].min():.2f} - {df['gravity_score'].max():.2f}")
print()

print("🏆 Top 5 Lakers by Gravity Score:")
print("-"*70)
top_5 = df.nlargest(5, 'gravity_score')[['player_name', 'position', 'gravity_score', 'gravity_tier']]
for idx, row in top_5.iterrows():
    print(f"  {row['player_name']:25s} ({row['position']:3s}) - {row['gravity_score']:.2f} [{row['gravity_tier']}]")

print()

# Verify LeBron and AD are high
lebron_score = df[df['player_name'] == 'LeBron James']['gravity_score'].values
ad_score = df[df['player_name'] == 'Anthony Davis']['gravity_score'].values

if len(lebron_score) > 0:
    print(f"LeBron James: {lebron_score[0]:.2f}")
if len(ad_score) > 0:
    print(f"Anthony Davis: {ad_score[0]:.2f}")

print()

# Verify unique scores
unique_scores = df['gravity_score'].nunique()
total_players = len(df)
print(f"Unique Scores: {unique_scores}/{total_players}")

if unique_scores >= total_players * 0.7:  # At least 70% unique
    print("✅ PASS: Scores are sufficiently unique")
else:
    print("⚠️  WARNING: Too many duplicate scores")

print()

# Save results
output_dir = "test_results"
os.makedirs(output_dir, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
output_file = f"{output_dir}/lakers_verified_{timestamp}.csv"
df.to_csv(output_file, index=False)
print(f"💾 Saved to: {output_file}")

print()
print("="*70)
print("✅ LAKERS TEST COMPLETE!")
print("="*70)

