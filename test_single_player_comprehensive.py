#!/usr/bin/env python3
"""
Test comprehensive data collection for a single player with detailed field logging.
"""

import logging
from simple_comprehensive_collector import SimpleComprehensiveCollector

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_single_player_comprehensive():
    """Test comprehensive collection for a single high-profile player."""
    
    print("=== COMPREHENSIVE DATA COLLECTION TEST ===")
    print("Testing with: Saquon Barkley (Eagles)")
    print("This will show detailed field collection from each source")
    print("-" * 60)
    
    # Initialize collector
    collector = SimpleComprehensiveCollector()
    
    # Test with a well-known player who should have good data coverage
    player_name = "Saquon Barkley"
    team = "eagles"
    
    print(f"Starting comprehensive collection for {player_name}...")
    
    # Collect comprehensive data using the correct method
    enhanced_data = collector.collect_comprehensive_data(
        player_name, team, position="RB"
    )
    
    print("\n=== COLLECTION RESULTS ===")
    print(f"Player: {enhanced_data.get('name', 'Unknown')}")
    print(f"Team: {enhanced_data.get('team', 'Unknown')}")
    print(f"Position: {enhanced_data.get('position', 'Unknown')}")
    print(f"Total fields collected: {len(enhanced_data)}")
    print(f"Data quality score: {enhanced_data.get('data_quality_score', 0)}")
    print(f"Data sources used: {enhanced_data.get('data_sources', [])}")
    
    print("\n=== DETAILED FIELD BREAKDOWN ===")
    
    # Basic player info
    basic_fields = ['name', 'team', 'position', 'jersey_number', 'height', 'weight', 'age', 'college']
    print("\n📋 Basic Player Info:")
    for field in basic_fields:
        value = enhanced_data.get(field)
        if value:
            print(f"  ✅ {field}: {value}")
        else:
            print(f"  ❌ {field}: Not found")
    
    # Social media fields
    social_fields = ['twitter_handle', 'instagram_handle', 'tiktok_handle', 'youtube_handle',
                    'twitter_followers', 'instagram_followers', 'tiktok_followers', 'youtube_subscribers']
    print("\n📱 Social Media Data:")
    for field in social_fields:
        value = enhanced_data.get(field)
        if value:
            print(f"  ✅ {field}: {value}")
        else:
            print(f"  ❌ {field}: Not found")
    
    # Career/Performance fields
    career_fields = ['career_stats', 'pro_bowls', 'all_pro_selections', 'super_bowl_wins', 
                    'rookie_year', 'years_experience', 'contract_value', 'career_earnings']
    print("\n🏆 Career & Performance:")
    for field in career_fields:
        value = enhanced_data.get(field)
        if value:
            print(f"  ✅ {field}: {value}")
        else:
            print(f"  ❌ {field}: Not found")
    
    # Wikipedia/Bio fields
    bio_fields = ['wikipedia_url', 'birth_date', 'birth_place', 'education', 'biography']
    print("\n📖 Biographical Data:")
    for field in bio_fields:
        value = enhanced_data.get(field)
        if value:
            if len(str(value)) > 100:
                print(f"  ✅ {field}: {str(value)[:100]}...")
            else:
                print(f"  ✅ {field}: {value}")
        else:
            print(f"  ❌ {field}: Not found")
    
    # Show all collected fields
    print(f"\n=== ALL {len(enhanced_data)} COLLECTED FIELDS ===")
    for i, (key, value) in enumerate(enhanced_data.items(), 1):
        if value and str(value).strip():
            if len(str(value)) > 50:
                print(f"{i:2d}. {key}: {str(value)[:50]}...")
            else:
                print(f"{i:2d}. {key}: {value}")
        else:
            print(f"{i:2d}. {key}: [Empty]")
    
    print("\n=== SUMMARY ===")
    filled_fields = sum(1 for v in enhanced_data.values() if v and str(v).strip())
    print(f"Fields with data: {filled_fields}/{len(enhanced_data)}")
    print(f"Data completeness: {(filled_fields/len(enhanced_data)*100):.1f}%")
    
    return enhanced_data

if __name__ == "__main__":
    result = test_single_player_comprehensive()