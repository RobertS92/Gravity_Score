#!/usr/bin/env python3
"""
NBA Test Scraper - 2 Players Per Team
======================================

Scrapes 2 players from each NBA team to validate data collection.
VALIDATES ALL FIELDS (comprehensive validation).
Outputs detailed report of missing/empty fields.

Usage:
    python test_nba_2_per_team.py
"""

import sys
import os
import logging
from datetime import datetime
from typing import List, Dict, Any
import pandas as pd
from dataclasses import fields

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


# NBA Team Structure with Conference/Division
NBA_STRUCTURE = {
    "Eastern": {
        "Atlantic": ["Boston Celtics", "Brooklyn Nets", "New York Knicks", "Philadelphia 76ers", "Toronto Raptors"],
        "Central": ["Chicago Bulls", "Cleveland Cavaliers", "Detroit Pistons", "Indiana Pacers", "Milwaukee Bucks"],
        "Southeast": ["Atlanta Hawks", "Charlotte Hornets", "Miami Heat", "Orlando Magic", "Washington Wizards"]
    },
    "Western": {
        "Northwest": ["Denver Nuggets", "Minnesota Timberwolves", "Oklahoma City Thunder", "Portland Trail Blazers", "Utah Jazz"],
        "Pacific": ["Golden State Warriors", "LA Clippers", "Los Angeles Lakers", "Phoenix Suns", "Sacramento Kings"],
        "Southwest": ["Dallas Mavericks", "Houston Rockets", "Memphis Grizzlies", "New Orleans Pelicans", "San Antonio Spurs"]
    }
}


def get_two_players_per_team() -> List[Dict]:
    """
    Get 2 notable players from each NBA team
    
    Returns:
        List of player dicts with name, team, position, conference, division
    """
    # Predefined list of 2 notable players per team
    test_players = {
        # Eastern - Atlantic
        "Boston Celtics": [
            {"name": "Jayson Tatum", "position": "F"},
            {"name": "Jaylen Brown", "position": "G"}
        ],
        "Brooklyn Nets": [
            {"name": "Mikal Bridges", "position": "F"},
            {"name": "Cameron Johnson", "position": "F"}
        ],
        "New York Knicks": [
            {"name": "Jalen Brunson", "position": "G"},
            {"name": "Julius Randle", "position": "F"}
        ],
        "Philadelphia 76ers": [
            {"name": "Joel Embiid", "position": "C"},
            {"name": "Tyrese Maxey", "position": "G"}
        ],
        "Toronto Raptors": [
            {"name": "Scottie Barnes", "position": "F"},
            {"name": "Pascal Siakam", "position": "F"}
        ],
        
        # Eastern - Central
        "Chicago Bulls": [
            {"name": "DeMar DeRozan", "position": "F"},
            {"name": "Zach LaVine", "position": "G"}
        ],
        "Cleveland Cavaliers": [
            {"name": "Donovan Mitchell", "position": "G"},
            {"name": "Darius Garland", "position": "G"}
        ],
        "Detroit Pistons": [
            {"name": "Cade Cunningham", "position": "G"},
            {"name": "Jaden Ivey", "position": "G"}
        ],
        "Indiana Pacers": [
            {"name": "Tyrese Haliburton", "position": "G"},
            {"name": "Myles Turner", "position": "C"}
        ],
        "Milwaukee Bucks": [
            {"name": "Giannis Antetokounmpo", "position": "F"},
            {"name": "Damian Lillard", "position": "G"}
        ],
        
        # Eastern - Southeast
        "Atlanta Hawks": [
            {"name": "Trae Young", "position": "G"},
            {"name": "Dejounte Murray", "position": "G"}
        ],
        "Charlotte Hornets": [
            {"name": "LaMelo Ball", "position": "G"},
            {"name": "Brandon Miller", "position": "F"}
        ],
        "Miami Heat": [
            {"name": "Bam Adebayo", "position": "C"},
            {"name": "Tyler Herro", "position": "G"}
        ],
        "Orlando Magic": [
            {"name": "Paolo Banchero", "position": "F"},
            {"name": "Franz Wagner", "position": "F"}
        ],
        "Washington Wizards": [
            {"name": "Kyle Kuzma", "position": "F"},
            {"name": "Jordan Poole", "position": "G"}
        ],
        
        # Western - Northwest
        "Denver Nuggets": [
            {"name": "Nikola Jokic", "position": "C"},
            {"name": "Jamal Murray", "position": "G"}
        ],
        "Minnesota Timberwolves": [
            {"name": "Anthony Edwards", "position": "G"},
            {"name": "Karl-Anthony Towns", "position": "C"}
        ],
        "Oklahoma City Thunder": [
            {"name": "Shai Gilgeous-Alexander", "position": "G"},
            {"name": "Chet Holmgren", "position": "C"}
        ],
        "Portland Trail Blazers": [
            {"name": "Damian Lillard", "position": "G"},
            {"name": "Anfernee Simons", "position": "G"}
        ],
        "Utah Jazz": [
            {"name": "Lauri Markkanen", "position": "F"},
            {"name": "Jordan Clarkson", "position": "G"}
        ],
        
        # Western - Pacific
        "Golden State Warriors": [
            {"name": "Stephen Curry", "position": "G"},
            {"name": "Klay Thompson", "position": "G"}
        ],
        "LA Clippers": [
            {"name": "Kawhi Leonard", "position": "F"},
            {"name": "Paul George", "position": "F"}
        ],
        "Los Angeles Lakers": [
            {"name": "LeBron James", "position": "F"},
            {"name": "Anthony Davis", "position": "F"}
        ],
        "Phoenix Suns": [
            {"name": "Kevin Durant", "position": "F"},
            {"name": "Devin Booker", "position": "G"}
        ],
        "Sacramento Kings": [
            {"name": "De'Aaron Fox", "position": "G"},
            {"name": "Domantas Sabonis", "position": "C"}
        ],
        
        # Western - Southwest
        "Dallas Mavericks": [
            {"name": "Luka Doncic", "position": "G"},
            {"name": "Kyrie Irving", "position": "G"}
        ],
        "Houston Rockets": [
            {"name": "Alperen Sengun", "position": "C"},
            {"name": "Jalen Green", "position": "G"}
        ],
        "Memphis Grizzlies": [
            {"name": "Ja Morant", "position": "G"},
            {"name": "Jaren Jackson Jr.", "position": "F"}
        ],
        "New Orleans Pelicans": [
            {"name": "Zion Williamson", "position": "F"},
            {"name": "Brandon Ingram", "position": "F"}
        ],
        "San Antonio Spurs": [
            {"name": "Victor Wembanyama", "position": "C"},
            {"name": "Devin Vassell", "position": "G"}
        ]
    }
    
    # Flatten to list with conference/division info
    players = []
    for conference, divisions in NBA_STRUCTURE.items():
        for division, teams in divisions.items():
            for team in teams:
                if team in test_players:
                    for player in test_players[team]:
                        players.append({
                            "name": player["name"],
                            "team": team,
                            "position": player["position"],
                            "conference": conference,
                            "division": division
                        })
    
    return players


