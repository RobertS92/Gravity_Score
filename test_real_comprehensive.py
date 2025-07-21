#!/usr/bin/env python3
"""
Test Real Comprehensive Data Collection
Proves that we can actually collect 70+ fields with social media, stats, contracts
"""

import logging
from enhanced_comprehensive_collector import EnhancedComprehensiveCollector
from enhanced_db_manager import EnhancedDatabaseManager
from gravity_score_system import GravityScoreCalculator

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(name)s: %(message)s')
logger = logging.getLogger(__name__)

def test_real_comprehensive_collection():
    """Test actual comprehensive data collection on famous players."""
    
    print("🔍 TESTING REAL COMPREHENSIVE DATA COLLECTION")
    print("="*60)
    
    # Initialize systems
    collector = EnhancedComprehensiveCollector()
    db_manager = EnhancedDatabaseManager()
    gravity_calc = GravityScoreCalculator()
    
    # Test with well-known players who should have lots of data
    test_players = [
        {"name": "Patrick Mahomes", "team": "chiefs", "position": "QB"},
        {"name": "Josh Allen", "team": "bills", "position": "QB"},
        {"name": "Travis Kelce", "team": "chiefs", "position": "TE"}
    ]
    
    for player in test_players:
        print(f"\n🏈 Testing: {player['name']}")
        print("-" * 40)
        
        try:
            # Run comprehensive collection
            comprehensive_data = collector.collect_comprehensive_data(
                player_name=player['name'],
                team=player['team'],
                position=player['position']
            )
            
            # Count filled fields
            filled_fields = sum(1 for v in comprehensive_data.values() 
                              if v is not None and str(v).strip() != '' and str(v) != 'None')
            total_fields = len(comprehensive_data)
            
            # Check specific social media fields
            social_media = {
                'Twitter': comprehensive_data.get('twitter_handle'),
                'Instagram': comprehensive_data.get('instagram_handle'),
                'TikTok': comprehensive_data.get('tiktok_handle'),
                'YouTube': comprehensive_data.get('youtube_handle')
            }
            
            social_count = sum(1 for v in social_media.values() 
                             if v is not None and str(v).strip() != '' and str(v) != 'None')
            
            # Calculate gravity score
            gravity_scores = gravity_calc.calculate_gravity_score(comprehensive_data)
            
            print(f"✅ Fields populated: {filled_fields}/{total_fields} ({filled_fields/total_fields*100:.1f}%)")
            print(f"📱 Social media accounts found: {social_count}/4")
            print(f"⭐ Gravity score: {gravity_scores.get('total_gravity', 'N/A')}/100")
            
            # Show social media details
            for platform, handle in social_media.items():
                if handle:
                    followers_key = f"{platform.lower()}_followers"
                    followers = comprehensive_data.get(followers_key, 'N/A')
                    print(f"   {platform}: @{handle} ({followers} followers)")
            
            # Show key stats
            key_stats = {
                'Age': comprehensive_data.get('age'),
                'College': comprehensive_data.get('college'),
                'Experience': comprehensive_data.get('experience'),
                'Contract Value': comprehensive_data.get('contract_value'),
                'Awards': comprehensive_data.get('awards')
            }
            
            print("📊 Key Data:")
            for stat, value in key_stats.items():
                if value:
                    print(f"   {stat}: {value}")
                    
        except Exception as e:
            print(f"❌ Error collecting data for {player['name']}: {e}")
    
    print(f"\n🎯 CONCLUSION:")
    print("This test demonstrates whether we can actually collect comprehensive")
    print("social media, statistical, and biographical data for NFL players.")

if __name__ == "__main__":
    test_real_comprehensive_collection()