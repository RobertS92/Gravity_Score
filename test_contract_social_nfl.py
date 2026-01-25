#!/usr/bin/env python3
"""
Test Contract & Social Data Collection - NFL
============================================
Tests the improved contract and social media collectors with 5 players.
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path

# Add paths
script_dir = Path(__file__).parent.absolute()
parent_dir = script_dir.parent.absolute()
sys.path.insert(0, str(parent_dir))
sys.path.insert(0, str(script_dir / 'gravity'))

from gravity.nfl_scraper import NFLPlayerCollector
from gravity.scrape import get_direct_api
from tqdm import tqdm

# Configure logging to see collection details
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test players - mix of stars and regular players
TEST_PLAYERS = [
    {"name": "Patrick Mahomes", "team": "Kansas City Chiefs", "position": "QB"},
    {"name": "Travis Kelce", "team": "Kansas City Chiefs", "position": "TE"},
    {"name": "Josh Allen", "team": "Buffalo Bills", "position": "QB"},
    {"name": "Creed Humphrey", "team": "Kansas City Chiefs", "position": "C"},
    {"name": "Justin Jefferson", "team": "Minnesota Vikings", "position": "WR"}
]


def format_value(value, is_money=False):
    """Format values for display"""
    if value is None or value == 0:
        return "❌ Not found"
    if is_money:
        return f"${value:,.0f}"
    if isinstance(value, (int, float)) and value > 1000000:
        return f"{value/1000000:.2f}M"
    return str(value)


def test_player(collector, player_info):
    """Test data collection for one player"""
    print(f"\n{'='*70}")
    print(f"🏈 Testing: {player_info['name']} ({player_info['position']}, {player_info['team']})")
    print('='*70)
    
    try:
        player_data = collector.collect_player_data(
            player_info["name"],
            player_info["team"],
            player_info["position"]
        )
        
        if not player_data:
            print("❌ No data collected")
            return None
        
        # Check contract data
        identity = player_data.identity if hasattr(player_data, 'identity') else None
        contract_value = identity.contract_value if identity else None
        contract_years = identity.current_contract_length if identity else None
        
        # Check social data
        brand = player_data.brand if hasattr(player_data, 'brand') else None
        instagram = brand.instagram_followers if brand else None
        twitter = brand.twitter_followers if brand else None
        tiktok = brand.tiktok_followers if brand else None
        
        # Display results
        print("\n📊 COLLECTION RESULTS:")
        print(f"   Contract Value: {format_value(contract_value, is_money=True)}")
        print(f"   Contract Years: {format_value(contract_years)}")
        print(f"   Instagram: {format_value(instagram)}")
        print(f"   Twitter: {format_value(twitter)}")
        print(f"   TikTok: {format_value(tiktok)}")
        
        # Success indicators
        contract_success = contract_value is not None and contract_value > 0
        social_success = (instagram or twitter or tiktok) is not None
        
        print(f"\n✅ Contract Data: {'✅ FOUND' if contract_success else '❌ MISSING'}")
        print(f"✅ Social Data: {'✅ FOUND' if social_success else '❌ MISSING'}")
        
        return {
            'name': player_info['name'],
            'contract_value': contract_value,
            'contract_years': contract_years,
            'instagram': instagram,
            'twitter': twitter,
            'tiktok': tiktok,
            'contract_success': contract_success,
            'social_success': social_success
        }
        
    except Exception as e:
        logger.error(f"Error collecting {player_info['name']}: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None


def main():
    """Run test scrape"""
    print("\n" + "="*70)
    print("  🧪 CONTRACT & SOCIAL DATA COLLECTION TEST")
    print("  Testing improved scrapers with 5 NFL players")
    print("="*70)
    
    collector = NFLPlayerCollector(get_direct_api())
    results = []
    
    # Test each player
    for player_info in TEST_PLAYERS:
        result = test_player(collector, player_info)
        if result:
            results.append(result)
        # Small delay between players
        import time
        time.sleep(1)
    
    # Summary
    print("\n" + "="*70)
    print("  📊 TEST SUMMARY")
    print("="*70)
    
    if results:
        contract_count = sum(1 for r in results if r['contract_success'])
        social_count = sum(1 for r in results if r['social_success'])
        
        print(f"\n✅ Contract Data: {contract_count}/{len(results)} players ({contract_count*100//len(results)}%)")
        print(f"✅ Social Data: {social_count}/{len(results)} players ({social_count*100//len(results)}%)")
        
        print("\n📋 Detailed Results:")
        for r in results:
            print(f"\n   {r['name']}:")
            print(f"      Contract: {format_value(r['contract_value'], is_money=True)}")
            print(f"      Instagram: {format_value(r['instagram'])}")
            print(f"      Twitter: {format_value(r['twitter'])}")
        
        # Decision
        print("\n" + "="*70)
        if contract_count >= 3 and social_count >= 3:
            print("  ✅ TEST PASSED - Ready for full scrape!")
            print("="*70)
            print("\n🚀 Next step: Run full NFL scrape:")
            print("   python3 gravity/nfl_scraper.py all")
        else:
            print("  ⚠️  TEST PARTIAL - Some data missing")
            print("="*70)
            print("\n💡 Review the errors above and check:")
            print("   1. Is beautifulsoup4 installed? (pip install beautifulsoup4)")
            print("   2. Are there rate limiting issues?")
            print("   3. Check logs for specific errors")
    else:
        print("  ❌ TEST FAILED - No data collected")
        print("="*70)
    
    print()


if __name__ == '__main__':
    main()

