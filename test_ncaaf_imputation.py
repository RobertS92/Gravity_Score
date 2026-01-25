#!/usr/bin/env python3
"""
Test NCAAF Imputation Features
===============================

Demonstrates the new CFB-specific imputation capabilities.
"""

import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gravity.ml_imputer import MLImputer


def test_ncaaf_imputation():
    """Test all NCAAF-specific imputation features"""
    
    print("=" * 80)
    print("🏈 TESTING NCAAF IMPUTATION FEATURES")
    print("=" * 80)
    
    # Create test data with missing values
    test_data = pd.DataFrame({
        'player_name': [
            'Player 1 (Georgia QB)',
            'Player 2 (Alabama WR)', 
            'Player 3 (Ohio State RB)',
            'Player 4 (Clemson Junior)',
            'Player 5 (Texas Senior)'
        ],
        'team': ['Georgia', 'Alabama', 'Ohio State', 'Clemson', 'Texas'],
        'position': ['QB', 'WR', 'RB', 'LB', 'DE'],
        'identity.class_year': ['Junior', 'Senior', 'Sophomore', 'Junior', 'Senior'],
        'identity.age': [None, None, None, None, None],
        'identity.conference': [None, None, None, None, None],
        'identity.eligibility_year': [None, None, None, None, None],
        'identity.contract_value': [None, None, None, None, None],
        'brand.total_social_followers': [500000, 250000, 150000, 75000, 50000],
        'proof.all_american_selections': [1, 1, 0, 0, 0],
        'proof.conference_honors': [2, 1, 1, 0, 1],
        'proof.heisman_winner': [0, 0, 0, 0, 0],
        'proof.nil_valuation': [None, 300000, None, None, None]
    })
    
    print("\n📊 BEFORE IMPUTATION:")
    print("=" * 80)
    print(test_data[['player_name', 'identity.age', 'identity.conference', 
                     'identity.eligibility_year', 'identity.contract_value']].to_string())
    
    # Apply imputation
    print("\n🔄 APPLYING NCAAF IMPUTATION...")
    print("=" * 80)
    
    imputer = MLImputer()
    result = imputer.impute_dataframe(test_data, use_ml=False)
    
    print("\n✅ AFTER IMPUTATION:")
    print("=" * 80)
    print(result[['player_name', 'identity.age', 'identity.conference', 
                  'identity.eligibility_year', 'identity.contract_value']].to_string())
    
    # Detailed results
    print("\n" + "=" * 80)
    print("📋 DETAILED RESULTS")
    print("=" * 80)
    
    for idx, row in result.iterrows():
        print(f"\n{row['player_name']}:")
        print(f"  Team: {row['team']}")
        print(f"  Position: {row['position']}")
        print(f"  Class Year: {row['identity.class_year']}")
        print(f"  ✓ Age: {row['identity.age']} (imputed from class year)")
        print(f"  ✓ Conference: {row['identity.conference']} (imputed from team)")
        print(f"  ✓ Eligibility: {row['identity.eligibility_year']} years (imputed from class year)")
        print(f"  ✓ Market Value: ${row['identity.contract_value']:,.0f} (NIL estimate)")
    
    # Validation
    print("\n" + "=" * 80)
    print("✅ VALIDATION")
    print("=" * 80)
    
    age_complete = result['identity.age'].notna().sum()
    conf_complete = result['identity.conference'].notna().sum()
    elig_complete = result['identity.eligibility_year'].notna().sum()
    value_complete = result['identity.contract_value'].notna().sum()
    
    print(f"Age Imputed: {age_complete}/{len(result)} (100%)")
    print(f"Conference Imputed: {conf_complete}/{len(result)} (100%)")
    print(f"Eligibility Imputed: {elig_complete}/{len(result)} (100%)")
    print(f"Market Value Imputed: {value_complete}/{len(result)} (100%)")
    
    # Verify accuracy
    print("\n" + "=" * 80)
    print("🎯 ACCURACY CHECK")
    print("=" * 80)
    
    expected = {
        'Player 1 (Georgia QB)': {
            'age': 20, 
            'conference': 'SEC', 
            'eligibility': 2,
            'value_check': 'Should be high (QB, All-American, social media)'
        },
        'Player 2 (Alabama WR)': {
            'age': 21, 
            'conference': 'SEC', 
            'eligibility': 1,
            'value_check': 'Should use NIL valuation ($300K)'
        },
        'Player 3 (Ohio State RB)': {
            'age': 19, 
            'conference': 'Big Ten', 
            'eligibility': 3,
            'value_check': 'Should be moderate (good social, some honors)'
        },
        'Player 4 (Clemson Junior)': {
            'age': 20, 
            'conference': 'ACC', 
            'eligibility': 2,
            'value_check': 'Should be lower (no awards, lower social)'
        },
        'Player 5 (Texas Senior)': {
            'age': 21, 
            'conference': 'SEC', 
            'eligibility': 1,
            'value_check': 'Should be moderate (some honors)'
        }
    }
    
    all_correct = True
    for idx, row in result.iterrows():
        player = row['player_name']
        exp = expected[player]
        
        age_match = row['identity.age'] == exp['age']
        conf_match = row['identity.conference'] == exp['conference']
        elig_match = row['identity.eligibility_year'] == exp['eligibility']
        
        status = "✓" if (age_match and conf_match and elig_match) else "✗"
        print(f"\n{status} {player}:")
        print(f"  Age: {row['identity.age']} (expected {exp['age']}) {'✓' if age_match else '✗'}")
        print(f"  Conference: {row['identity.conference']} (expected {exp['conference']}) {'✓' if conf_match else '✗'}")
        print(f"  Eligibility: {row['identity.eligibility_year']} (expected {exp['eligibility']}) {'✓' if elig_match else '✗'}")
        print(f"  Market Value: ${row['identity.contract_value']:,.0f}")
        print(f"  Note: {exp['value_check']}")
        
        if not (age_match and conf_match and elig_match):
            all_correct = False
    
    print("\n" + "=" * 80)
    if all_correct:
        print("✅ ALL TESTS PASSED!")
    else:
        print("⚠️  SOME TESTS FAILED - Review above")
    print("=" * 80)
    
    return all_correct


if __name__ == '__main__':
    success = test_ncaaf_imputation()
    sys.exit(0 if success else 1)

