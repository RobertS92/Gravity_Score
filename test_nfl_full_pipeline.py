#!/usr/bin/env python3
"""
NFL Test Scraper with Full Pipeline & Scoring
============================================
Tests complete NFL data collection and scoring pipeline with 5 players:
1. Scrapes player data
2. Flattens nested structures
3. Imputes missing values
4. Extracts features
5. Calculates Gravity Scores
6. Displays results

Output saved to: test_outputs/nfl_test_YYYYMMDD_HHMMSS/
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path
from dataclasses import asdict
import pandas as pd

# Add paths
script_dir = Path(__file__).parent.absolute()
parent_dir = script_dir.parent.absolute()
sys.path.insert(0, str(parent_dir))
sys.path.insert(0, str(script_dir / 'gravity'))

from gravity.nfl_scraper import NFLPlayerCollector
from gravity.scrape import get_direct_api
from gravity.data_pipeline import GravityPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test players - mix of positions and star levels
TEST_PLAYERS = [
    {"name": "Patrick Mahomes", "team": "Kansas City Chiefs", "position": "QB"},
    {"name": "Travis Kelce", "team": "Kansas City Chiefs", "position": "TE"},
    {"name": "Josh Allen", "team": "Buffalo Bills", "position": "QB"},
    {"name": "Creed Humphrey", "team": "Kansas City Chiefs", "position": "C"},
    {"name": "Justin Jefferson", "team": "Minnesota Vikings", "position": "WR"}
]


def format_value(value, is_money=False):
    """Format values for display"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    if is_money:
        return f"${value:,.0f}"
    if isinstance(value, (int, float)) and value > 1000000:
        return f"{value/1000000:.2f}M"
    return str(value)


