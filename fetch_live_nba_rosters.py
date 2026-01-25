#!/usr/bin/env python3
"""
Automatically fetch CURRENT NBA rosters from multiple sources
Tries multiple APIs with fallbacks for reliability
"""
import requests
from bs4 import BeautifulSoup
import json
import time
from typing import Dict, List, Optional

# Team mappings
TEAMS = {
    'ATL': 'Atlanta Hawks',
    'BOS': 'Boston Celtics', 
    'BKN': 'Brooklyn Nets',
    'CHA': 'Charlotte Hornets',
    'CHI': 'Chicago Bulls',
    'CLE': 'Cleveland Cavaliers',
    'DAL': 'Dallas Mavericks',
    'DEN': 'Denver Nuggets',
    'DET': 'Detroit Pistons',
    'GSW': 'Golden State Warriors',
    'HOU': 'Houston Rockets',
    'IND': 'Indiana Pacers',
    'LAC': 'LA Clippers',
    'LAL': 'Los Angeles Lakers',
    'MEM': 'Memphis Grizzlies',
    'MIA': 'Miami Heat',
    'MIL': 'Milwaukee Bucks',
    'MIN': 'Minnesota Timberwolves',
    'NOP': 'New Orleans Pelicans',
    'NYK': 'New York Knicks',
    'OKC': 'Oklahoma City Thunder',
    'ORL': 'Orlando Magic',
    'PHI': 'Philadelphia 76ers',
    'PHX': 'Phoenix Suns',
    'POR': 'Portland Trail Blazers',
    'SAC': 'Sacramento Kings',
    'SAS': 'San Antonio Spurs',
    'TOR': 'Toronto Raptors',
    'UTA': 'Utah Jazz',
    'WAS': 'Washington Wizards'
}

BBREF_CODES = {
    'ATL': 'ATL', 'BOS': 'BOS', 'BKN': 'BRK', 'CHA': 'CHO', 'CHI': 'CHI',
    'CLE': 'CLE', 'DAL': 'DAL', 'DEN': 'DEN', 'DET': 'DET', 'GSW': 'GSW',
    'HOU': 'HOU', 'IND': 'IND', 'LAC': 'LAC', 'LAL': 'LAL', 'MEM': 'MEM',
    'MIA': 'MIA', 'MIL': 'MIL', 'MIN': 'MIN', 'NOP': 'NOP', 'NYK': 'NYK',
    'OKC': 'OKC', 'ORL': 'ORL', 'PHI': 'PHI', 'PHX': 'PHO', 'POR': 'POR',
    'SAC': 'SAC', 'SAS': 'SAS', 'TOR': 'TOR', 'UTA': 'UTA', 'WAS': 'WAS'
}


def fetch_from_basketball_reference(team_abbrev: str) -> Optional[List[Dict]]:
    """
    Fetch roster from Basketball-Reference (most reliable)
    """
    bbref_code = BBREF_CODES.get(team_abbrev)
    if not bbref_code:
        return None
    
    url = f"https://www.basketball-reference.com/teams/{bbref_code}/2026.html"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
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
                        if 'G' in position:
                            pos = 'G'
                        elif 'C' in position:
                            pos = 'C'
                        else:
                            pos = 'F'
                        
                        players.append({'name': name, 'position': pos})
                
                return players if players else None
    except Exception as e:
        print(f"    BBRef error: {e}")
    
    return None


def fetch_from_espn_site(team_abbrev: str) -> Optional[List[Dict]]:
    """
    Fetch from ESPN website (scrape HTML)
    """
    espn_team_names = {
        'ATL': 'hawks', 'BOS': 'celtics', 'BKN': 'nets', 'CHA': 'hornets',
        'CHI': 'bulls', 'CLE': 'cavaliers', 'DAL': 'mavericks', 'DEN': 'nuggets',
        'DET': 'pistons', 'GSW': 'warriors', 'HOU': 'rockets', 'IND': 'pacers',
        'LAC': 'clippers', 'LAL': 'lakers', 'MEM': 'grizzlies', 'MIA': 'heat',
        'MIL': 'bucks', 'MIN': 'timberwolves', 'NOP': 'pelicans', 'NYK': 'knicks',
        'OKC': 'thunder', 'ORL': 'magic', 'PHI': '76ers', 'PHX': 'suns',
        'POR': 'blazers', 'SAC': 'kings', 'SAS': 'spurs', 'TOR': 'raptors',
        'UTA': 'jazz', 'WAS': 'wizards'
    }
    
    team_slug = espn_team_names.get(team_abbrev)
    if not team_slug:
        return None
    
    url = f"https://www.espn.com/nba/team/roster/_/name/{team_abbrev.lower()}/{team_slug}"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find roster table
            tables = soup.find_all('table')
            players = []
            
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        # Try to extract name and position
                        name_link = cells[0].find('a')
                        if name_link:
                            name = name_link.get_text().strip()
                            pos = cells[2].get_text().strip() if len(cells) > 2 else 'F'
                            
                            # Simplify position
                            if 'G' in pos or 'PG' in pos or 'SG' in pos:
                                pos = 'G'
                            elif 'C' in pos:
                                pos = 'C'
                            else:
                                pos = 'F'
                            
                            if name and len(name) > 2:
                                players.append({'name': name, 'position': pos})
            
            return players if players else None
    except Exception as e:
        print(f"    ESPN site error: {e}")
    
    return None


