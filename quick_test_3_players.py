#!/usr/bin/env python3
"""
Quick Test - 3 Players Per Sport
=================================

Fast validation script that scrapes just 3 notable players from each sport.
Perfect for quick smoke tests and validation after changes.

Usage:
    python quick_test_3_players.py [sport]
    
    sport (optional): nfl, nba, cfb, or all (default: all)

Examples:
    python quick_test_3_players.py          # Test all sports (9 players total)
    python quick_test_3_players.py nfl      # Test only NFL (3 players)
    python quick_test_3_players.py nba      # Test only NBA (3 players)
"""

import sys
import os
import logging
from datetime import datetime
from typing import List, Dict, Any
import pandas as pd
from dataclasses import fields, asdict

# Add gravity to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gravity'))

from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# TEST PLAYER SELECTIONS (3 notable players per sport)
# ============================================================================

TEST_PLAYERS = {
    "NFL": [
        {"name": "Patrick Mahomes", "team": "Kansas City Chiefs", "position": "QB"},
        {"name": "Travis Kelce", "team": "Kansas City Chiefs", "position": "TE"},
        {"name": "Josh Allen", "team": "Buffalo Bills", "position": "QB"}
    ],
    "NBA": [
        {"name": "LeBron James", "team": "Los Angeles Lakers", "position": "SF"},
        {"name": "Stephen Curry", "team": "Golden State Warriors", "position": "PG"},
        {"name": "Kevin Durant", "team": "Phoenix Suns", "position": "PF"}
    ],
    "CFB": [
        {"name": "Caleb Williams", "team": "USC", "position": "QB"},
        {"name": "Marvin Harrison Jr.", "team": "Ohio State", "position": "WR"},
        {"name": "Bo Nix", "team": "Oregon", "position": "QB"}
    ]
}


def _is_empty(value: Any) -> bool:
    """Check if a value is considered empty"""
    if value is None:
        return True
    if value == "":
        return True
    if value == 0:
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def validate_player_data(player_data, player_name: str, sport: str) -> Dict:
    """
    Quick validation of key fields
    
    Returns dict with validation results
    """
    validation = {
        "player_name": player_name,
        "sport": sport,
        "missing_critical": [],
        "empty_critical": [],
        "filled_critical": [],
        "completeness_score": 0
    }
    
    # Critical fields to check for quick validation
    critical_fields = {
        "identity": ["age", "position", "team"],
        "proof": ["awards"] if sport == "NFL" else ["career_points"],
        "brand": ["instagram_followers"],
        "risk": ["injury_risk_score"]
    }
    
    total_critical = 0
    filled_critical = 0
    
    # Get all sections
    sections = {
        "identity": player_data.identity,
        "brand": player_data.brand,
        "proof": player_data.proof,
        "risk": player_data.risk
    }
    
    for section_name, field_list in critical_fields.items():
        section_data = sections.get(section_name)
        
        for field_name in field_list:
            total_critical += 1
            field_path = f"{section_name}.{field_name}"
            
            if section_data is None:
                validation["missing_critical"].append(field_path)
            else:
                value = getattr(section_data, field_name, None)
                
                if value is None:
                    validation["missing_critical"].append(field_path)
                elif _is_empty(value):
                    validation["empty_critical"].append(field_path)
                else:
                    validation["filled_critical"].append(field_path)
                    filled_critical += 1
    
    # Calculate completeness score
    validation["completeness_score"] = (filled_critical / total_critical) * 100 if total_critical > 0 else 0
    
    return validation


def test_nfl():
    """Test NFL scraper with 3 players"""
    print("\n" + "="*70)
    print("  🏈 NFL QUICK TEST (3 Players)")
    print("="*70 + "\n")
    
    from gravity.nfl_scraper import NFLPlayerCollector
    from gravity.scrape import get_direct_api, PlayerData
    
    collector = NFLPlayerCollector(get_direct_api())
    results = []
    validations = []
    
    with tqdm(total=3, desc="🏈 NFL Players", unit="player") as pbar:
        for player_info in TEST_PLAYERS["NFL"]:
            try:
                player_data = collector.collect_player_data(
                    player_info["name"],
                    player_info["team"],
                    player_info["position"]
                )
                
                if player_data:
                    results.append(player_data)
                    validation = validate_player_data(player_data, player_info["name"], "NFL")
                    validations.append(validation)
                    pbar.set_postfix_str(f"✅ {player_info['name']} ({validation['completeness_score']:.0f}%)")
                else:
                    pbar.set_postfix_str(f"❌ {player_info['name']} - No data")
                
                pbar.update(1)
                
            except Exception as e:
                logger.error(f"Failed to collect {player_info['name']}: {e}")
                pbar.update(1)
    
    return results, validations


def test_nba():
    """Test NBA scraper with 3 players"""
    print("\n" + "="*70)
    print("  🏀 NBA QUICK TEST (3 Players)")
    print("="*70 + "\n")
    
    from gravity.nba_scraper import NBAPlayerCollector
    from gravity.scrape import get_direct_api
    from gravity.nba_data_models import NBAPlayerData
    
    collector = NBAPlayerCollector(get_direct_api())
    results = []
    validations = []
    
    with tqdm(total=3, desc="🏀 NBA Players", unit="player") as pbar:
        for player_info in TEST_PLAYERS["NBA"]:
            try:
                player_data = collector.collect_player_data(
                    player_info["name"],
                    player_info["team"],
                    player_info["position"]
                )
                
                if player_data:
                    results.append(player_data)
                    validation = validate_player_data(player_data, player_info["name"], "NBA")
                    validations.append(validation)
                    pbar.set_postfix_str(f"✅ {player_info['name']} ({validation['completeness_score']:.0f}%)")
                else:
                    pbar.set_postfix_str(f"❌ {player_info['name']} - No data")
                
                pbar.update(1)
                
            except Exception as e:
                logger.error(f"Failed to collect {player_info['name']}: {e}")
                pbar.update(1)
    
    return results, validations


