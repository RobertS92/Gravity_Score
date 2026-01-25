#!/usr/bin/env python3
"""
Debug Scoring Calculation
========================
Test the scoring calculation step by step to find the bug
"""

import pandas as pd
import sys
import logging

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

from gravity.data_pipeline import DataFlattener, DataImputer, GravityScoreCalculator

def main():
    print("\n" + "="*100)
    print("🐛 DEBUGGING SCORING CALCULATION")
    print("="*100 + "\n")
    
    # Load data
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'nfl_players_with_social.csv'
    df = pd.read_csv(input_file)
    print(f"📂 Loaded {len(df)} players from {input_file}\n")
    
    # Check Mahomes data
    mahomes = df[df['player_name'] == 'Patrick Mahomes']
    if len(mahomes) > 0:
        row = mahomes.iloc[0]
        print("Patrick Mahomes Data:")
        print(f"   contract_value: {row.get('contract_value', 'N/A')}")
        print(f"   instagram_followers: {row.get('instagram_followers', 'N/A')}")
        print(f"   twitter_followers: {row.get('twitter_followers', 'N/A')}")
        print()
    
    # Test column finding
    print("Testing _find_col method:")
    calculator = GravityScoreCalculator()
    
    contract_col = calculator._find_col(df, ['contract_value', 'identity.contract_value', 'current_contract_length'])
    print(f"   Contract column: {contract_col}")
    
    instagram_col = calculator._find_col(df, ['instagram_followers', 'brand.instagram_followers', 'instagram'])
    print(f"   Instagram column: {instagram_col}")
    
    twitter_col = calculator._find_col(df, ['twitter_followers', 'brand.twitter_followers', 'twitter'])
    print(f"   Twitter column: {twitter_col}")
    print()
    
    # Test normalization
    if contract_col:
        contract_data = df[contract_col].fillna(0)
        print(f"Contract data stats:")
        print(f"   Non-null: {contract_data.notna().sum()}")
        print(f"   Max: {contract_data.max():,.0f}")
        print(f"   Min: {contract_data.min():,.0f}")
        
        normalized = calculator._normalize(contract_data, 0, 60000000)
        print(f"   Normalized max: {normalized.max():.4f}")
        print(f"   Normalized min: {normalized.min():.4f}")
        
        if len(mahomes) > 0:
            mahomes_idx = mahomes.index[0]
            mahomes_contract = contract_data.iloc[mahomes_idx]
            mahomes_norm = normalized.iloc[mahomes_idx]
            print(f"   Mahomes contract: {mahomes_contract:,.0f}")
            print(f"   Mahomes normalized: {mahomes_norm:.4f}")
        print()
    
    if instagram_col:
        ig_data = df[instagram_col].fillna(0)
        print(f"Instagram data stats:")
        print(f"   Non-null: {ig_data.notna().sum()}")
        print(f"   Max: {ig_data.max():,.0f}")
        print(f"   Min: {ig_data.min():,.0f}")
        
        normalized = calculator._normalize(ig_data, 0, 20000000)
        print(f"   Normalized max: {normalized.max():.4f}")
        print(f"   Normalized min: {normalized.min():.4f}")
        
        if len(mahomes) > 0:
            mahomes_idx = mahomes.index[0]
            mahomes_ig = ig_data.iloc[mahomes_idx]
            mahomes_norm = normalized.iloc[mahomes_idx]
            print(f"   Mahomes Instagram: {mahomes_ig:,.0f}")
            print(f"   Mahomes normalized: {mahomes_norm:.4f}")
        print()
    
    # Test actual scoring
    print("Testing actual scoring methods:")
    
    # Flatten if needed
    if 'instagram_followers' in df.columns:
        df_flat = df.copy()
    else:
        flattener = DataFlattener()
        df_flat = flattener.flatten_dataframe(df)
    
    # Impute
    imputer = DataImputer()
    df_imputed = imputer.impute_data(df_flat)
    
    # Calculate market score
    print("   Calculating market score...")
    market_scores = calculator._calculate_market_score(df_imputed)
    print(f"   Market score range: {market_scores.min():.2f} to {market_scores.max():.2f}")
    if len(mahomes) > 0:
        mahomes_idx = mahomes.index[0]
        print(f"   Mahomes market score: {market_scores.iloc[mahomes_idx]:.2f}")
    print()
    
    # Calculate social score
    print("   Calculating social score...")
    social_scores = calculator._calculate_social_score(df_imputed)
    print(f"   Social score range: {social_scores.min():.2f} to {social_scores.max():.2f}")
    if len(mahomes) > 0:
        mahomes_idx = mahomes.index[0]
        print(f"   Mahomes social score: {social_scores.iloc[mahomes_idx]:.2f}")
    print()
    
    # Calculate performance score
    print("   Calculating performance score...")
    perf_scores = calculator._calculate_performance_score(df_imputed)
    print(f"   Performance score range: {perf_scores.min():.2f} to {perf_scores.max():.2f}")
    if len(mahomes) > 0:
        mahomes_idx = mahomes.index[0]
        print(f"   Mahomes performance score: {perf_scores.iloc[mahomes_idx]:.2f}")
    print()
    
    # Full calculation
    print("   Calculating full gravity scores...")
    df_scored = calculator.calculate_gravity_scores(df_imputed)
    
    if len(mahomes) > 0:
        mahomes_scored = df_scored[df_scored['player_name'] == 'Patrick Mahomes']
        if len(mahomes_scored) > 0:
            row = mahomes_scored.iloc[0]
            print("\n" + "="*100)
            print("📊 FINAL RESULTS FOR PATRICK MAHOMES")
            print("="*100)
            print(f"   Total Gravity Score: {row.get('gravity_score', 'N/A')}")
            print(f"   Performance: {row.get('gravity.performance_score', 'N/A')}")
            print(f"   Market: {row.get('gravity.market_score', 'N/A')}")
            print(f"   Social: {row.get('gravity.social_score', 'N/A')}")
            print(f"   Velocity: {row.get('gravity.velocity_score', 'N/A')}")
            print(f"   Risk: {row.get('gravity.risk_score', 'N/A')}")
            print("="*100 + "\n")


if __name__ == '__main__':
    main()