def fetch_roster_with_fallback(team_abbrev: str, team_name: str) -> List[Dict]:
    """
    Try multiple sources with fallback
    """
    print(f"  Fetching {team_name}...", end='', flush=True)
    
    # Try 1: Basketball-Reference (most reliable)
    roster = fetch_from_basketball_reference(team_abbrev)
    if roster and len(roster) > 5:
        print(f" ✓ BBRef ({len(roster)} players)")
        return roster
    
    # Try 2: ESPN website scraping
    roster = fetch_from_espn_site(team_abbrev)
    if roster and len(roster) > 5:
        print(f" ✓ ESPN ({len(roster)} players)")
        return roster
    
    print(f" ✗ Failed")
    return []


def fetch_all_current_rosters(progress=True) -> Dict[str, List[Dict]]:
    """
    Fetch all NBA rosters with multiple fallback sources
    """
    all_rosters = {}
    failed_teams = []
    
    for abbrev, team_name in TEAMS.items():
        roster = fetch_roster_with_fallback(abbrev, team_name)
        
        if roster:
            all_rosters[team_name] = roster
        else:
            failed_teams.append(team_name)
        
        time.sleep(0.5)  # Be respectful
    
    if failed_teams:
        print(f"\n⚠️  Failed to fetch: {', '.join(failed_teams)}")
    
    return all_rosters


def save_to_python_file(rosters: Dict, filename: str = 'live_nba_rosters_auto.py'):
    """
    Save rosters to Python file that can be imported
    """
    with open(filename, 'w') as f:
        f.write('#!/usr/bin/env python3\n')
        f.write('"""\n')
        f.write('AUTO-GENERATED NBA ROSTERS\n')
        f.write('Fetched from Basketball-Reference and ESPN\n')
        f.write('Generated automatically - DO NOT EDIT MANUALLY\n')
        f.write('"""\n\n')
        f.write('LIVE_NBA_ROSTERS = {\n')
        
        for team_name, roster in sorted(rosters.items()):
            f.write(f'    "{team_name}": [\n')
            for player in roster:
                name = player['name'].replace("'", "\\'")
                pos = player['position']
                f.write(f"        {{'name': '{name}', 'position': '{pos}'}},\n")
            f.write('    ],\n')
        
        f.write('}\n\n')
        f.write('def get_live_rosters():\n')
        f.write('    """Returns live NBA rosters"""\n')
        f.write('    return LIVE_NBA_ROSTERS\n')
    
    print(f"\n✅ Saved to {filename}")
    return filename


if __name__ == "__main__":
    print("="*70)
    print("🏀 FETCHING LIVE NBA ROSTERS")
    print("="*70)
    print()
    print("Trying multiple sources with fallbacks...")
    print()
    
    rosters = fetch_all_current_rosters()
    
    if rosters:
        total_players = sum(len(r) for r in rosters.values())
        print()
        print("="*70)
        print(f"✅ SUCCESS: Fetched {len(rosters)}/30 teams ({total_players} players)")
        print("="*70)
        
        # Save to file
        filename = save_to_python_file(rosters)
        
        # Show sample
        print()
        print("Sample teams:")
        for team in ['Los Angeles Lakers', 'Dallas Mavericks', 'Golden State Warriors']:
            if team in rosters:
                print(f"\n{team} ({len(rosters[team])} players):")
                for player in rosters[team][:5]:
                    print(f"  - {player['name']:25s} {player['position']}")
        
        print()
        print("="*70)
        print(f"✅ Import with: from {filename.replace('.py', '')} import get_live_rosters")
        print("="*70)
    else:
        print("\n❌ Failed to fetch any rosters")
        print("Check your internet connection and try again")


