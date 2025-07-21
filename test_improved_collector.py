#!/usr/bin/env python3
"""
Test Improved Comprehensive Data Collector
Shows enhanced field coverage with real Wikipedia API integration
"""

from improved_comprehensive_collector import ImprovedComprehensiveCollector
import json

def test_improved_collector():
    """Test the improved comprehensive collector with real API calls."""
    
    print("🚀 TESTING IMPROVED COMPREHENSIVE DATA COLLECTOR")
    print("="*70)
    
    collector = ImprovedComprehensiveCollector()
    
    # Test with Patrick Mahomes
    print("🏈 Testing Enhanced Collection: Patrick Mahomes")
    print("-" * 50)
    
    try:
        # Run improved comprehensive collection
        data = collector.collect_comprehensive_data(
            player_name="Patrick Mahomes",
            team="chiefs", 
            position="QB"
        )
        
        # Analyze results by category
        categories = {
            'Basic Information': [
                'name', 'team', 'position', 'jersey_number', 'height', 'weight', 
                'age', 'birth_date', 'birth_place', 'college', 'high_school', 
                'experience', 'status'
            ],
            'Social Media': [
                'twitter_handle', 'instagram_handle', 'tiktok_handle', 'youtube_handle',
                'twitter_url', 'instagram_url', 'twitter_followers', 'instagram_followers'
            ],
            'Career Statistics': [
                'passing_yards', 'passing_tds', 'passing_rating', 'completion_percentage',
                'interceptions', 'rushing_yards', 'rushing_tds'
            ],
            'Financial': [
                'salary', 'contract_value', 'contract_years', 'current_salary', 
                'guaranteed_money', 'cap_hit'
            ],
            'Achievements': [
                'pro_bowls', 'all_pros', 'championships', 'awards', 'mvp_awards'
            ],
            'Draft Information': [
                'draft_year', 'draft_round', 'draft_pick', 'draft_team', 'overall_pick'
            ],
            'URLs and Sources': [
                'nfl_url', 'espn_url', 'wikipedia_url', 'data_sources'
            ]
        }
        
        total_filled = 0
        total_fields = 0
        
        print("📊 ENHANCED DATA COVERAGE ANALYSIS:")
        print("="*40)
        
        for category, fields in categories.items():
            filled_in_category = 0
            
            print(f"\n{category}:")
            for field in fields:
                value = data.get(field)
                total_fields += 1
                
                if value and str(value).strip() and str(value) != 'None':
                    if field == 'data_sources' and isinstance(value, list):
                        print(f"   ✓ {field}: {', '.join(value)}")
                    else:
                        print(f"   ✓ {field}: {value}")
                    filled_in_category += 1
                    total_filled += 1
                else:
                    print(f"   ✗ {field}: (empty)")
            
            coverage_pct = (filled_in_category / len(fields)) * 100
            print(f"   → Category Coverage: {filled_in_category}/{len(fields)} ({coverage_pct:.1f}%)")
        
        # Overall results
        overall_coverage = (total_filled / total_fields) * 100
        quality_score = data.get('data_quality', overall_coverage / 20)
        
        print(f"\n🎯 OVERALL RESULTS:")
        print(f"   Total fields filled: {total_filled}/{total_fields} ({overall_coverage:.1f}%)")
        print(f"   Data quality score: {quality_score}/5.0")
        print(f"   Data sources used: {len(data.get('data_sources', []))}")
        
        # Highlight key improvements
        key_improvements = []
        if data.get('birth_date'):
            key_improvements.append("Birth date extracted")
        if data.get('birth_place'):
            key_improvements.append("Birth place found")
        if data.get('wikipedia_url'):
            key_improvements.append("Wikipedia profile linked")
        if data.get('twitter_handle'):
            key_improvements.append("Social media discovered")
        if any(data.get(f) for f in ['passing_yards', 'rushing_yards', 'tackles']):
            key_improvements.append("Career statistics found")
            
        if key_improvements:
            print(f"\n✨ KEY IMPROVEMENTS:")
            for improvement in key_improvements:
                print(f"   • {improvement}")
        
        # Target analysis
        if overall_coverage >= 60:
            print(f"\n🎉 SUCCESS: Achieved {overall_coverage:.1f}% coverage (Target: 60%+)")
        elif overall_coverage >= 40:
            print(f"\n⚡ GOOD PROGRESS: {overall_coverage:.1f}% coverage (Target: 60%+)")
        else:
            print(f"\n⚠️  NEEDS IMPROVEMENT: {overall_coverage:.1f}% coverage (Target: 60%+)")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_improved_collector()