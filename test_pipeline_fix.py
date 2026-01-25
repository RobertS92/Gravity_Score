#!/usr/bin/env python3
"""
Test Pipeline Fix
==================
Validates that fixed pipeline produces same results as manual scorer
"""

import pandas as pd
import sys
import logging

# Set up logging to see debug messages
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

from gravity.data_pipeline import DataFlattener, DataImputer, GravityScoreCalculator

def main():
    print("\n" + "="*100)
    print("🧪 TESTING PIPELINE FIX - VALIDATION")
    print("="*100 + "\n")
    
    # Load data with social info
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'nfl_players_top100_social.csv'
    
    try:
        df = pd.read_csv(input_file)
        print(f"📂 Loaded {len(df)} players from {input_file}")
    except FileNotFoundError:
        print(f"❌ Error: {input_file} not found")
        return
    
    # Check if we have social data
    has_ig = df['instagram_followers'].notna().sum() if 'instagram_followers' in df.columns else 0
    has_contract = df['contract_value'].notna().sum() if 'contract_value' in df.columns else 0
    print(f"   Players with Instagram: {has_ig}")
    print(f"   Players with Contract: {has_contract}\n")
    
    # Run pipeline
    print("🔄 Running pipeline...")
    
    # Step 1: Check if data is already flat
    print("   1. Checking data structure...")
    if 'instagram_followers' in df.columns and 'contract_value' in df.columns:
        print(f"      ✅ Data is already flat ({len(df.columns)} columns)")
        df_flat = df.copy()  # Skip flattening - data is already flat
    else:
        print("   1. Flattening data...")
        flattener = DataFlattener()
        df_flat = flattener.flatten_dataframe(df)
        print(f"      ✅ Flattened to {len(df_flat.columns)} columns")
    
    # Check if social columns exist
    if 'instagram_followers' in df_flat.columns:
        ig_count = df_flat['instagram_followers'].notna().sum()
        print(f"      ✅ Instagram column found: {ig_count} values")
    else:
        print(f"      ⚠️  Instagram column NOT found")
        print(f"      Available columns: {[c for c in df_flat.columns if 'instagram' in c.lower()][:5]}")
    
    if 'contract_value' in df_flat.columns:
        contract_count = df_flat['contract_value'].notna().sum()
        print(f"      ✅ Contract column found: {contract_count} values")
    else:
        print(f"      ⚠️  Contract column NOT found")
        print(f"      Available columns: {[c for c in df_flat.columns if 'contract' in c.lower()][:5]}")
    
    # Step 2: Impute
    print("   2. Imputing data...")
    imputer = DataImputer()
    df_imputed = imputer.impute_data(df_flat)
    print(f"      ✅ Imputation complete")
    
    # Step 3: Score
    print("   3. Calculating Gravity Scores...")
    calculator = GravityScoreCalculator()
    df_scored = calculator.calculate_gravity_scores(df_imputed)
    print(f"      ✅ Scoring complete")
    
    # Check results for Patrick Mahomes
    print("\n" + "="*100)
    print("📊 VALIDATION RESULTS")
    print("="*100 + "\n")
    
    mahomes = df_scored[df_scored['player_name'] == 'Patrick Mahomes']
    if len(mahomes) > 0:
        row = mahomes.iloc[0]
        print("Patrick Mahomes Scores:")
        print(f"   Total Gravity Score: {row.get('gravity_score', 'N/A'):.2f}")
        print(f"   Performance: {row.get('gravity.performance_score', 'N/A'):.2f}")
        print(f"   Market: {row.get('gravity.market_score', 'N/A'):.2f}")
        print(f"   Social: {row.get('gravity.social_score', 'N/A'):.2f}")
        print(f"   Velocity: {row.get('gravity.velocity_score', 'N/A'):.2f}")
        print(f"   Risk: {row.get('gravity.risk_score', 'N/A'):.2f}")
        print()
        print("Expected (from manual scorer):")
        print("   Total: ~74.58")
        print("   Market: ~15.0")
        print("   Social: ~30.0")
        print()
        
        # Compare
        market_score = row.get('gravity.market_score', 0)
        social_score = row.get('gravity.social_score', 0)
        
        if market_score > 5 and social_score > 5:
            print("✅ SUCCESS: Market and Social scores are non-zero!")
            print(f"   Market: {market_score:.1f} (expected ~15)")
            print(f"   Social: {social_score:.1f} (expected ~30)")
            
            # Check if within 50% (acceptable for validation)
            if abs(market_score - 15) / 15 < 0.5 and abs(social_score - 30) / 30 < 0.5:
                print("✅ VALIDATION PASSED: Scores are within acceptable range")
            else:
                print("⚠️  VALIDATION WARNING: Scores are outside expected range but non-zero")
        else:
            print("❌ VALIDATION FAILED: Market or Social scores are still zero")
            print(f"   Market: {market_score:.1f}")
            print(f"   Social: {social_score:.1f}")
    else:
        print("⚠️  Patrick Mahomes not found in results")
    
    # Show top 10
    print("\n" + "="*100)
    print("🏆 TOP 10 PLAYERS (Pipeline Results)")
    print("="*100 + "\n")
    
    df_top = df_scored.sort_values('gravity_score', ascending=False).head(10)
    for i, (_, r) in enumerate(df_top.iterrows(), 1):
        name = r['player_name']
        total = r.get('gravity_score', 0)
        market = r.get('gravity.market_score', 0)
        social = r.get('gravity.social_score', 0)
        print(f"{i:2d}. {name:25s} {total:6.2f} (M:{market:5.1f} S:{social:5.1f})")
    
    # Save results
    output_file = 'final_scores/NFL_PIPELINE_TEST.csv'
    df_scored.to_csv(output_file, index=False)
    print(f"\n💾 Saved test results to {output_file}")
    print("="*100 + "\n")


if __name__ == '__main__':
    main()

