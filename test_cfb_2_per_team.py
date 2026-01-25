#!/usr/bin/env python3
"""
CFB Test Scraper - 2 Players Per Team
======================================

Scrapes 2 players from major College Football teams to validate data collection.
VALIDATES ALL FIELDS (not just critical ones) for comprehensive testing.

Usage:
    python test_cfb_2_per_team.py
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

from gravity.cfb_scraper import CFBPlayerCollector
from gravity.scrape import get_direct_api
from gravity.cfb_data_models import CFBPlayerData, CFBIdentityData, CFBProofData
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# CFB Team Structure - Power 5 + Select Group of 5
CFB_STRUCTURE = {
    "SEC": {
        "East": ["Georgia", "Florida", "Tennessee", "Kentucky", "South Carolina", "Missouri", "Vanderbilt"],
        "West": ["Alabama", "LSU", "Texas A&M", "Auburn", "Ole Miss", "Mississippi State", "Arkansas"]
    },
    "Big Ten": {
        "East": ["Ohio State", "Michigan", "Penn State", "Maryland", "Rutgers", "Indiana"],
        "West": ["Wisconsin", "Iowa", "Minnesota", "Nebraska", "Northwestern", "Illinois", "Purdue"]
    },
    "ACC": {
        "Atlantic": ["Clemson", "Florida State", "NC State", "Wake Forest", "Syracuse", "Boston College", "Louisville"],
        "Coastal": ["Miami", "North Carolina", "Virginia", "Virginia Tech", "Pittsburgh", "Duke", "Georgia Tech"]
    },
    "Big 12": {
        "Conference": ["Oklahoma", "Texas", "Baylor", "Oklahoma State", "Kansas State", "TCU", 
                      "West Virginia", "Kansas", "Iowa State", "Texas Tech"]
    },
    "Pac-12": {
        "North": ["Washington", "Oregon", "Oregon State", "Washington State", "California", "Stanford"],
        "South": ["USC", "UCLA", "Utah", "Colorado", "Arizona", "Arizona State"]
    }
}


def get_two_players_per_team() -> List[Dict]:
    """
    Get 2 notable players from select CFB teams
    
    Returns:
        List of player dicts with name, team, position, conference, division
    """
    # Select ~30 top teams (2 players each = 60 total)
    test_players = {
        # SEC
        "Georgia": [
            {"name": "Carson Beck", "position": "QB"},
            {"name": "Brock Bowers", "position": "TE"}
        ],
        "Alabama": [
            {"name": "Jalen Milroe", "position": "QB"},
            {"name": "Dallas Turner", "position": "LB"}
        ],
        "LSU": [
            {"name": "Jayden Daniels", "position": "QB"},
            {"name": "Harold Perkins", "position": "LB"}
        ],
        "Texas A&M": [
            {"name": "Conner Weigman", "position": "QB"},
            {"name": "Edgerrin Cooper", "position": "LB"}
        ],
        "Florida": [
            {"name": "Graham Mertz", "position": "QB"},
            {"name": "Ricky Pearsall", "position": "WR"}
        ],
        "Tennessee": [
            {"name": "Joe Milton III", "position": "QB"},
            {"name": "Cedric Tillman", "position": "WR"}
        ],
        
        # Big Ten
        "Ohio State": [
            {"name": "Kyle McCord", "position": "QB"},
            {"name": "Marvin Harrison Jr.", "position": "WR"}
        ],
        "Michigan": [
            {"name": "J.J. McCarthy", "position": "QB"},
            {"name": "Blake Corum", "position": "RB"}
        ],
        "Penn State": [
            {"name": "Drew Allar", "position": "QB"},
            {"name": "Chop Robinson", "position": "DE"}
        ],
        "Wisconsin": [
            {"name": "Tanner Mordecai", "position": "QB"},
            {"name": "Braelon Allen", "position": "RB"}
        ],
        "Iowa": [
            {"name": "Cade McNamara", "position": "QB"},
            {"name": "Cooper DeJean", "position": "DB"}
        ],
        
        # ACC
        "Clemson": [
            {"name": "Cade Klubnik", "position": "QB"},
            {"name": "Peter Woods", "position": "DT"}
        ],
        "Florida State": [
            {"name": "Jordan Travis", "position": "QB"},
            {"name": "Jared Verse", "position": "DE"}
        ],
        "Miami": [
            {"name": "Tyler Van Dyke", "position": "QB"},
            {"name": "Kamren Kinchens", "position": "S"}
        ],
        "North Carolina": [
            {"name": "Drake Maye", "position": "QB"},
            {"name": "Cedric Gray", "position": "LB"}
        ],
        "Louisville": [
            {"name": "Jack Plummer", "position": "QB"},
            {"name": "Ashton Gillotte", "position": "DE"}
        ],
        
        # Big 12
        "Oklahoma": [
            {"name": "Dillon Gabriel", "position": "QB"},
            {"name": "Danny Stutsman", "position": "LB"}
        ],
        "Texas": [
            {"name": "Quinn Ewers", "position": "QB"},
            {"name": "T'Vondre Sweat", "position": "DT"}
        ],
        "Oklahoma State": [
            {"name": "Alan Bowman", "position": "QB"},
            {"name": "Collin Oliver", "position": "DE"}
        ],
        "Kansas State": [
            {"name": "Will Howard", "position": "QB"},
            {"name": "Felix Anudike-Uzomah", "position": "DE"}
        ],
        "TCU": [
            {"name": "Chandler Morris", "position": "QB"},
            {"name": "Johnny Hodges", "position": "DB"}
        ],
        
        # Pac-12
        "Washington": [
            {"name": "Michael Penix Jr.", "position": "QB"},
            {"name": "Rome Odunze", "position": "WR"}
        ],
        "Oregon": [
            {"name": "Bo Nix", "position": "QB"},
            {"name": "Troy Franklin", "position": "WR"}
        ],
        "USC": [
            {"name": "Caleb Williams", "position": "QB"},
            {"name": "Zachariah Branch", "position": "WR"}
        ],
        "Utah": [
            {"name": "Cameron Rising", "position": "QB"},
            {"name": "Karene Reid", "position": "RB"}
        ],
        "UCLA": [
            {"name": "Dante Moore", "position": "QB"},
            {"name": "Laiatu Latu", "position": "DE"}
        ],
        
        # Additional Power Programs
        "Notre Dame": [
            {"name": "Sam Hartman", "position": "QB"},
            {"name": "Benjamin Morrison", "position": "CB"}
        ],
        "Baylor": [
            {"name": "Blake Shapen", "position": "QB"},
            {"name": "Richard Reese", "position": "RB"}
        ],
        "Ole Miss": [
            {"name": "Jaxson Dart", "position": "QB"},
            {"name": "Quinshon Judkins", "position": "RB"}
        ],
        "Auburn": [
            {"name": "Payton Thorne", "position": "QB"},
            {"name": "Keldric Faulk", "position": "LB"}
        ],
        "Oregon State": [
            {"name": "DJ Uiagalelei", "position": "QB"},
            {"name": "Damien Martinez", "position": "RB"}
        ]
    }
    
    # Flatten to list with conference info
    players = []
    for conference, divisions in CFB_STRUCTURE.items():
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


def validate_all_fields(player_data: CFBPlayerData, player_name: str) -> Dict:
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
    print("  CFB TEST SCRAPER - 2 Players Per Team")
    print("  COMPREHENSIVE VALIDATION (ALL FIELDS)")
    print("="*80 + "\n")
    
    # Initialize collector
    collector = CFBPlayerCollector(get_direct_api())
    
    # Get test players
    print("🏈 Loading test player list (2 per team, ~60 total)...")
    players = get_two_players_per_team()
    print(f"✅ {len(players)} players selected\n")
    
    # Display conference breakdown
    print("📊 Distribution by Conference:")
    for conf in ["SEC", "Big Ten", "ACC", "Big 12", "Pac-12"]:
        conf_players = [p for p in players if p["conference"] == conf]
        print(f"   {conf:15s}: {len(conf_players):2d} players")
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
    
    # Conference comparison
    print("📊 Completeness by Conference:")
    for conf in ["SEC", "Big Ten", "ACC", "Big 12", "Pac-12"]:
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
    output_dir = f"test_results/CFB/{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    csv_file = os.path.join(output_dir, f"cfb_test_2per_team_{timestamp}.csv")
    
    # Convert to DataFrame and save
    player_dicts = [p.to_dict() for p in results]
    df = pd.DataFrame(player_dicts)
    df.to_csv(csv_file, index=False)
    
    print(f"💾 Results saved to: {csv_file}")
    print(f"   {len(df)} players, {len(df.columns)} columns")
    print()
    
    # Save comprehensive validation report
    report_file = os.path.join(output_dir, f"cfb_validation_report_{timestamp}.txt")
    with open(report_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("CFB COMPREHENSIVE DATA VALIDATION REPORT\n")
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