def validate_all_fields(player_data: NBAPlayerData, player_name: str) -> Dict:
    """
    Validate ALL fields in player data (comprehensive validation)
    
    Returns dict with validation results
    """
    validation = {
        "player_name": player_name,
        "missing_fields": [],
        "empty_fields": [],
        "filled_fields": [],
        "completeness_score": 0,
        "total_fields": 0,
        "by_section": {}
    }
    
    # Get all sections
    sections = {
        "identity": player_data.identity,
        "brand": player_data.brand,
        "proof": player_data.proof,
        "proximity": player_data.proximity,
        "velocity": player_data.velocity,
        "risk": player_data.risk
    }
    
    total_fields = 0
    filled_count = 0
    
    # Validate each section comprehensively
    for section_name, section_data in sections.items():
        section_stats = {
            "total": 0,
            "filled": 0,
            "missing": 0,
            "empty": 0
        }
        
        if section_data is None:
            logger.warning(f"Section {section_name} is None for {player_name}")
            continue
        
        # Get all fields in this dataclass
        section_fields = fields(section_data)
        
        for field in section_fields:
            field_name = field.name
            field_path = f"{section_name}.{field_name}"
            total_fields += 1
            section_stats["total"] += 1
            
            try:
                value = getattr(section_data, field_name, None)
                
                if value is None:
                    validation["missing_fields"].append(field_path)
                    section_stats["missing"] += 1
                elif _is_empty(value):
                    validation["empty_fields"].append(field_path)
                    section_stats["empty"] += 1
                else:
                    validation["filled_fields"].append(field_path)
                    filled_count += 1
                    section_stats["filled"] += 1
            except Exception as e:
                logger.debug(f"Error checking field {field_path}: {e}")
                validation["missing_fields"].append(field_path)
                section_stats["missing"] += 1
        
        validation["by_section"][section_name] = section_stats
    
    # Calculate completeness score
    validation["total_fields"] = total_fields
    validation["completeness_score"] = (filled_count / total_fields) * 100 if total_fields > 0 else 0
    
    return validation


