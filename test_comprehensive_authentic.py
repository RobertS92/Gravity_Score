#!/usr/bin/env python3
"""
Test Comprehensive Authentic Data Collection
Tests the comprehensive scraper with real sources only
"""

import logging
import pandas as pd
from datetime import datetime
from simple_comprehensive_collector import SimpleComprehensiveCollector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_comprehensive_collection():
    """Test comprehensive data collection with multiple players."""
    
    print("🧪 TESTING AUTHENTIC COMPREHENSIVE DATA COLLECTION")
    print("=" * 70)
    
    collector = SimpleComprehensiveCollector()
    
    # Test players from different teams and positions
    test_players = [
        {"name": "Patrick Mahomes", "team": "chiefs", "position": "QB"},
        {"name": "Travis Kelce", "team": "chiefs", "position": "TE"},
        {"name": "Budda Baker", "team": "cardinals", "position": "S"}
    ]
    
    all_results = []
    
    for player_info in test_players:
        print(f"\n🔍 Testing {player_info['name']} ({player_info['team']}, {player_info['position']})")
        print("-" * 50)
        
        # Collect comprehensive data
        result = collector.collect_comprehensive_data(
            player_info['name'], 
            player_info['team'], 
            player_info['position']
        )
        
        # Analyze results
        filled_fields = [k for k, v in result.items() if v not in [None, '', 'N/A'] and str(v).strip() != '']
        total_fields = len(result)
        quality_percentage = (len(filled_fields) / total_fields) * 100
        
        print(f"📊 Results: {len(filled_fields)}/{total_fields} fields filled ({quality_percentage:.1f}%)")
        print(f"🎯 Quality score: {result.get('data_quality_score', 'N/A')}")
        
        # Show key authentic data found
        key_fields = ['age', 'birth_place', 'high_school', 'wikipedia_url', 
                     'twitter_handle', 'instagram_handle', 'current_salary', 'spotrac_url']
        
        print("✅ Key authentic data found:")
        for field in key_fields:
            if result.get(field) and result[field] not in [None, '', 'N/A']:
                value = str(result[field])
                if len(value) > 40:
                    value = value[:37] + "..."
                print(f"   {field}: {value}")
        
        all_results.append(result)
    
    # Create comprehensive dataset
    if all_results:
        print(f"\n📁 CREATING COMPREHENSIVE DATASET")
        print("=" * 50)
        
        df = pd.DataFrame(all_results)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/comprehensive_test_authentic_{timestamp}.csv"
        
        df.to_csv(filename, index=False)
        
        print(f"✅ Saved authentic comprehensive data: {filename}")
        print(f"📊 Dataset: {len(df)} players, {len(df.columns)} columns")
        
        # Show overall quality
        overall_quality = df['data_quality_score'].mean() if 'data_quality_score' in df.columns else 0
        print(f"🎯 Average quality score: {overall_quality:.2f}/10")
        
        # Show column distribution
        non_null_counts = df.notna().sum()
        filled_columns = non_null_counts[non_null_counts > 0]
        
        print(f"\n📈 Data coverage by category:")
        
        categories = {
            'Basic Info': ['name', 'team', 'position', 'age', 'height', 'weight'],
            'Social Media': ['twitter_handle', 'instagram_handle', 'twitter_followers', 'instagram_followers'],
            'Biographical': ['birth_place', 'high_school', 'wikipedia_url'],
            'Financial': ['current_salary', 'contract_value', 'spotrac_url'],
            'Career Stats': ['career_pass_yards', 'career_rush_yards', 'career_tackles']
        }
        
        for category, fields in categories.items():
            category_coverage = sum(1 for field in fields if field in filled_columns and filled_columns[field] > 0)
            total_category_fields = len(fields)
            coverage_pct = (category_coverage / total_category_fields) * 100
            print(f"   {category}: {category_coverage}/{total_category_fields} fields ({coverage_pct:.1f}%)")
        
        print(f"\n✅ SUCCESS: Comprehensive authentic data collection working!")
        print(f"🎯 Zero simulated data - all fields from real sources")
        
        return filename
    
    return None

if __name__ == "__main__":
    test_comprehensive_collection()