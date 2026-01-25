#!/usr/bin/env python3
"""
NFL Test Scraper - 2 Players Per Team
======================================

Scrapes 2 players from each NFL team to validate data collection.
VALIDATES ALL FIELDS (comprehensive validation).
Outputs detailed report of missing/empty fields.

Usage:
    python test_nfl_2_per_team.py
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

from gravity.nfl_scraper import NFLPlayerCollector
from gravity.scrape import get_direct_api, PlayerData
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# NFL Team Structure with Conference/Division
NFL_STRUCTURE = {
    "AFC": {
        "AFC East": ["Buffalo Bills", "Miami Dolphins", "New England Patriots", "New York Jets"],
        "AFC North": ["Baltimore Ravens", "Cincinnati Bengals", "Cleveland Browns", "Pittsburgh Steelers"],
        "AFC South": ["Houston Texans", "Indianapolis Colts", "Jacksonville Jaguars", "Tennessee Titans"],
        "AFC West": ["Denver Broncos", "Kansas City Chiefs", "Las Vegas Raiders", "Los Angeles Chargers"]
    },
    "NFC": {
        "NFC East": ["Dallas Cowboys", "New York Giants", "Philadelphia Eagles", "Washington Commanders"],
        "NFC North": ["Chicago Bears", "Detroit Lions", "Green Bay Packers", "Minnesota Vikings"],
        "NFC South": ["Atlanta Falcons", "Carolina Panthers", "New Orleans Saints", "Tampa Bay Buccaneers"],
        "NFC West": ["Arizona Cardinals", "Los Angeles Rams", "San Francisco 49ers", "Seattle Seahawks"]
    }
}


def get_two_players_per_team() -> List[Dict]:
    """
    Get 2 notable players from each NFL team (one offense, one defense if possible)
    
    Returns:
        List of player dicts with name, team, position, conference, division
    """
    # Predefined list of 2 notable players per team (mix of positions)
    test_players = {
        # AFC East
        "Buffalo Bills": [
            {"name": "Josh Allen", "position": "QB"},
            {"name": "Von Miller", "position": "LB"}
        ],
        "Miami Dolphins": [
            {"name": "Tua Tagovailoa", "position": "QB"},
            {"name": "Tyreek Hill", "position": "WR"}
        ],
        "New England Patriots": [
            {"name": "Mac Jones", "position": "QB"},
            {"name": "Matthew Judon", "position": "LB"}
        ],
        "New York Jets": [
            {"name": "Aaron Rodgers", "position": "QB"},
            {"name": "Sauce Gardner", "position": "CB"}
        ],
        
        # AFC North
        "Baltimore Ravens": [
            {"name": "Lamar Jackson", "position": "QB"},
            {"name": "Roquan Smith", "position": "LB"}
        ],
        "Cincinnati Bengals": [
            {"name": "Joe Burrow", "position": "QB"},
            {"name": "Trey Hendrickson", "position": "DE"}
        ],
        "Cleveland Browns": [
            {"name": "Deshaun Watson", "position": "QB"},
            {"name": "Myles Garrett", "position": "DE"}
        ],
        "Pittsburgh Steelers": [
            {"name": "Russell Wilson", "position": "QB"},
            {"name": "T.J. Watt", "position": "LB"}
        ],
        
        # AFC South
        "Houston Texans": [
            {"name": "C.J. Stroud", "position": "QB"},
            {"name": "Will Anderson Jr.", "position": "DE"}
        ],
        "Indianapolis Colts": [
            {"name": "Anthony Richardson", "position": "QB"},
            {"name": "DeForest Buckner", "position": "DT"}
        ],
        "Jacksonville Jaguars": [
            {"name": "Trevor Lawrence", "position": "QB"},
            {"name": "Josh Allen", "position": "LB"}
        ],
        "Tennessee Titans": [
            {"name": "Will Levis", "position": "QB"},
            {"name": "Jeffery Simmons", "position": "DT"}
        ],
        
        # AFC West
        "Denver Broncos": [
            {"name": "Bo Nix", "position": "QB"},
            {"name": "Patrick Surtain II", "position": "CB"}
        ],
        "Kansas City Chiefs": [
            {"name": "Patrick Mahomes", "position": "QB"},
            {"name": "Travis Kelce", "position": "TE"}
        ],
        "Las Vegas Raiders": [
            {"name": "Aidan O'Connell", "position": "QB"},
            {"name": "Maxx Crosby", "position": "DE"}
        ],
        "Los Angeles Chargers": [
            {"name": "Justin Herbert", "position": "QB"},
            {"name": "Khalil Mack", "position": "LB"}
        ],
        
        # NFC East
        "Dallas Cowboys": [
            {"name": "Dak Prescott", "position": "QB"},
            {"name": "Micah Parsons", "position": "LB"}
        ],
        "New York Giants": [
            {"name": "Daniel Jones", "position": "QB"},
            {"name": "Dexter Lawrence", "position": "DT"}
        ],
        "Philadelphia Eagles": [
            {"name": "Jalen Hurts", "position": "QB"},
            {"name": "A.J. Brown", "position": "WR"}
        ],
        "Washington Commanders": [
            {"name": "Jayden Daniels", "position": "QB"},
            {"name": "Terry McLaurin", "position": "WR"}
        ],
        
        # NFC North
        "Chicago Bears": [
            {"name": "Caleb Williams", "position": "QB"},
            {"name": "Montez Sweat", "position": "DE"}
        ],
        "Detroit Lions": [
            {"name": "Jared Goff", "position": "QB"},
            {"name": "Amon-Ra St. Brown", "position": "WR"}
        ],
        "Green Bay Packers": [
            {"name": "Jordan Love", "position": "QB"},
            {"name": "Rashan Gary", "position": "LB"}
        ],
        "Minnesota Vikings": [
            {"name": "Sam Darnold", "position": "QB"},
            {"name": "Justin Jefferson", "position": "WR"}
        ],
        
        # NFC South
        "Atlanta Falcons": [
            {"name": "Kirk Cousins", "position": "QB"},
            {"name": "Grady Jarrett", "position": "DT"}
        ],
        "Carolina Panthers": [
            {"name": "Bryce Young", "position": "QB"},
            {"name": "Brian Burns", "position": "DE"}
        ],
        "New Orleans Saints": [
            {"name": "Derek Carr", "position": "QB"},
            {"name": "Cameron Jordan", "position": "DE"}
        ],
        "Tampa Bay Buccaneers": [
            {"name": "Baker Mayfield", "position": "QB"},
            {"name": "Vita Vea", "position": "DT"}
        ],
        
        # NFC West
        "Arizona Cardinals": [
            {"name": "Kyler Murray", "position": "QB"},
            {"name": "Budda Baker", "position": "S"}
        ],
        "Los Angeles Rams": [
            {"name": "Matthew Stafford", "position": "QB"},
            {"name": "Aaron Donald", "position": "DT"}
        ],
        "San Francisco 49ers": [
            {"name": "Brock Purdy", "position": "QB"},
            {"name": "Nick Bosa", "position": "DE"}
        ],
        "Seattle Seahawks": [
            {"name": "Geno Smith", "position": "QB"},
            {"name": "Bobby Wagner", "position": "LB"}
        ]
    }
    
    # Flatten to list with conference/division info
    players = []
    for conference, divisions in NFL_STRUCTURE.items():
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


def validate_all_fields(player_data: PlayerData, player_name: str) -> Dict:
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
    print("  NFL TEST SCRAPER - 2 Players Per Team")
    print("  COMPREHENSIVE VALIDATION (ALL FIELDS)")
    print("="*80 + "\n")
    
    # Initialize collector
    collector = NFLPlayerCollector(get_direct_api())
    
    # Get test players
    print("📋 Loading test player list (2 per team, 64 total)...")
    players = get_two_players_per_team()
    print(f"✅ {len(players)} players selected\n")
    
    # Display conference/division breakdown
    print("📊 Distribution:")
    for conf in ["AFC", "NFC"]:
        conf_players = [p for p in players if p["conference"] == conf]
        print(f"   {conf}: {len(conf_players)} players")
    print()
    
    # Scrape players
    print("🏈 Starting data collection...\n")
    
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
    
    # ========================================================================
    # SAVE RESULTS
    # ========================================================================
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create date-based output folder
    output_dir = f"test_results/NFL/{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    csv_file = os.path.join(output_dir, f"nfl_test_2per_team_{timestamp}.csv")
    
    # Convert to DataFrame and save
    player_dicts = [p.to_dict() for p in results]
    df = pd.DataFrame(player_dicts)
    df.to_csv(csv_file, index=False)
    
    print(f"💾 Results saved to: {csv_file}")
    print(f"   {len(df)} players, {len(df.columns)} columns")
    print()
    
    # Save comprehensive validation report
    report_file = os.path.join(output_dir, f"nfl_validation_report_{timestamp}.txt")
    with open(report_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("NFL COMPREHENSIVE DATA VALIDATION REPORT\n")
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