def test_full_pipeline():
    """Run complete test: scrape + pipeline + scoring"""
    # Find the next test number
    test_outputs_dir = Path("test_outputs")
    test_outputs_dir.mkdir(exist_ok=True)
    
    # Find existing nfl_test_N directories
    existing_tests = list(test_outputs_dir.glob("nfl_test_*"))
    test_numbers = []
    for test_dir in existing_tests:
        if test_dir.name.startswith("nfl_test_") and test_dir.name != "nfl_test_LATEST":
            try:
                num = int(test_dir.name.replace("nfl_test_", ""))
                test_numbers.append(num)
            except ValueError:
                continue
    
    # Get next test number (start at 0 if none exist)
    next_num = max(test_numbers) + 1 if test_numbers else 0
    
    output_dir = test_outputs_dir / f"nfl_test_{next_num}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a symlink to the most recent test
    latest_link = test_outputs_dir / "nfl_test_LATEST"
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(output_dir.name)
    
    print("\n" + "="*80)
    print("  🧪 NFL TEST SCRAPER - FULL PIPELINE & SCORING")
    print("="*80)
    print(f"  Testing with {len(TEST_PLAYERS)} players")
    print(f"  Output Directory: {output_dir}")
    print(f"  Test Number: {next_num}")
    print("="*80 + "\n")
    
    # ========================================================================
    # STEP 1: SCRAPE DATA
    # ========================================================================
    print("📥 STEP 1: Scraping Player Data...")
    print("-" * 80)
    
    collector = NFLPlayerCollector(get_direct_api())
    player_data_list = []
    
    for i, player_info in enumerate(TEST_PLAYERS, 1):
        print(f"\n[{i}/{len(TEST_PLAYERS)}] Collecting: {player_info['name']} ({player_info['position']})")
        try:
            player_data = collector.collect_player_data(
                player_info["name"],
                player_info["team"],
                player_info["position"]
            )
            if player_data:
                player_data_list.append(player_data)
                print(f"   ✅ Data collected")
                
                # Quick validation
                identity = player_data.identity if hasattr(player_data, 'identity') else None
                if identity:
                    age = identity.age if hasattr(identity, 'age') else None
                    birth_date = identity.birth_date if hasattr(identity, 'birth_date') else None
                    print(f"   📊 Age: {format_value(age)}, Birth Date: {format_value(birth_date)}")
            else:
                print(f"   ❌ No data collected")
        except Exception as e:
            logger.error(f"Failed to collect {player_info['name']}: {e}")
            print(f"   ❌ Error: {e}")
    
    if not player_data_list:
        print("\n❌ No player data collected. Cannot continue.")
        return
    
    print(f"\n✅ Scraped {len(player_data_list)}/{len(TEST_PLAYERS)} players")
    
    # ========================================================================
    # STEP 2: CONVERT TO DICT FORMAT
    # ========================================================================
    print("\n🔄 STEP 2: Converting to dictionary format...")
    print("-" * 80)
    
    player_dicts = [asdict(player) for player in player_data_list]
    print(f"✅ Converted {len(player_dicts)} players to dictionaries")
    
    # Save raw scraped data
    import json
    raw_data_file = output_dir / f"01_raw_scraped_data_{next_num}.json"
    with open(raw_data_file, 'w') as f:
        json.dump(player_dicts, f, indent=2, default=str)
    print(f"💾 Saved raw data to: {raw_data_file.name}")
    
    # ========================================================================
    # STEP 3: RUN FULL PIPELINE
    # ========================================================================
    print("\n🚀 STEP 3: Running Full Pipeline (Flatten → Impute → Features → Scores)...")
    print("-" * 80)
    
    try:
        pipeline = GravityPipeline(max_years=3)
        df = pipeline.process(player_dicts, output_format='dataframe')
        print(f"✅ Pipeline complete! Processed {len(df)} players")
        print(f"   Columns: {len(df.columns)}")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ========================================================================
    # STEP 4: DISPLAY RESULTS
    # ========================================================================
    print("\n" + "="*80)
    print("  📊 RESULTS - GRAVITY SCORES")
    print("="*80)
    
    # Sort by gravity score
    df_sorted = df.sort_values('gravity_score', ascending=False)
    
    for i, (idx, player) in enumerate(df_sorted.iterrows(), 1):
        name = player.get('player_name', player.get('identity.name', 'Unknown'))
        position = player.get('position', player.get('identity.position', '?'))
        team = player.get('team', player.get('identity.team', '?'))
        
        # Scores
        total_score = player.get('gravity_score', 0)
        perf_score = player.get('gravity.performance_score', 0)
        market_score = player.get('gravity.market_score', 0)
        social_score = player.get('gravity.social_score', 0)
        velocity_score = player.get('gravity.velocity_score', 0)
        risk_score = player.get('gravity.risk_score', 0)
        tier = player.get('gravity_tier', 'Unknown')
        percentile = player.get('gravity_percentile', 0)
        
        # Key data
        age = player.get('identity.age', player.get('age'))
        contract = player.get('identity.contract_value', player.get('contract_value'))
        instagram = player.get('brand.instagram_followers', player.get('instagram_followers'))
        twitter = player.get('brand.twitter_followers', player.get('twitter_followers'))
        
        print(f"\n{i}. {name:25s} {position:3s} {team:20s}")
        print(f"   {'='*70}")
        print(f"   🎯 Gravity Score: {total_score:5.1f}/100  [{tier:12s}]  (Top {100-percentile:.0f}%)")
        print(f"   📈 Component Scores:")
        print(f"      Performance: {perf_score:5.1f} | Market: {market_score:5.1f} | Social: {social_score:5.1f}")
        print(f"      Velocity:    {velocity_score:5.1f} | Risk:    {risk_score:5.1f}")
        print(f"   📋 Key Data:")
        print(f"      Age: {format_value(age)} | Contract: {format_value(contract, is_money=True)}")
        print(f"      Instagram: {format_value(instagram)} | Twitter: {format_value(twitter)}")
    
    # ========================================================================
    # STEP 5: SUMMARY STATISTICS
    # ========================================================================
    print("\n" + "="*80)
    print("  📊 SUMMARY STATISTICS")
    print("="*80)
    
    print(f"\n   Gravity Scores:")
    print(f"      Min:  {df['gravity_score'].min():.1f}")
    print(f"      Max:  {df['gravity_score'].max():.1f}")
    print(f"      Avg:  {df['gravity_score'].mean():.1f}")
    print(f"      Median: {df['gravity_score'].median():.1f}")
    
    print(f"\n   Component Score Averages:")
    print(f"      Performance: {df['gravity.performance_score'].mean():.1f}")
    print(f"      Market:      {df['gravity.market_score'].mean():.1f}")
    print(f"      Social:      {df['gravity.social_score'].mean():.1f}")
    print(f"      Velocity:    {df['gravity.velocity_score'].mean():.1f}")
    print(f"      Risk:        {df['gravity.risk_score'].mean():.1f}")
    
    # Tier distribution
    if 'gravity_tier' in df.columns:
        print(f"\n   Tier Distribution:")
        tier_counts = df['gravity_tier'].value_counts()
        for tier, count in tier_counts.items():
            pct = (count / len(df)) * 100
            print(f"      {tier:12s}: {count} ({pct:5.1f}%)")
    
    # Data quality check
    print(f"\n   Data Quality:")
    age_col = 'identity.age' if 'identity.age' in df.columns else 'age'
    contract_col = 'identity.contract_value' if 'identity.contract_value' in df.columns else 'contract_value'
    instagram_col = 'brand.instagram_followers' if 'brand.instagram_followers' in df.columns else 'instagram_followers'
    twitter_col = 'brand.twitter_followers' if 'brand.twitter_followers' in df.columns else 'twitter_followers'
    
    age_count = df[age_col].notna().sum() if age_col in df.columns else 0
    
    # Convert contract to numeric before comparison
    if contract_col in df.columns:
        contract_numeric = pd.to_numeric(df[contract_col], errors='coerce').fillna(0)
        contract_count = (contract_numeric > 0).sum()
    else:
        contract_count = 0
    
    # Convert social media columns to numeric before comparison
    social_count = 0
    if instagram_col in df.columns and twitter_col in df.columns:
        instagram_numeric = pd.to_numeric(df[instagram_col], errors='coerce').fillna(0)
        twitter_numeric = pd.to_numeric(df[twitter_col], errors='coerce').fillna(0)
        social_count = ((instagram_numeric > 0) | (twitter_numeric > 0)).sum()
    elif instagram_col in df.columns:
        instagram_numeric = pd.to_numeric(df[instagram_col], errors='coerce').fillna(0)
        social_count = (instagram_numeric > 0).sum()
    elif twitter_col in df.columns:
        twitter_numeric = pd.to_numeric(df[twitter_col], errors='coerce').fillna(0)
        social_count = (twitter_numeric > 0).sum()
    
    print(f"      Age Data:     {age_count}/{len(df)} ({age_count*100//len(df) if len(df) > 0 else 0}%)")
    print(f"      Contract:    {contract_count}/{len(df)} ({contract_count*100//len(df) if len(df) > 0 else 0}%)")
    print(f"      Social Media: {social_count}/{len(df)} ({social_count*100//len(df) if len(df) > 0 else 0}%)")
    
    # ========================================================================
    # STEP 6: SAVE RESULTS
    # ========================================================================
    print("\n" + "="*80)
    print("  💾 SAVING RESULTS")
    print("="*80)
    
    # Save CSV with test number in filename
    csv_file = output_dir / f"02_final_scores_{next_num}.csv"
    df.to_csv(csv_file, index=False)
    print(f"✅ CSV saved: {csv_file.name}")
    
    # Save JSON with test number in filename
    json_file = output_dir / f"02_final_scores_{next_num}.json"
    # Convert to dict first to handle non-serializable types, then use json.dump
    import json
    records = df.to_dict(orient='records')
    with open(json_file, 'w') as f:
        json.dump(records, f, indent=2, default=str)
    print(f"✅ JSON saved: {json_file.name}")
    
    # Save summary report
    summary_file = output_dir / "03_summary_report.txt"
    with open(summary_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("  NFL TEST SCRAPER - SUMMARY REPORT\n")
        f.write("="*80 + "\n\n")
        f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Players Tested: {len(TEST_PLAYERS)}\n")
        f.write(f"Players Scraped: {len(player_data_list)}\n")
        f.write(f"Players Scored: {len(df)}\n\n")
        
        f.write("Gravity Scores:\n")
        f.write(f"  Min:    {df['gravity_score'].min():.1f}\n")
        f.write(f"  Max:    {df['gravity_score'].max():.1f}\n")
        f.write(f"  Avg:    {df['gravity_score'].mean():.1f}\n")
        f.write(f"  Median: {df['gravity_score'].median():.1f}\n\n")
        
        f.write("Component Averages:\n")
        f.write(f"  Performance: {df['gravity.performance_score'].mean():.1f}\n")
        f.write(f"  Market:      {df['gravity.market_score'].mean():.1f}\n")
        f.write(f"  Social:      {df['gravity.social_score'].mean():.1f}\n")
        f.write(f"  Velocity:    {df['gravity.velocity_score'].mean():.1f}\n")
        f.write(f"  Risk:        {df['gravity.risk_score'].mean():.1f}\n\n")
        
        f.write("Data Quality:\n")
        f.write(f"  Age Data:     {age_count}/{len(df)} ({age_count*100//len(df) if len(df) > 0 else 0}%)\n")
        f.write(f"  Contract:    {contract_count}/{len(df)} ({contract_count*100//len(df) if len(df) > 0 else 0}%)\n")
        f.write(f"  Social Media: {social_count}/{len(df)} ({social_count*100//len(df) if len(df) > 0 else 0}%)\n\n")
        
        f.write("Top Players:\n")
        for i, (idx, player) in enumerate(df_sorted.iterrows(), 1):
            name = player.get('player_name', player.get('identity.name', 'Unknown'))
            score = player.get('gravity_score', 0)
            tier = player.get('gravity_tier', 'Unknown')
            f.write(f"  {i}. {name:25s} - {score:5.1f}/100 [{tier}]\n")
    
    print(f"✅ Summary report saved: {summary_file.name}")
    
    # Create README in output directory
    readme_file = output_dir / "README.txt"
    with open(readme_file, 'w') as f:
        f.write("NFL Test Scraper Output\n")
        f.write("="*50 + "\n\n")
        f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Test Number: {next_num}\n\n")
        f.write("Files in this directory:\n")
        f.write(f"  01_raw_scraped_data_{next_num}.json - Raw scraped player data\n")
        f.write(f"  02_final_scores_{next_num}.csv      - Final scores (CSV format)\n")
        f.write(f"  02_final_scores_{next_num}.json     - Final scores (JSON format)\n")
        f.write("  03_summary_report.txt    - Summary statistics and report\n")
        f.write("  README.txt              - This file\n\n")
        f.write("To access the most recent test, use:\n")
        f.write("  test_outputs/nfl_test_LATEST/\n")
    
    print(f"✅ README saved: {readme_file.name}")
    
    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    print("\n" + "="*80)
    print("  ✅ TEST COMPLETE")
    print("="*80)
    
    print(f"\n📁 All results saved to: {output_dir}")
    print(f"🔗 Latest test link: test_outputs/nfl_test_LATEST/")
    
    if age_count >= len(df) * 0.8 and contract_count >= len(df) * 0.6:
        print("\n🎉 TEST PASSED - Data collection and scoring working correctly!")
        print("\n🚀 Ready for full scrape:")
        print("   python3 run_pipeline.py --scrape nfl --scrape-mode all --output final_scores/NFL_COMPLETE_$(date +%Y%m%d_%H%M%S).csv")
    else:
        print("\n⚠️  TEST PARTIAL - Some data missing:")
        if age_count < len(df) * 0.8:
            print(f"   - Age data: {age_count}/{len(df)} (need {int(len(df)*0.8)}+)")
        if contract_count < len(df) * 0.6:
            print(f"   - Contract data: {contract_count}/{len(df)} (need {int(len(df)*0.6)}+)")
    
    print()


if __name__ == '__main__':
    test_full_pipeline()

