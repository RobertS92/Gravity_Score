#!/usr/bin/env python3
"""
Fetch NBA rosters with proper rate limiting
Basketball-Reference requires slower requests
"""
import requests
from bs4 import BeautifulSoup
import time
import random

TEAMS = {
    'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
    'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
    'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
    'GSW': 'Golden State Warriors', 'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
    'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
    'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
    'NOP': 'New Orleans Pelicans', 'NYK': 'New York Knicks', 'OKC': 'Oklahoma City Thunder',
    'ORL': 'Orlando Magic', 'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
    'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 'SAS': 'San Antonio Spurs',
    'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards'
}

BBREF_CODES = {
    'ATL': 'ATL', 'BOS': 'BOS', 'BKN': 'BRK', 'CHA': 'CHO', 'CHI': 'CHI',
    'CLE': 'CLE', 'DAL': 'DAL', 'DEN': 'DEN', 'DET': 'DET', 'GSW': 'GSW',
    'HOU': 'HOU', 'IND': 'IND', 'LAC': 'LAC', 'LAL': 'LAL', 'MEM': 'MEM',
    'MIA': 'MIA', 'MIL': 'MIL', 'MIN': 'MIN', 'NOP': 'NOP', 'NYK': 'NYK',
    'OKC': 'OKC', 'ORL': 'ORL', 'PHI': 'PHI', 'PHX': 'PHO', 'POR': 'POR',
    'SAC': 'SAC', 'SAS': 'SAS', 'TOR': 'TOR', 'UTA': 'UTA', 'WAS': 'WAS'
}

def fetch_team_roster(abbrev, team_name, retry_count=0):
    """Fetch roster with retry logic and rate limiting"""
    bbref_code = BBREF_CODES.get(abbrev, abbrev)
    url = f"https://www.basketball-reference.com/teams/{bbref_code}/2026.html"
    
    try:
        # Add random delay to avoid rate limiting
        delay = random.uniform(2, 4)  # 2-4 second delay
        time.sleep(delay)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 429:  # Rate limited
            if retry_count < 2:
                wait_time = (retry_count + 1) * 30  # Wait 30s, then 60s
                print(f" ⏳ Rate limited, waiting {wait_time}s...", end='', flush=True)
                time.sleep(wait_time)
                return fetch_team_roster(abbrev, team_name, retry_count + 1)
            else:
                return []
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            roster_table = soup.find('table', {'id': 'roster'})
            
            if roster_table:
                players = []
                rows = roster_table.find('tbody').find_all('tr')
                
                for row in rows:
                    name_cell = row.find('th', {'data-stat': 'player'})
                    pos_cell = row.find('td', {'data-stat': 'pos'})
                    
                    if name_cell and pos_cell:
                        name = name_cell.get_text().strip()
                        position = pos_cell.get_text().strip()
                        
                        # Simplify position
                        if 'G' in position or 'PG' in position or 'SG' in position:
                            pos = 'G'
                        elif 'C' in position:
                            pos = 'C'
                        else:
                            pos = 'F'
                        
                        players.append({'name': name, 'position': pos})
                
                return players
        
        return []
    except Exception as e:
        print(f" Error: {e}", end='')
        return []

def fetch_all_rosters():
    """Fetch all 30 team rosters with proper rate limiting"""
    all_rosters = {}
    failed = []
    
    print("⏰ This will take 1-2 minutes with proper rate limiting...")
    print()
    
    for i, (abbrev, team_name) in enumerate(TEAMS.items(), 1):
        print(f"[{i}/30] {team_name}...", end='', flush=True)
        roster = fetch_team_roster(abbrev, team_name)
        
        if roster:
            all_rosters[team_name] = roster
            print(f" ✓ {len(roster)} players")
        else:
            print(f" ✗ Failed")
            failed.append(team_name)
    
    return all_rosters, failed

def save_to_python_file(rosters, filename='current_nba_rosters_live.py'):
    """Save to Python file"""
    with open(filename, 'w') as f:
        f.write('#!/usr/bin/env python3\n')
        f.write('"""\n')
        f.write('CURRENT NBA ROSTERS - Fetched from Basketball-Reference\n')
        f.write('Auto-generated from live 2025-26 season data\n')
        f.write('"""\n\n')
        f.write('CURRENT_NBA_ROSTERS = {\n')
        
        for team_name, roster in sorted(rosters.items()):
            f.write(f'    "{team_name}": [\n')
            for player in roster:
                name = player['name'].replace("'", "\\'")
                pos = player['position']
                f.write(f"        {{'name': '{name}', 'position': '{pos}'}},\n")
            f.write('    ],\n')
        
        f.write('}\n\n')
        f.write('def get_current_rosters():\n')
        f.write('    return CURRENT_NBA_ROSTERS\n')
    
    print(f"\n✅ Saved to {filename}")

if __name__ == "__main__":
    print("="*70)
    print("🏀 FETCHING CURRENT NBA ROSTERS")
    print("="*70)
    print()
    
    rosters, failed = fetch_all_rosters()
    
    if rosters:
        total = sum(len(r) for r in rosters.values())
        print()
        print("="*70)
        print(f"✅ SUCCESS: {len(rosters)}/30 teams ({total} players)")
        if failed:
            print(f"⚠️  Failed: {len(failed)} teams - {', '.join(failed[:3])}")
        print("="*70)
        
        save_to_python_file(rosters)
        
        # Show key teams
        print()
        for team in ['Los Angeles Lakers', 'Dallas Mavericks']:
            if team in rosters:
                print(f"\n{team} ({len(rosters[team])} players):")
                for p in rosters[team][:10]:
                    print(f"  - {p['name']:30s} {p['position']}")
        
        # Anthony Davis check
        print()
        print("="*70)
        print("ANTHONY DAVIS LOCATION CHECK:")
        ad_teams = []
        for team_name, roster in rosters.items():
            for player in roster:
                if 'Anthony Davis' in player['name']:
                    ad_teams.append(team_name)
        
        if ad_teams:
            for team in ad_teams:
                print(f"  ✓ Found on: {team}")
        else:
            print("  ℹ️  Anthony Davis not found in any roster")
        print("="*70)
    else:
        print("\n❌ Failed to fetch any rosters")
        print("Basketball-Reference may be rate-limiting.")
        print("Try again in a few minutes.")


