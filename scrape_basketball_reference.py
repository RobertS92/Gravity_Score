#!/usr/bin/env python3
"""
Scrape current rosters from Basketball-Reference.com
Most reliable source for current NBA data
"""
import requests
from bs4 import BeautifulSoup
import json
import time

TEAM_CODES = {
    'Atlanta Hawks': 'ATL',
    'Boston Celtics': 'BOS',
    'Brooklyn Nets': 'BRK',
    'Charlotte Hornets': 'CHO',
    'Chicago Bulls': 'CHI',
    'Cleveland Cavaliers': 'CLE',
    'Dallas Mavericks': 'DAL',
    'Denver Nuggets': 'DEN',
    'Detroit Pistons': 'DET',
    'Golden State Warriors': 'GSW',
    'Houston Rockets': 'HOU',
    'Indiana Pacers': 'IND',
    'LA Clippers': 'LAC',
    'Los Angeles Lakers': 'LAL',
    'Memphis Grizzlies': 'MEM',
    'Miami Heat': 'MIA',
    'Milwaukee Bucks': 'MIL',
    'Minnesota Timberwolves': 'MIN',
    'New Orleans Pelicans': 'NOP',
    'New York Knicks': 'NYK',
    'Oklahoma City Thunder': 'OKC',
    'Orlando Magic': 'ORL',
    'Philadelphia 76ers': 'PHI',
    'Phoenix Suns': 'PHO',
    'Portland Trail Blazers': 'POR',
    'Sacramento Kings': 'SAC',
    'San Antonio Spurs': 'SAS',
    'Toronto Raptors': 'TOR',
    'Utah Jazz': 'UTA',
    'Washington Wizards': 'WAS'
}


def scrape_team_roster(team_code, team_name):
    """Scrape roster from Basketball-Reference"""
    url = f"https://www.basketball-reference.com/teams/{team_code}/2026.html"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find roster table
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
                        
                        # Map positions to our format
                        if 'G' in position:
                            pos = 'G'
                        elif 'F' in position:
                            pos = 'F'
                        elif 'C' in position:
                            pos = 'C'
                        else:
                            pos = 'F'
                        
                        players.append({'name': name, 'position': pos})
                
                return players
            else:
                print(f"  ⚠️  No roster table found for {team_name}")
                return []
        else:
            print(f"  ❌ Failed to fetch {team_name}: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"  ❌ Error scraping {team_name}: {e}")
        return []


def scrape_all_rosters():
    """Scrape all 30 NBA team rosters"""
    all_rosters = {}
    
    for team_name, team_code in TEAM_CODES.items():
        print(f"Scraping {team_name}...")
        roster = scrape_team_roster(team_code, team_name)
        
        if roster:
            all_rosters[team_name] = roster
            print(f"  ✓ Got {len(roster)} players")
        else:
            print(f"  ✗ Failed")
        
        time.sleep(1)  # Be respectful to the server
    
    return all_rosters


if __name__ == "__main__":
    print("="*70)
    print("SCRAPING CURRENT ROSTERS FROM BASKETBALL-REFERENCE")
    print("="*70)
    print()
    
    # Test with Lakers and Mavericks first
    print("Testing with key teams:\n")
    
    print("1. Los Angeles Lakers:")
    lakers = scrape_team_roster('LAL', 'Lakers')
    if lakers:
        for p in lakers[:5]:
            print(f"   - {p['name']:25s} {p['position']}")
        ad_found = any('Davis' in p['name'] for p in lakers)
        print(f"   Anthony Davis on Lakers? {ad_found}")
    
    print()
    print("2. Dallas Mavericks:")
    mavs = scrape_team_roster('DAL', 'Mavericks')
    if mavs:
        for p in mavs[:5]:
            print(f"   - {p['name']:25s} {p['position']}")
        ad_found = any('Davis' in p['name'] for p in mavs)
        print(f"   Anthony Davis on Mavericks? {ad_found}")
    
    print()
    print("="*70)
    print("To scrape all 30 teams:")
    print("  all_rosters = scrape_all_rosters()")
    print("  # Save to file for pipeline")
    print("="*70)