def test_cfb():
    """Test CFB scraper with 3 players"""
    print("\n" + "="*70)
    print("  🏈 CFB QUICK TEST (3 Players)")
    print("="*70 + "\n")
    
    from gravity.cfb_scraper import CFBPlayerCollector
    from gravity.scrape import get_direct_api
    from gravity.cfb_data_models import CFBPlayerData
    
    collector = CFBPlayerCollector(get_direct_api())
    results = []
    validations = []
    
    with tqdm(total=3, desc="🏈 CFB Players", unit="player") as pbar:
        for player_info in TEST_PLAYERS["CFB"]:
            try:
                player_data = collector.collect_player_data(
                    player_info["name"],
                    player_info["team"],
                    player_info["position"]
                )
                
                if player_data:
                    results.append(player_data)
                    validation = validate_player_data(player_data, player_info["name"], "CFB")
                    validations.append(validation)
                    pbar.set_postfix_str(f"✅ {player_info['name']} ({validation['completeness_score']:.0f}%)")
                else:
                    pbar.set_postfix_str(f"❌ {player_info['name']} - No data")
                
                pbar.update(1)
                
            except Exception as e:
                logger.error(f"Failed to collect {player_info['name']}: {e}")
                pbar.update(1)
    
    return results, validations


def save_results(sport: str, results: List, validations: List):
    """Save test results to organized folder"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create date-based output folder
    output_dir = f"test_results/{sport.upper()}_Quick/{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save CSV
    csv_file = os.path.join(output_dir, f"{sport.lower()}_quick_test_{timestamp}.csv")
    player_dicts = [asdict(p) for p in results]
    df = pd.DataFrame(player_dicts)
    df.to_csv(csv_file, index=False)
    
    # Save validation report
    report_file = os.path.join(output_dir, f"{sport.lower()}_quick_validation_{timestamp}.txt")
    with open(report_file, 'w') as f:
        f.write("="*70 + "\n")
        f.write(f"{sport.upper()} QUICK TEST VALIDATION\n")
        f.write("="*70 + "\n\n")
        f.write(f"Players tested: {len(results)}\n\n")
        
        for v in validations:
            f.write(f"{v['player_name']}: {v['completeness_score']:.1f}% complete\n")
            if v['missing_critical']:
                f.write(f"  Missing: {', '.join(v['missing_critical'])}\n")
            if v['empty_critical']:
                f.write(f"  Empty: {', '.join(v['empty_critical'])}\n")
    
    return csv_file, report_file, output_dir


def print_summary(sport: str, validations: List):
    """Print validation summary"""
    print(f"\n📊 {sport.upper()} Summary:")
    print(f"   Players tested: {len(validations)}")
    
    avg_completeness = sum(v["completeness_score"] for v in validations) / len(validations) if validations else 0
    print(f"   Avg completeness: {avg_completeness:.1f}%")
    
    for v in validations:
        status = "✅" if v["completeness_score"] >= 70 else "⚠️"
        print(f"   {status} {v['player_name']}: {v['completeness_score']:.1f}%")
    print()


def main():
    """Run quick tests"""
    
    # Parse command line arguments
    sport_filter = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    
    if sport_filter not in ["all", "nfl", "nba", "cfb"]:
        print(f"❌ Invalid sport: {sport_filter}")
        print("Valid options: all, nfl, nba, cfb")
        return 1
    
    print("\n" + "="*70)
    print("  ⚡ QUICK TEST - 3 Players Per Sport")
    print("="*70)
    
    sports_to_test = ["nfl", "nba", "cfb"] if sport_filter == "all" else [sport_filter]
    
    all_results = {}
    
    start_time = datetime.now()
    
    # Run tests
    for sport in sports_to_test:
        if sport == "nfl":
            results, validations = test_nfl()
        elif sport == "nba":
            results, validations = test_nba()
        elif sport == "cfb":
            results, validations = test_cfb()
        
        if results:
            csv_file, report_file, output_dir = save_results(sport, results, validations)
            print(f"\n💾 {sport.upper()} results saved to: {output_dir}")
            print_summary(sport, validations)
            
            all_results[sport] = {
                "results": results,
                "validations": validations,
                "output_dir": output_dir
            }
    
    # Final summary
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print("="*70)
    print("  ✅ QUICK TEST COMPLETE!")
    print("="*70)
    print(f"\nTotal time: {elapsed:.1f} seconds")
    print(f"Sports tested: {len(all_results)}")
    print(f"Total players: {sum(len(r['results']) for r in all_results.values())}")
    
    # Overall summary
    print("\n📊 Overall Results:")
    for sport, data in all_results.items():
        avg = sum(v["completeness_score"] for v in data["validations"]) / len(data["validations"])
        status = "✅" if avg >= 70 else "⚠️"
        print(f"   {status} {sport.upper()}: {avg:.1f}% avg completeness ({len(data['results'])} players)")
    
    print("\n💡 Tip: Use ./view_latest_results.sh to view detailed results")
    print()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

