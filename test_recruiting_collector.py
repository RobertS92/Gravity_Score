#!/usr/bin/env python3
"""
Test script for the Recruiting Data Collector
Demonstrates collecting college recruiting data for NFL/NBA players
"""

import sys
import os
import logging

# Add gravity to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gravity'))

from gravity.recruiting_collector import RecruitingCollector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_nfl_players():
    """Test recruiting data collection for NFL players"""
    print("\n" + "="*80)
    print("🏈 NFL PLAYERS - RECRUITING DATA TEST")
    print("="*80)
    
    collector = RecruitingCollector()
    
    # Test with various NFL stars
    test_players = [
        # Recent high draft picks
        ("Trevor Lawrence", "Clemson", 2021),
        ("Justin Fields", "Ohio State", 2021),
        ("Mac Jones", "Alabama", 2021),
        
        # Elite QBs
        ("Patrick Mahomes", "Texas Tech", 2017),
        ("Josh Allen", "Wyoming", 2018),
        
        # Star WRs
        ("Justin Jefferson", "LSU", 2020),
        ("CeeDee Lamb", "Oklahoma", 2020),
        
        # Star defensive players
        ("Micah Parsons", "Penn State", 2021),
        ("Nick Bosa", "Ohio State", 2019),
    ]
    
    results = []
    
    for player_name, college, draft_year in test_players:
        print(f"\n{'─'*80}")
        print(f"Player: {player_name} | College: {college} | Draft: {draft_year}")
        print(f"{'─'*80}")
        
        data = collector.collect_recruiting_data(
            player_name=player_name,
            college=college,
            draft_year=draft_year,
            sport='nfl'
        )
        
        # Display results
        if any(v is not None for k, v in data.items() if k != 'recruiting_source'):
            print(f"✅ FOUND RECRUITING DATA:")
            print(f"   Stars: {data.get('recruiting_stars', 'N/A')}★")
            print(f"   National Rank: #{data.get('recruiting_ranking', 'N/A')}")
            print(f"   Position Rank: #{data.get('recruiting_position_ranking', 'N/A')}")
            print(f"   State Rank: #{data.get('recruiting_state_ranking', 'N/A')}")
            print(f"   Recruiting Class: {data.get('recruiting_class', 'N/A')}")
            print(f"   Eligibility Year: {data.get('eligibility_year', 'N/A')}")
            print(f"   Source: {data.get('recruiting_source', 'N/A')}")
            results.append((player_name, True, data))
        else:
            print(f"❌ No recruiting data found")
            results.append((player_name, False, None))
    
    # Summary
    print("\n" + "="*80)
    print("📊 NFL RECRUITING DATA SUMMARY")
    print("="*80)
    found = sum(1 for _, success, _ in results if success)
    total = len(results)
    print(f"Success Rate: {found}/{total} ({100*found//total}%)")
    
    print("\n✅ Players with data:")
    for name, success, data in results:
        if success:
            stars = data.get('recruiting_stars', '?')
            rank = data.get('recruiting_ranking', '?')
            print(f"   • {name}: {stars}★, Rank #{rank}")
    
    print("\n❌ Players without data:")
    for name, success, _ in results:
        if not success:
            print(f"   • {name}")


def test_nba_players():
    """Test recruiting data collection for NBA players"""
    print("\n" + "="*80)
    print("🏀 NBA PLAYERS - RECRUITING DATA TEST")
    print("="*80)
    
    collector = RecruitingCollector()
    
    # Test with various NBA stars
    test_players = [
        # Recent #1 picks
        ("Victor Wembanyama", None, 2023),  # International - likely no data
        ("Chet Holmgren", "Gonzaga", 2022),
        ("Cade Cunningham", "Oklahoma State", 2021),
        ("Anthony Edwards", "Georgia", 2020),
        
        # Elite college players
        ("Zion Williamson", "Duke", 2019),
        ("RJ Barrett", "Duke", 2019),
        ("Ja Morant", "Murray State", 2019),
        
        # Recent stars
        ("Paolo Banchero", "Duke", 2022),
        ("Jalen Green", None, 2021),  # G-League Ignite - might not have data
    ]
    
    results = []
    
    for player_name, college, draft_year in test_players:
        print(f"\n{'─'*80}")
        college_str = college if college else "No College"
        print(f"Player: {player_name} | College: {college_str} | Draft: {draft_year}")
        print(f"{'─'*80}")
        
        data = collector.collect_recruiting_data(
            player_name=player_name,
            college=college,
            draft_year=draft_year,
            sport='nba'
        )
        
        # Display results
        if any(v is not None for k, v in data.items() if k != 'recruiting_source'):
            print(f"✅ FOUND RECRUITING DATA:")
            print(f"   Stars: {data.get('recruiting_stars', 'N/A')}★")
            print(f"   National Rank: #{data.get('recruiting_ranking', 'N/A')}")
            print(f"   Position Rank: #{data.get('recruiting_position_ranking', 'N/A')}")
            print(f"   State Rank: #{data.get('recruiting_state_ranking', 'N/A')}")
            print(f"   Recruiting Class: {data.get('recruiting_class', 'N/A')}")
            print(f"   Eligibility Year: {data.get('eligibility_year', 'N/A')}")
            print(f"   Source: {data.get('recruiting_source', 'N/A')}")
            results.append((player_name, True, data))
        else:
            print(f"❌ No recruiting data found")
            results.append((player_name, False, None))
    
    # Summary
    print("\n" + "="*80)
    print("📊 NBA RECRUITING DATA SUMMARY")
    print("="*80)
    found = sum(1 for _, success, _ in results if success)
    total = len(results)
    print(f"Success Rate: {found}/{total} ({100*found//total if total > 0 else 0}%)")
    
    print("\n✅ Players with data:")
    for name, success, data in results:
        if success:
            stars = data.get('recruiting_stars', '?')
            rank = data.get('recruiting_ranking', '?')
            print(f"   • {name}: {stars}★, Rank #{rank}")
    
    print("\n❌ Players without data:")
    for name, success, _ in results:
        if not success:
            print(f"   • {name}")


def main():
    """Run all tests"""
    print("\n" + "🎓"*40)
    print("RECRUITING DATA COLLECTOR - COMPREHENSIVE TEST")
    print("🎓"*40)
    
    print("\nThis test will:")
    print("  1. Scrape 247Sports for recruiting rankings")
    print("  2. Fall back to Rivals if 247Sports fails")
    print("  3. Fall back to ESPN Recruiting if both fail")
    print("  4. Show star ratings, national rankings, position rankings, etc.")
    
    try:
        # Test NFL
        test_nfl_players()
        
        # Test NBA
        test_nba_players()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETE")
        print("="*80)
        print("\nNote: Some players may not have recruiting data if:")
        print("  • They attended college before 2010 (limited historical data)")
        print("  • They are international players who didn't attend U.S. college")
        print("  • They went straight to pros (no college)")
        print("  • Their name has changed or is spelled differently")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