def _is_empty(value: Any) -> bool:
    """Check if a value is considered empty"""
    if value == "":
        return True
    if value == 0:
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def main():
    """Run test scrape of 2 players per team"""
    
    print("\n" + "="*80)
    print("  NBA TEST SCRAPER - 2 Players Per Team")
    print("  COMPREHENSIVE VALIDATION (ALL FIELDS)")
    print("="*80 + "\n")
    
    # Initialize collector
    collector = NBAPlayerCollector(get_direct_api())
    
    # Get test players
    print("🏀 Loading test player list (2 per team, 60 total)...")
    players = get_two_players_per_team()
    print(f"✅ {len(players)} players selected\n")
    
    # Display conference/division breakdown
    print("📊 Distribution:")
    for conf in ["Eastern", "Western"]:
        conf_players = [p for p in players if p["conference"] == conf]
        print(f"   {conf} Conference: {len(conf_players)} players")
    print()
    
    # Scrape players
    print("🏀 Starting data collection...\n")
    
    results = []
    validations = []
    
    with tqdm(total=len(players), desc="Collecting player data", unit="player") as pbar:
        for player in players:
            try:
                # Collect data
                player_data = collector.collect_player_data(
                    player["name"],
                    player["team"],
                    player["position"]
                )
                
                if player_data:
                    results.append(player_data)
                    
                    # Validate ALL fields
                    validation = validate_all_fields(player_data, player["name"])
                    validations.append(validation)
                    
                    pbar.set_postfix_str(f"✅ {player['name']} ({validation['completeness_score']:.0f}% complete)")
                else:
                    pbar.set_postfix_str(f"❌ {player['name']} - No data")
                
                pbar.update(1)
                
            except Exception as e:
                logger.error(f"Failed to collect {player['name']}: {e}")
                pbar.update(1)
    
    print(f"\n✅ Data collection complete!\n")
    
    # ========================================================================
    # GENERATE COMPREHENSIVE VALIDATION REPORT
    # ========================================================================
    
    print("="*80)
    print("  COMPREHENSIVE DATA VALIDATION REPORT")
    print("  (ALL FIELDS VALIDATED)")
    print("="*80 + "\n")
    
    # Overall stats
    avg_completeness = sum(v["completeness_score"] for v in validations) / len(validations) if validations else 0
    total_fields_avg = sum(v["total_fields"] for v in validations) / len(validations) if validations else 0
    
    print(f"📊 Overall Statistics:")
    print(f"   Players collected: {len(results)}/{len(players)}")
    print(f"   Avg fields per player: {total_fields_avg:.0f}")
    print(f"   Avg completeness: {avg_completeness:.1f}%")
    print()
    
    # Section-level analysis
    print("📊 Completeness by Section:")
    section_names = ["identity", "brand", "proof", "proximity", "velocity", "risk"]
    for section in section_names:
        section_totals = {"total": 0, "filled": 0, "missing": 0, "empty": 0}
        
        for v in validations:
            if section in v["by_section"]:
                for key in section_totals.keys():
                    section_totals[key] += v["by_section"][section][key]
        
        if section_totals["total"] > 0:
            completeness = (section_totals["filled"] / section_totals["total"]) * 100
            print(f"   {section:15s}: {completeness:5.1f}% complete "
                  f"({section_totals['filled']}/{section_totals['total']} fields)")
    print()
    
    # Field-level analysis
    all_missing = {}
    all_empty = {}
    
    for v in validations:
        for field in v["missing_fields"]:
            all_missing[field] = all_missing.get(field, 0) + 1
        for field in v["empty_fields"]:
            all_empty[field] = all_empty.get(field, 0) + 1
    
    # Most commonly missing fields
    print("❌ Top 15 Most Commonly MISSING Fields (NULL):")
    sorted_missing = sorted(all_missing.items(), key=lambda x: x[1], reverse=True)[:15]
    for field, count in sorted_missing:
        pct = (count / len(validations)) * 100
        print(f"   {field:55s}: {count:3d} players ({pct:5.1f}%)")
    print()
    
    # Most commonly empty fields
    print("⚠️  Top 15 Most Commonly EMPTY Fields (0, '', []):")
    sorted_empty = sorted(all_empty.items(), key=lambda x: x[1], reverse=True)[:15]
    for field, count in sorted_empty:
        pct = (count / len(validations)) * 100
        print(f"   {field:55s}: {count:3d} players ({pct:5.1f}%)")
    print()
    
    # Best and worst players
    validations_sorted = sorted(validations, key=lambda x: x["completeness_score"], reverse=True)
    
    print("🏆 Top 5 Most Complete Players:")
    for i, v in enumerate(validations_sorted[:5], 1):
        print(f"   {i}. {v['player_name']:30s} - {v['completeness_score']:5.1f}% complete "
              f"({len(v['filled_fields'])}/{v['total_fields']} fields)")
    print()
    
    print("⚠️  Bottom 5 Least Complete Players:")
    for i, v in enumerate(validations_sorted[-5:], 1):
        print(f"   {i}. {v['player_name']:30s} - {v['completeness_score']:5.1f}% complete "
              f"({len(v['filled_fields'])}/{v['total_fields']} fields)")
    print()
    
    # Conference comparison
    print("📊 Completeness by Conference:")
    for conf in ["Eastern", "Western"]:
        conf_validations = [v for i, v in enumerate(validations) 
                           if players[i]["conference"] == conf]
        if conf_validations:
            conf_avg = sum(v["completeness_score"] for v in conf_validations) / len(conf_validations)
            print(f"   {conf:15s}: {conf_avg:5.1f}% avg completeness")
    print()
    
    # ========================================================================
    # SAVE RESULTS
    # ========================================================================
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create date-based output folder
    output_dir = f"test_results/NBA/{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    csv_file = os.path.join(output_dir, f"nba_test_2per_team_{timestamp}.csv")
    
    # Convert to DataFrame and save
    player_dicts = [p.to_dict() for p in results]
    df = pd.DataFrame(player_dicts)
    df.to_csv(csv_file, index=False)
    
    print(f"💾 Results saved to: {csv_file}")
    print(f"   {len(df)} players, {len(df.columns)} columns")
    print()
    
    # Save comprehensive validation report
    report_file = os.path.join(output_dir, f"nba_validation_report_{timestamp}.txt")
    with open(report_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("NBA COMPREHENSIVE DATA VALIDATION REPORT\n")
        f.write("(ALL FIELDS VALIDATED)\n")
        f.write("="*80 + "\n\n")
        f.write(f"Players collected: {len(results)}/{len(players)}\n")
        f.write(f"Avg fields per player: {total_fields_avg:.0f}\n")
        f.write(f"Avg completeness: {avg_completeness:.1f}%\n\n")
        
        f.write("SECTION-LEVEL COMPLETENESS:\n")
        for section in section_names:
            section_totals = {"total": 0, "filled": 0, "missing": 0, "empty": 0}
            for v in validations:
                if section in v["by_section"]:
                    for key in section_totals.keys():
                        section_totals[key] += v["by_section"][section][key]
            if section_totals["total"] > 0:
                completeness = (section_totals["filled"] / section_totals["total"]) * 100
                f.write(f"  {section}: {completeness:.1f}% ({section_totals['filled']}/{section_totals['total']} fields)\n")
        
        f.write("\nMOST COMMONLY MISSING FIELDS:\n")
        for field, count in sorted_missing:
            pct = (count / len(validations)) * 100
            f.write(f"  {field}: {count} players ({pct:.1f}%)\n")
        
        f.write("\nMOST COMMONLY EMPTY FIELDS:\n")
        for field, count in sorted_empty:
            pct = (count / len(validations)) * 100
            f.write(f"  {field}: {count} players ({pct:.1f}%)\n")
        
        f.write("\nPER-PLAYER VALIDATION:\n")
        for v in validations_sorted:
            f.write(f"\n{v['player_name']} - {v['completeness_score']:.1f}% complete "
                   f"({len(v['filled_fields'])}/{v['total_fields']} fields)\n")
            f.write(f"  Section breakdown:\n")
            for section, stats in v["by_section"].items():
                if stats["total"] > 0:
                    sect_pct = (stats["filled"] / stats["total"]) * 100
                    f.write(f"    {section}: {sect_pct:.1f}% ({stats['filled']}/{stats['total']})\n")
    
    print(f"📄 Comprehensive validation report saved to: {report_file}")
    print()
    print(f"📁 All files saved to: {output_dir}")
    
    print("\n" + "="*80)
    print("  ✅ TEST COMPLETE!")
    print("="*80 + "\n")
    
    print("Next steps:")
    print("  1. Review comprehensive validation report for ALL missing fields")
    print("  2. Fix high-priority missing fields across all sections")
    print(f"  3. Run: python run_pipeline.py {csv_file} scored_output.csv")
    print("     to add Gravity Scores with velocity features!")
    print()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

