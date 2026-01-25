#!/usr/bin/env python3
"""
Test NBA scraper's new features: gamelog and endorsements
Tests with 3-5 notable players with known endorsements
"""

import os
import sys
from pathlib import Path

# Add to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from gravity.nba_scraper import NBAPlayerCollector

def test_nba_features():
    """Test NBA scraper with players known to have endorsements and active games"""
    
    # Test players with known endorsements and active 2025-26 season
    test_players = [
        {"name": "LeBron James", "team": "Los Angeles Lakers", "position": "SF"},
        {"name": "Stephen Curry", "team": "Golden State Warriors", "position": "PG"},
        {"name": "Giannis Antetokounmpo", "team": "Milwaukee Bucks", "position": "PF"},
        {"name": "Luka Dončić", "team": "Dallas Mavericks", "position": "PG"},
        {"name": "Kevin Durant", "team": "Phoenix Suns", "position": "PF"},
    ]
    
    print("\n" + "="*70)
    print("NBA SCRAPER - GAMELOG & ENDORSEMENTS TEST")
    print("="*70)
    print(f"Testing {len(test_players)} players\n")
    
    # Initialize collector
    api_key = os.getenv("FIRECRAWL_API_KEY", "fc-NONE")
    collector = NBAPlayerCollector(api_key)
    
    results = []
    
    for i, player_info in enumerate(test_players, 1):
        print(f"\n[{i}/{len(test_players)}] Testing: {player_info['name']}")
        print("-" * 70)
        
        try:
            # Collect data
            player_data = collector.collect_player_data(
                player_info['name'],
                player_info['team'],
                player_info['position']
            )
            
            # Verify gamelog data
            gamelog_found = False
            if hasattr(player_data.proof, 'current_season_gamelog'):
                games = player_data.proof.current_season_gamelog
                if games and len(games) > 0:
                    gamelog_found = True
                    print(f"✅ GAMELOG: {len(games)} games in current season")
                    print(f"   Recent games: {len(player_data.proof.recent_games)}")
                    
                    # Show sample game stats
                    if games:
                        latest_game = games[-1]
                        print(f"   Latest game: {latest_game.get('opponent', 'N/A')} - {latest_game.get('result', 'N/A')}")
            
            if not gamelog_found:
                print(f"❌ GAMELOG: No current season games found")
            
            # Verify historical gamelog
            if hasattr(player_data.proof, 'gamelog_by_year'):
                historical = player_data.proof.gamelog_by_year
                if historical:
                    total_games = sum(len(games) for games in historical.values())
                    print(f"✅ HISTORICAL: {total_games} games across {len(historical)} seasons")
                else:
                    print(f"⚠️  HISTORICAL: No historical gamelog data")
            
            # Verify endorsements
            endorsements_found = False
            if hasattr(player_data, 'proximity') and player_data.proximity:
                endorsements = player_data.proximity.endorsements
                if endorsements and len(endorsements) > 0:
                    endorsements_found = True
                    print(f"✅ ENDORSEMENTS: {len(endorsements)} brands")
                    print(f"   Brands: {', '.join(endorsements[:5])}")
                    
                    if player_data.proximity.endorsement_value:
                        print(f"   Estimated value: ${player_data.proximity.endorsement_value:,.0f}")
            
            if not endorsements_found:
                print(f"❌ ENDORSEMENTS: No endorsements found")
            
            # Verify current season stats
            current_stats = player_data.proof.current_season_stats
            if current_stats:
                print(f"✅ CURRENT SEASON STATS: {len(current_stats)} stat categories")
            else:
                print(f"❌ CURRENT SEASON STATS: No stats found")
            
            results.append({
                'player': player_info['name'],
                'gamelog': gamelog_found,
                'endorsements': endorsements_found,
                'current_stats': bool(current_stats)
            })
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append({
                'player': player_info['name'],
                'gamelog': False,
                'endorsements': False,
                'current_stats': False,
                'error': str(e)
            })
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    gamelog_success = sum(1 for r in results if r['gamelog'])
    endorsements_success = sum(1 for r in results if r['endorsements'])
    stats_success = sum(1 for r in results if r['current_stats'])
    
    print(f"Gamelog collection: {gamelog_success}/{len(results)} players")
    print(f"Endorsements collection: {endorsements_success}/{len(results)} players")
    print(f"Current season stats: {stats_success}/{len(results)} players")
    
    if gamelog_success == len(results) and endorsements_success >= len(results) // 2:
        print("\n✅ TEST PASSED - NBA scraper now matches NFL capabilities")
    else:
        print("\n⚠️  TEST INCOMPLETE - Some features may need adjustment")
    
    return results

if __name__ == "__main__":
    test_nba_features()

