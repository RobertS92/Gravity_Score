#!/usr/bin/env python3
"""
Get CURRENT NBA rosters from live sources
Avoids hardcoded data that becomes outdated
"""
import requests
import json
from typing import Dict, List

def get_current_team_roster_from_nba_api(team_abbreviation: str) -> List[Dict]:
    """
    Get current roster from NBA API (most reliable source)
    
    Args:
        team_abbreviation: e.g., 'LAL', 'BOS', 'GSW'
    
    Returns:
        List of player dicts with name and position
    """
    # Map team abbreviations to NBA.com team IDs
    TEAM_IDS = {
        'ATL': '1610612737', 'BOS': '1610612738', 'BKN': '1610612751',
        'CHA': '1610612766', 'CHI': '1610612741', 'CLE': '1610612739',
        'DAL': '1610612742', 'DEN': '1610612743', 'DET': '1610612765',
        'GSW': '1610612744', 'HOU': '1610612745', 'IND': '1610612754',
        'LAC': '1610612746', 'LAL': '1610612747', 'MEM': '1610612763',
        'MIA': '1610612748', 'MIL': '1610612749', 'MIN': '1610612750',
        'NOP': '1610612740', 'NYK': '1610612752', 'OKC': '1610612760',
        'ORL': '1610612753', 'PHI': '1610612755', 'PHX': '1610612756',
        'POR': '1610612757', 'SAC': '1610612758', 'SAS': '1610612759',
        'TOR': '1610612761', 'UTA': '1610612762', 'WAS': '1610612764'
    }
    
    team_id = TEAM_IDS.get(team_abbreviation.upper())
    if not team_id:
        print(f"Unknown team: {team_abbreviation}")
        return []
    
    # NBA.com roster endpoint
    url = f"https://stats.nba.com/stats/commonteamroster"
    params = {
        'LeagueID': '00',
        'Season': '2025-26',  # Current season
        'TeamID': team_id
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            roster = []
            
            # Parse roster data
            if 'resultSets' in data and len(data['resultSets']) > 0:
                result_set = data['resultSets'][0]
                headers_list = result_set.get('headers', [])
                rows = result_set.get('rowSet', [])
                
                # Find column indices
                name_idx = headers_list.index('PLAYER') if 'PLAYER' in headers_list else None
                pos_idx = headers_list.index('POSITION') if 'POSITION' in headers_list else None
                
                for row in rows:
                    if name_idx is not None:
                        player = {
                            'name': row[name_idx],
                            'position': row[pos_idx] if pos_idx is not None else 'F'
                        }
                        roster.append(player)
            
            return roster
        else:
            print(f"API returned status {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Error fetching roster: {e}")
        return []


def get_all_current_nba_rosters() -> Dict[str, List[Dict]]:
    """
    Get current rosters for all 30 NBA teams from live API
    
    Returns:
        Dict of {team_name: [players]}
    """
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
    
    all_rosters = {}
    
    for abbrev, team_name in TEAMS.items():
        print(f"Fetching {team_name}...")
        roster = get_current_team_roster_from_nba_api(abbrev)
        all_rosters[team_name] = roster
        print(f"  ✓ Got {len(roster)} players")
    
    return all_rosters


def save_rosters_to_file(rosters: Dict, filename: str = 'current_nba_rosters.json'):
    """Save rosters to JSON file"""
    with open(filename, 'w') as f:
        json.dump(rosters, f, indent=2)
    print(f"\n✅ Saved to {filename}")


if __name__ == "__main__":
    print("="*70)
    print("FETCHING CURRENT NBA ROSTERS FROM LIVE API")
    print("="*70)
    print()
    
    # Test with Lakers first
    print("Testing with Lakers:")
    lakers_roster = get_current_team_roster_from_nba_api('LAL')
    
    if lakers_roster:
        print(f"\n✅ Lakers Roster ({len(lakers_roster)} players):")
        for player in lakers_roster[:10]:
            print(f"  - {player['name']:30s} {player['position']}")
        
        # Check if AD is there
        ad_found = any('Anthony Davis' in p['name'] for p in lakers_roster)
        if ad_found:
            print("\n⚠️  Anthony Davis found on Lakers (unexpected!)")
        else:
            print("\n✅ Anthony Davis NOT on Lakers (correct - he's on Mavericks)")
    else:
        print("❌ Failed to fetch Lakers roster")
        print("\nTrying alternative: Basketball Reference scraping...")
        print("Or manually verify at: https://www.nba.com/lakers/roster")
    
    print()
    print("="*70)
    print("To get ALL team rosters, uncomment below:")
    print("# all_rosters = get_all_current_nba_rosters()")
    print("# save_rosters_to_file(all_rosters)")
    print("="*70)


