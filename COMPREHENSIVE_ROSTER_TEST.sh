#!/bin/bash
# Test ALL roster fetching methods and report results

cd /Users/robcseals/Gravity_Score

echo "=================================================================="
echo "🏀 COMPREHENSIVE NBA ROSTER FETCHING TEST"
echo "=================================================================="
echo ""
echo "Testing all available methods..."
echo ""

echo "1. Basketball-Reference scraping..."
python3 -c "
import requests
from bs4 import BeautifulSoup
url = 'https://www.basketball-reference.com/teams/LAL/2026.html'
try:
    r = requests.get(url, timeout=5)
    if r.status_code == 200:
        soup = BeautifulSoup(r.content, 'html.parser')
        table = soup.find('table', {'id': 'roster'})
        if table:
            rows = table.find('tbody').find_all('tr')
            print(f'   ✓ SUCCESS: Found {len(rows)} Lakers players')
        else:
            print('   ✗ FAILED: No roster table found')
    else:
        print(f'   ✗ FAILED: HTTP {r.status_code}')
except Exception as e:
    print(f'   ✗ FAILED: {e}')
"

echo ""
echo "2. ESPN website scraping..."
python3 -c "
import requests
from bs4 import BeautifulSoup
url = 'https://www.espn.com/nba/team/roster/_/name/lal/los-angeles-lakers'
try:
    r = requests.get(url, timeout=5)
    if r.status_code == 200:
        print(f'   ✓ SUCCESS: Got Lakers page')
    else:
        print(f'   ✗ FAILED: HTTP {r.status_code}')
except Exception as e:
    print(f'   ✗ FAILED: {e}')
"

echo ""
echo "3. NBA.com API..."
python3 -c "
import requests
url = 'https://stats.nba.com/stats/commonteamroster'
params = {'LeagueID': '00', 'Season': '2025-26', 'TeamID': '1610612747'}
headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.nba.com/'}
try:
    r = requests.get(url, params=params, headers=headers, timeout=5)
    if r.status_code == 200:
        print(f'   ✓ SUCCESS: NBA API responded')
    else:
        print(f'   ✗ FAILED: HTTP {r.status_code}')
except Exception as e:
    print(f'   ✗ FAILED: {e}')
"

echo ""
echo "4. ESPN Roster API (via scrape module)..."
python3 << 'EOF'
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').absolute()))
import importlib.util

spec = importlib.util.spec_from_file_location("scrape", Path("gravity/scrape"))
scrape = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scrape)

api = scrape.DirectSportsAPI()
roster = api.get_espn_nba_roster('LAL')
if roster:
    print(f'   ✓ SUCCESS: Got {len(roster)} players')
    # Check if data is valid
    has_luka = any('Luka' in p.get('name', '') for p in roster)
    has_lebron = any('LeBron' in p.get('name', '') for p in roster)
    if has_luka:
        print(f'   ⚠️  WARNING: Luka Doncic in Lakers roster (WRONG!)')
    if has_lebron:
        print(f'   ✓ LeBron James found (correct)')
else:
    print('   ✗ FAILED: No roster data')
EOF

echo ""
echo "=================================================================="
echo "RESULTS SUMMARY"
echo "=================================================================="
echo ""
echo "If all methods failed, roster automation is not currently possible."
echo "Recommendation: Use manual roster updates until APIs become reliable."
echo ""
echo "See NBA_ROSTER_SOLUTION.md for next steps."
echo "=================================================================="


