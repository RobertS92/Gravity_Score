#!/usr/bin/env python3
"""
Quick NBA Test - 3 Players
===========================

Fast validation for NBA scraper with 3 notable players.

Usage:
    python quick_test_nba.py
    
Time: ~30-45 seconds
"""

import sys
import os
import logging
from datetime import datetime
from typing import List, Dict, Any
import pandas as pd
from dataclasses import asdict

# Add gravity to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gravity'))

from gravity.nba_scraper import NBAPlayerCollector
from gravity.scrape import get_direct_api
from gravity.nba_data_models import NBAPlayerData
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Test players - 3 notable NBA stars
TEST_PLAYERS = [
    {"name": "LeBron James", "team": "Los Angeles Lakers", "position": "SF"},
    {"name": "Stephen Curry", "team": "Golden State Warriors", "position": "PG"},
    {"name": "Kevin Durant", "team": "Phoenix Suns", "position": "PF"}
]


def _is_empty(value: Any) -> bool:
    """Check if a value is considered empty"""
    if value is None:
        return True
    if value == "" or value == 0:
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def validate_player(player_data: NBAPlayerData, player_name: str) -> Dict:
    """Quick validation of critical fields"""
    validation = {
        "player_name": player_name,
        "filled": 0,
        "total": 0,
        "completeness": 0
    }
    
    # Check critical fields
    critical = [
        ("identity", "age"),
        ("identity", "position"),
        ("identity", "team"),
        ("proof", "career_points"),
        ("brand", "instagram_followers"),
        ("risk", "injury_risk_score")
    ]
    
    for section, field in critical:
        validation["total"] += 1
        section_data = getattr(player_data, section, None)
        if section_data:
            value = getattr(section_data, field, None)
            if not _is_empty(value):
                validation["filled"] += 1
    
    validation["completeness"] = (validation["filled"] / validation["total"]) * 100 if validation["total"] > 0 else 0
    return validation


def main():
    """Run quick NBA test"""
    
    print("\n" + "="*70)
    print("  🏀 NBA QUICK TEST - 3 Players")
    print("="*70 + "\n")
    
    start_time = datetime.now()
    
    # Initialize collector
    collector = NBAPlayerCollector(get_direct_api())
    
    results = []
    validations = []
    
    # Collect data
    with tqdm(total=3, desc="🏀 Collecting NBA players", unit="player") as pbar:
        for player_info in TEST_PLAYERS:
            try:
                player_data = collector.collect_player_data(
                    player_info["name"],
                    player_info["team"],
                    player_info["position"]
                )
                
                if player_data:
                    results.append(player_data)
                    validation = validate_player(player_data, player_info["name"])
                    validations.append(validation)
                    pbar.set_postfix_str(f"✅ {player_info['name']} ({validation['completeness']:.0f}%)")
                else:
                    pbar.set_postfix_str(f"❌ {player_info['name']} - No data")
                
                pbar.update(1)
                
            except Exception as e:
                logger.error(f"Failed: {player_info['name']}: {e}")
                pbar.update(1)
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = f"test_results/NBA_Quick/{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    # CSV
    csv_file = os.path.join(output_dir, f"nba_quick_{timestamp}.csv")
    df = pd.DataFrame([asdict(p) for p in results])
    df.to_csv(csv_file, index=False)
    
    # Report
    report_file = os.path.join(output_dir, f"nba_quick_report_{timestamp}.txt")
    with open(report_file, 'w') as f:
        f.write("NBA QUICK TEST REPORT\n")
        f.write("="*70 + "\n\n")
        for v in validations:
            f.write(f"{v['player_name']}: {v['completeness']:.1f}%\n")
    
    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    avg = sum(v["completeness"] for v in validations) / len(validations) if validations else 0
    
    print(f"\n📊 Summary:")
    print(f"   Players: {len(results)}")
    print(f"   Avg completeness: {avg:.1f}%")
    print(f"   Time: {elapsed:.1f}s")
    print(f"\n💾 Saved to: {output_dir}")
    
    for v in validations:
        status = "✅" if v["completeness"] >= 70 else "⚠️"
        print(f"   {status} {v['player_name']}: {v['completeness']:.0f}%")
    
    print("\n" + "="*70)
    print("  ✅ NBA QUICK TEST COMPLETE!")
    print("="*70 + "\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

