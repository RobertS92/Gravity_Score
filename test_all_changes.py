#!/usr/bin/env python3
"""
Automated Test Suite for All Recent Changes
Tests: Proof data, Contract data, Risk data, Data quality
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
import csv

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'

class TestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []
    
    def add_pass(self, test_name, message=""):
        self.passed.append((test_name, message))
        print(f"{GREEN}✅ PASS{RESET}: {test_name} {message}")
    
    def add_fail(self, test_name, message=""):
        self.failed.append((test_name, message))
        print(f"{RED}❌ FAIL{RESET}: {test_name} {message}")
    
    def add_warning(self, test_name, message=""):
        self.warnings.append((test_name, message))
        print(f"{YELLOW}⚠️  WARN{RESET}: {test_name} {message}")
    
    def summary(self):
        print("\n" + "="*80)
        print(f"{BOLD}TEST SUMMARY{RESET}")
        print("="*80)
        print(f"{GREEN}Passed:{RESET} {len(self.passed)}")
        print(f"{RED}Failed:{RESET} {len(self.failed)}")
        print(f"{YELLOW}Warnings:{RESET} {len(self.warnings)}")
        
        if self.failed:
            print(f"\n{RED}Failed Tests:{RESET}")
            for test_name, msg in self.failed:
                print(f"  - {test_name}: {msg}")
        
        if self.warnings:
            print(f"\n{YELLOW}Warnings:{RESET}")
            for test_name, msg in self.warnings:
                print(f"  - {test_name}: {msg}")
        
        print("="*80)
        return len(self.failed) == 0


def run_scraper(sport, mode, *args):
    """Run a scraper and capture output"""
    if sport == "nfl":
        cmd = ["python3", "gravity/nfl_scraper.py", mode] + list(args)
    elif sport == "nba":
        cmd = ["python3", "gravity/nba_scraper.py", mode] + list(args)
    elif sport == "wnba":
        cmd = ["python3", "gravity/wnba_scraper.py", mode] + list(args)
    else:
        return None, f"Unknown sport: {sport}"
    
    try:
        print(f"{BLUE}Running:{RESET} {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180  # 3 minute timeout
        )
        return result, None
    except subprocess.TimeoutExpired:
        return None, "Timeout after 3 minutes"
    except Exception as e:
        return None, str(e)


def find_latest_csv(sport="NFL"):
    """Find the most recent CSV file for a sport"""
    scrapes_dir = Path(f"scrapes/{sport}")
    if not scrapes_dir.exists():
        return None
    
    csv_files = list(scrapes_dir.rglob("*.csv"))
    if not csv_files:
        return None
    
    # Get most recent by modification time
    latest = max(csv_files, key=lambda p: p.stat().st_mtime)
    return latest


def read_csv_data(csv_path):
    """Read CSV and return as list of dicts"""
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


def test_nfl_proof_data(results):
    """Test NFL proof data collection (main fix)"""
    print(f"\n{BOLD}{'='*80}{RESET}")
    print(f"{BOLD}TEST 1: NFL Proof Data (Awards, Stats, Career Totals){RESET}")
    print(f"{BOLD}{'='*80}{RESET}\n")
    
    # Test with Patrick Mahomes (should have lots of awards)
    result, error = run_scraper("nfl", "player", "Patrick Mahomes", "Chiefs", "QB")
    
    if error:
        results.add_fail("NFL Scraper Execution", error)
        return
    
    if result.returncode != 0:
        results.add_fail("NFL Scraper Execution", f"Exit code: {result.returncode}")
        print(f"{RED}STDERR:{RESET}\n{result.stderr[:500]}")
        return
    
    results.add_pass("NFL Scraper Execution")
    
    # Check console output for key indicators
    output = result.stdout + result.stderr
    
    # Check for proof data logging
    if "Pro Bowls" in output and "All-Pro" in output:
        results.add_pass("NFL Proof Data Logging", "- Awards logged")
    else:
        results.add_fail("NFL Proof Data Logging", "- No awards in output")
    
    if "TDs" in output and "yards" in output:
        results.add_pass("NFL Career Totals Logging", "- Career stats logged")
    else:
        results.add_warning("NFL Career Totals Logging", "- Career stats not in output")
    
    # Check CSV output
    csv_path = find_latest_csv("NFL")
    if not csv_path:
        results.add_fail("NFL CSV Output", "- No CSV file found")
        return
    
    results.add_pass("NFL CSV Creation", f"- {csv_path}")
    
    # Read and validate CSV data
    try:
        data = read_csv_data(csv_path)
        if not data:
            results.add_fail("NFL CSV Data", "- CSV is empty")
            return
        
        # Find Mahomes' row
        mahomes = None
        for row in data:
            if "Mahomes" in row.get('player_name', ''):
                mahomes = row
                break
        
        if not mahomes:
            results.add_warning("NFL Player Data", "- Mahomes not in CSV")
            return
        
        # Check proof fields
        pro_bowls = mahomes.get('pro_bowls', '0')
        all_pro = mahomes.get('all_pro_selections', '0')
        awards = mahomes.get('awards', '')
        career_tds = mahomes.get('career_touchdowns', '')
        career_yards = mahomes.get('career_yards', '')
        
        if pro_bowls and int(pro_bowls) >= 5:
            results.add_pass("NFL Pro Bowls", f"- Mahomes: {pro_bowls} Pro Bowls")
        else:
            results.add_fail("NFL Pro Bowls", f"- Expected 5+, got {pro_bowls}")
        
        if all_pro and int(all_pro) >= 2:
            results.add_pass("NFL All-Pro", f"- Mahomes: {all_pro} All-Pro")
        else:
            results.add_fail("NFL All-Pro", f"- Expected 2+, got {all_pro}")
        
        if awards and len(awards) > 10:
            results.add_pass("NFL Awards List", f"- {len(awards)} chars")
        else:
            results.add_fail("NFL Awards List", f"- Too short: {len(awards)} chars")
        
        if career_tds and int(float(career_tds)) >= 200:
            results.add_pass("NFL Career TDs", f"- Mahomes: {career_tds} TDs")
        else:
            results.add_fail("NFL Career TDs", f"- Expected 200+, got {career_tds}")
        
        if career_yards and int(float(career_yards)) >= 25000:
            results.add_pass("NFL Career Yards", f"- Mahomes: {career_yards} yards")
        else:
            results.add_fail("NFL Career Yards", f"- Expected 25000+, got {career_yards}")
        
    except Exception as e:
        results.add_fail("NFL CSV Parsing", str(e))


def test_nba_contract_data(results):
    """Test NBA contract data collection"""
    print(f"\n{BOLD}{'='*80}{RESET}")
    print(f"{BOLD}TEST 2: NBA Contract Data Collection{RESET}")
    print(f"{BOLD}{'='*80}{RESET}\n")
    
    # Test with LeBron James (should have contract data)
    result, error = run_scraper("nba", "player", "LeBron James", "Lakers", "SF")
    
    if error:
        results.add_fail("NBA Scraper Execution", error)
        return
    
    if result.returncode != 0:
        results.add_fail("NBA Scraper Execution", f"Exit code: {result.returncode}")
        return
    
    results.add_pass("NBA Scraper Execution")
    
    # Check console output for contract data
    output = result.stdout + result.stderr
    
    if "Contract:" in output or "contract_length" in output:
        results.add_pass("NBA Contract Logging", "- Contract data logged")
    else:
        results.add_warning("NBA Contract Logging", "- No contract in output")
    
    # Check CSV
    csv_path = find_latest_csv("NBA")
    if not csv_path:
        results.add_warning("NBA CSV Output", "- No CSV file found")
        return
    
    results.add_pass("NBA CSV Creation", f"- {csv_path}")
    
    try:
        data = read_csv_data(csv_path)
        if not data:
            results.add_fail("NBA CSV Data", "- CSV is empty")
            return
        
        # Find LeBron's row
        lebron = None
        for row in data:
            if "James" in row.get('player_name', '') and "LeBron" in row.get('player_name', ''):
                lebron = row
                break
        
        if not lebron:
            results.add_warning("NBA Player Data", "- LeBron not in CSV")
            return
        
        # Check contract fields
        contract_length = lebron.get('current_contract_length', '')
        contract_value = lebron.get('contract_value', '')
        
        if contract_length and int(contract_length) > 0:
            results.add_pass("NBA Contract Length", f"- LeBron: {contract_length} years")
        else:
            results.add_warning("NBA Contract Length", f"- No data: {contract_length}")
        
        if contract_value and float(contract_value) > 50000000:
            results.add_pass("NBA Contract Value", f"- LeBron: ${float(contract_value):,.0f}")
        else:
            results.add_warning("NBA Contract Value", f"- Low/missing: {contract_value}")
        
    except Exception as e:
        results.add_fail("NBA CSV Parsing", str(e))


def test_data_quality(results):
    """Test overall data quality across all recent CSVs"""
    print(f"\n{BOLD}{'='*80}{RESET}")
    print(f"{BOLD}TEST 3: Data Quality Checks{RESET}")
    print(f"{BOLD}{'='*80}{RESET}\n")
    
    # Check NFL CSV
    nfl_csv = find_latest_csv("NFL")
    if nfl_csv:
        try:
            data = read_csv_data(nfl_csv)
            print(f"{BLUE}Analyzing NFL CSV:{RESET} {len(data)} players")
            
            # Count non-empty key fields
            fields_to_check = {
                'age': 0,
                'pro_bowls': 0,
                'career_touchdowns': 0,
                'career_yards': 0,
                'current_contract_length': 0,
                'injury_history': 0,
                'hometown': 0
            }
            
            for row in data:
                for field in fields_to_check:
                    value = row.get(field, '')
                    if value and value != '0' and value != '[]' and value != '{}' and len(str(value)) > 0:
                        fields_to_check[field] += 1
            
            # Report percentages
            total = len(data)
            for field, count in fields_to_check.items():
                pct = (count / total * 100) if total > 0 else 0
                status = "✅" if pct >= 70 else "⚠️" if pct >= 40 else "❌"
                print(f"  {status} {field}: {count}/{total} ({pct:.1f}%)")
                
                if pct >= 70:
                    results.add_pass(f"NFL {field} coverage", f"{pct:.1f}%")
                elif pct >= 40:
                    results.add_warning(f"NFL {field} coverage", f"{pct:.1f}% (low)")
                else:
                    results.add_fail(f"NFL {field} coverage", f"{pct:.1f}% (very low)")
        
        except Exception as e:
            results.add_fail("NFL Data Quality Check", str(e))


def test_specific_fixes(results):
    """Test specific fixes we made"""
    print(f"\n{BOLD}{'='*80}{RESET}")
    print(f"{BOLD}TEST 4: Specific Bug Fixes{RESET}")
    print(f"{BOLD}{'='*80}{RESET}\n")
    
    nfl_csv = find_latest_csv("NFL")
    if not nfl_csv:
        results.add_warning("Specific Fixes Test", "No NFL CSV found")
        return
    
    try:
        data = read_csv_data(nfl_csv)
        
        # Test 1: Hometown validation (no "Tuesday", "quarterback", etc.)
        invalid_hometowns = 0
        days_of_week = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        
        for row in data:
            hometown = row.get('hometown', '').lower()
            if any(day in hometown for day in days_of_week):
                invalid_hometowns += 1
            if hometown in ['qb', 'rb', 'wr', 'te']:
                invalid_hometowns += 1
        
        if invalid_hometowns == 0:
            results.add_pass("Hometown Validation", "- No invalid hometowns")
        else:
            results.add_fail("Hometown Validation", f"- {invalid_hometowns} invalid hometowns found")
        
        # Test 2: Draft data (should be "Undrafted" not empty)
        missing_draft = 0
        undrafted_count = 0
        
        for row in data:
            draft_year = row.get('draft_year', '')
            if draft_year == 'Undrafted':
                undrafted_count += 1
            elif not draft_year or draft_year == '0':
                missing_draft += 1
        
        if missing_draft == 0:
            results.add_pass("Draft Data Handling", f"- 0 missing, {undrafted_count} marked 'Undrafted'")
        else:
            results.add_warning("Draft Data Handling", f"- {missing_draft} missing draft data")
        
        # Test 3: Years in league (should not all be 0)
        zero_years = sum(1 for row in data if row.get('years_in_league', '0') == '0')
        
        if zero_years < len(data) * 0.2:  # Less than 20% zeros is acceptable
            results.add_pass("Years in League", f"- Only {zero_years}/{len(data)} are 0")
        else:
            results.add_fail("Years in League", f"- Too many zeros: {zero_years}/{len(data)}")
        
        # Test 4: Age collection (should be mostly populated)
        missing_age = sum(1 for row in data if not row.get('age') or row.get('age') == '0')
        
        if missing_age < len(data) * 0.1:  # Less than 10% missing
            results.add_pass("Age Collection", f"- Only {missing_age}/{len(data)} missing")
        else:
            results.add_fail("Age Collection", f"- Too many missing: {missing_age}/{len(data)}")
        
    except Exception as e:
        results.add_fail("Specific Fixes Test", str(e))


def main():
    print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
    print(f"{BOLD}{BLUE}AUTOMATED TEST SUITE - ALL RECENT CHANGES{RESET}")
    print(f"{BOLD}{BLUE}{'='*80}{RESET}\n")
    print(f"Testing:")
    print(f"  1. NFL Proof Data (awards, stats, career totals)")
    print(f"  2. NBA Contract Data")
    print(f"  3. Data Quality Metrics")
    print(f"  4. Specific Bug Fixes")
    print()
    
    results = TestResults()
    
    # Run all tests
    test_nfl_proof_data(results)
    test_nba_contract_data(results)
    test_data_quality(results)
    test_specific_fixes(results)
    
    # Print summary
    success = results.summary()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

