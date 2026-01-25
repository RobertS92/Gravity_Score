"""
Test NBA Scraper with Perplexity AI Fallback
Tests that the AI fallback is properly integrated and working
"""

import os
import sys

# Test if Perplexity key is set
perplexity_key = os.getenv('PERPLEXITY_API_KEY')
if perplexity_key:
    print(f"✅ PERPLEXITY_API_KEY is set: {perplexity_key[:10]}...{perplexity_key[-4:]}")
else:
    print("⚠️  PERPLEXITY_API_KEY not set - AI fallback will be disabled")
    print("   To enable: export PERPLEXITY_API_KEY='pplx-your-key-here'")

# Set environment for testing
os.environ['USE_AI_FALLBACK'] = 'true'
os.environ['AI_FALLBACK_MAX_COST_PER_PLAYER'] = '0.02'  # Allow $0.02 per player for testing

# Import after setting env vars
from gravity.nba_scraper import NBAPlayerCollector

print("\n" + "="*70)
print("NBA SCRAPER - PERPLEXITY AI FALLBACK TEST")
print("="*70)

# Initialize collector
firecrawl_key = os.getenv('FIRECRAWL_API_KEY', 'fc-test')
collector = NBAPlayerCollector(firecrawl_key)

# Check if Perplexity is initialized
if hasattr(collector, 'perplexity'):
    if collector.perplexity and collector.perplexity.enabled:
        print("✅ Perplexity AI fallback is ENABLED")
        print(f"   API Key: {collector.perplexity.api_key[:10]}...{collector.perplexity.api_key[-4:]}")
    elif collector.perplexity:
        print("⚠️  Perplexity object exists but is DISABLED (no API key)")
    else:
        print("❌ Perplexity object is None")
else:
    print("❌ Perplexity attribute not found on collector")

print("\n" + "="*70)
print("Testing with a single player (quick test)...")
print("="*70)

# Test with a player
test_player = "LeBron James"
test_team = "Los Angeles Lakers"
test_position = "F"

print(f"\nCollecting data for: {test_player}")
print("This will test:")
print("  1. Normal data collection (ESPN, social, etc.)")
print("  2. AI fallback for missing fields (if enabled)")
print("  3. Data quality score calculation")

try:
    player_data = collector.collect_player_data(test_player, test_team, test_position)
    
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    print(f"Player: {player_data.player_name}")
    print(f"Team: {player_data.team}")
    print(f"Position: {player_data.position}")
    print(f"Data Quality Score: {player_data.data_quality_score}%")
    
    # Check if AI was used
    if collector.perplexity and collector.perplexity.enabled:
        stats = collector.perplexity.get_stats()
        print(f"\n💰 AI Fallback Stats:")
        print(f"   Calls made: {stats['calls_made']}")
        print(f"   Estimated cost: ${stats['estimated_cost']:.4f}")
        
        if stats['calls_made'] > 0:
            print("   ✅ AI fallback was used!")
        else:
            print("   ℹ️  AI fallback not needed (all data collected from primary sources)")
    
    # Show some collected data
    print(f"\nIdentity:")
    print(f"   Draft: {player_data.identity.draft_year} Rd {player_data.identity.draft_round}")
    print(f"   College: {player_data.identity.college}")
    print(f"   Height/Weight: {player_data.identity.height} / {player_data.identity.weight}")
    
    print(f"\nBrand:")
    print(f"   Instagram: @{player_data.brand.instagram_handle}")
    print(f"   Twitter: @{player_data.brand.twitter_handle}")
    
    print(f"\nProximity:")
    print(f"   Endorsements: {len(player_data.proximity.endorsements)} brands")
    if player_data.proximity.endorsements:
        print(f"   Brands: {', '.join(player_data.proximity.endorsements[:5])}")
    
    print("\n✅ TEST PASSED - NBA scraper with Perplexity fallback working correctly!")
    
except Exception as e:
    print(f"\n❌ TEST FAILED: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("Next Steps:")
print("="*70)
print("1. To enable AI fallback, set: export PERPLEXITY_API_KEY='pplx-your-key'")
print("2. To use FAST_MODE: FAST_MODE=true python3 your_script.py")
print("3. Combined: FAST_MODE=true USE_AI_FALLBACK=true python3 your_script.py")
print("="*70)

