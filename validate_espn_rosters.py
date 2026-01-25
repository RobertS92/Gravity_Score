#!/usr/bin/env python3
"""
Get rosters from ESPN API and VALIDATE team assignments
Strategy: Get player list from roster API, then verify each player's actual team
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import importlib.util
import time

# Load scrape module
spec = importlib.util.spec_from_file_location("scrape", Path("gravity/scrape"))
scrape_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scrape_module)

DirectSportsAPI = scrape_module.DirectSportsAPI

def get_validated_roster(api, team_abbrev: str, team_name: str):
    """
    Get roster and validate each player's actual team
    Filter out players who don't actually play for this team
    """
    print(f"  Processing {team_name}...", end='', flush=True)
    
    # Step 1: Get roster from ESPN (may have wrong players)
    roster = api.get_espn_nba_roster(team_abbrev)
    
    if not roster:
        print(" ✗ No roster data")
        return []
    
    # Step 2: Validate each player
    validated = []
    wrong_team = []
    
    for player_info in roster:
        player_name = player_info.get('name', '')
        if not player_name:
            continue
        
        # Check player's actual team
        try:
            player_data = api.get_espn_nba_player(player_name, team_name)
            
            if player_data and 'team' in player_data:
                actual_team = player_data['team'].get('displayName', '')
                
                # Check if team matches
                if team_name.lower() in actual_team.lower() or actual_team.lower() in team_name.lower():
                    validated.append(player_info)
                else:
                    wrong_team.append(f"{player_name} (actually {actual_team})")
        except:
            # If we can't validate, skip this player
            pass
        
        time.sleep(0.1)  # Rate limit
    
    if wrong_team:
        print(f" ⚠️  {len(validated)} valid, removed {len(wrong_team)}: {', '.join(wrong_team[:3])}")
    else:
        print(f" ✓ {len(validated)} players validated")
    
    return validated


def get_all_validated_rosters():
    """
    Get and validate rosters for all 30 teams
    """
    teams = {
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
    
    api = DirectSportsAPI()
    all_rosters = {}
    
    for abbrev, team_name in teams.items():
        roster = get_validated_roster(api, abbrev, team_name)
        if roster:
            all_rosters[team_name] = roster
    
    return all_rosters


def save_validated_rosters(rosters, filename='validated_nba_rosters.py'):
    """
    Save validated rosters to Python file
    """
    with open(filename, 'w') as f:
        f.write('#!/usr/bin/env python3\n')
        f.write('"""\n')
        f.write('VALIDATED NBA ROSTERS - Team assignments verified\n')
        f.write('Each player checked against their actual current team\n')
        f.write('"""\n\n')
        f.write('VALIDATED_NBA_ROSTERS = {\n')
        
        for team_name, roster in sorted(rosters.items()):
            f.write(f'    "{team_name}": [\n')
            for player in roster:
                name = player['name'].replace("'", "\\'")
                pos = player.get('position', 'F')
                f.write(f"        {{'name': '{name}', 'position': '{pos}'}},\n")
            f.write('    ],\n')
        
        f.write('}\n\n')
        f.write('def get_validated_rosters():\n')
        f.write('    return VALIDATED_NBA_ROSTERS\n')
    
    print(f"\n✅ Saved to {filename}")


if __name__ == "__main__":
    print("="*70)
    print("🏀 ESPN ROSTER VALIDATION")
    print("="*70)
    print()
    print("Getting rosters from ESPN and validating team assignments...")
    print("This may take a few minutes...")
    print()
    
    rosters = get_all_validated_rosters()
    
    if rosters:
        total_players = sum(len(r) for r in rosters.values())
        print()
        print("="*70)
        print(f"✅ Validated {len(rosters)}/30 teams ({total_players} players)")
        print("="*70)
        
        save_validated_rosters(rosters)
        
        # Show key teams
        print()
        for team in ['Los Angeles Lakers', 'Dallas Mavericks']:
            if team in rosters:
                print(f"\n{team} ({len(rosters[team])} players):")
                for p in rosters[team][:5]:
                    print(f"  - {p['name']:25s} {p.get('position', 'F')}")
        
        print()
        print("="*70)
        print("Use validated_nba_rosters.py in pipeline")
        print("="*70)
    else:
        print("\n❌ No rosters validated")


