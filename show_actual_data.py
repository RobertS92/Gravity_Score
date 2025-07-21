#!/usr/bin/env python3
"""
Show Actual Comprehensive Data Collection
Demonstrates real data collection without errors to prove what's working
"""

from enhanced_comprehensive_collector import EnhancedComprehensiveCollector
import json

def show_comprehensive_data():
    """Show actual comprehensive data collection results."""
    
    print("🔍 REAL COMPREHENSIVE DATA COLLECTION TEST")
    print("="*60)
    
    collector = EnhancedComprehensiveCollector()
    
    # Test with Patrick Mahomes
    print("🏈 Testing: Patrick Mahomes")
    print("-" * 40)
    
    try:
        # Run comprehensive collection
        data = collector.collect_comprehensive_data(
            player_name="Patrick Mahomes",
            team="chiefs", 
            position="QB"
        )
        
        # Count fields with actual data
        filled_fields = 0
        total_fields = len(data)
        
        print("📊 COLLECTED DATA FIELDS:")
        print("="*30)
        
        # Group fields by category
        categories = {
            'Basic Info': ['name', 'team', 'position', 'jersey_number', 'height', 'weight', 'age', 'birth_date', 'birth_place'],
            'Education/Career': ['college', 'high_school', 'experience', 'status'],
            'Social Media': ['twitter_handle', 'instagram_handle', 'tiktok_handle', 'youtube_handle', 'facebook_handle'],
            'Followers': ['twitter_followers', 'instagram_followers', 'tiktok_followers', 'youtube_subscribers'],
            'Statistics': ['passing_yards', 'passing_tds', 'rushing_yards', 'receptions', 'tackles'],
            'Financial': ['salary', 'contract_value', 'contract_years', 'current_salary', 'guaranteed_money'],
            'Achievements': ['pro_bowls', 'all_pros', 'championships', 'awards'],
            'Draft': ['draft_year', 'draft_round', 'draft_pick', 'draft_team']
        }
        
        for category, fields in categories.items():
            print(f"\n{category}:")
            category_filled = 0
            for field in fields:
                value = data.get(field)
                if value and str(value).strip() and str(value) != 'None':
                    print(f"   ✓ {field}: {value}")
                    filled_fields += 1
                    category_filled += 1
                else:
                    print(f"   ✗ {field}: (empty)")
            
            print(f"   → {category_filled}/{len(fields)} fields filled")
        
        print(f"\n🎯 SUMMARY:")
        print(f"   Total fields filled: {filled_fields}/{total_fields} ({filled_fields/total_fields*100:.1f}%)")
        print(f"   Data quality score: {data.get('data_quality', 'N/A')}/5.0")
        
        # Show if any social media was found
        social_found = any(data.get(f) for f in ['twitter_handle', 'instagram_handle', 'tiktok_handle'])
        print(f"   Social media found: {'Yes' if social_found else 'No'}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    show_comprehensive_data()