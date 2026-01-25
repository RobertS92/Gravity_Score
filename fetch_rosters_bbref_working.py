#!/usr/bin/env python3
"""
Fetch current NBA rosters from Basketball-Reference (WORKING)
"""
import requests
from bs4 import BeautifulSoup
import time
import json

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

def fetch_team_roster(abbrev, team_name):
    """Fetch roster from Basketball-Reference"""
    bbref_code = BBREF_CODES.get(abbrev, abbrev)
    url = f"https://www.basketball-reference.com/teams/{bbref_code}/2026.html"
    
    try:
        response = requests.get(url, timeout=10)
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
                        else:  # F, PF, SF
                            pos = 'F'
                        
                        players.append({'name': name, 'position': pos})
                
                return players
        
        return []
    except Exception as e:
        print(f"  Error: {e}")
        return []

def fetch_all_rosters():
    """Fetch all 30 team rosters"""
    all_rosters = {}
    
    for abbrev, team_name in TEAMS.items():
        print(f"Fetching {team_name}...", end='', flush=True)
        roster = fetch_team_roster(abbrev, team_name)
        
        if roster:
            all_rosters[team_name] = roster
            print(f" ✓ {len(roster)} players")
        else:
            print(f" ✗ Failed")
        
        time.sleep(0.5)  # Be respectful
    
    return all_rosters

def save_to_python_file(rosters, filename='current_nba_rosters_live.py'):
    """Save to Python file for import"""
    with open(filename, 'w') as f:
        f.write('#!/usr/bin/env python3\n')
        f.write('"""\n')
        f.write('CURRENT NBA ROSTERS - Fetched from Basketball-Reference\n')
        f.write(f'Auto-generated from live data\n')
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
    print("🏀 FETCHING CURRENT NBA ROSTERS (Basketball-Reference)")
    print("="*70)
    print()
    
    rosters = fetch_all_rosters()
    
    if rosters:
        total = sum(len(r) for r in rosters.values())
        print()
        print("="*70)
        print(f"✅ SUCCESS: {len(rosters)}/30 teams ({total} players)")
        print("="*70)
        
        save_to_python_file(rosters)
        
        # Show Lakers and Mavericks
        print()
        for team in ['Los Angeles Lakers', 'Dallas Mavericks', 'Golden State Warriors']:
            if team in rosters:
                print(f"\n{team} ({len(rosters[team])} players):")
                for p in rosters[team][:8]:
                    print(f"  - {p['name']:30s} {p['position']}")
        
        # Check for Anthony Davis
        print()
        print("="*70)
        print("ANTHONY DAVIS CHECK:")
        for team_name, roster in rosters.items():
            for player in roster:
                if 'Anthony Davis' in player['name']:
                    print(f"  ✓ Found on: {team_name}")
        print("="*70)
    else:
        print("\n❌ Failed to fetch rosters")


