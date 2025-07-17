#!/usr/bin/env python3
"""
Test scraper to debug the NFL roster extraction issues
"""

import requests
from bs4 import BeautifulSoup
import json
import time

def test_nfl_roster_scraping():
    """Test scraping NFL rosters with current website structure."""
    
    # Test with a specific team
    team = "49ers"
    
    # Try different URL patterns
    urls_to_test = [
        f"https://www.nfl.com/teams/san-francisco-49ers/roster",
        f"https://www.nfl.com/teams/sf/roster",
        f"https://www.nfl.com/teams/sf/roster/",
        f"https://www.nfl.com/teams/san-francisco-49ers/roster/",
    ]
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    
    for url in urls_to_test:
        print(f"\n🔍 Testing URL: {url}")
        print("-" * 60)
        
        try:
            response = session.get(url, timeout=10)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for various roster elements
                print("\n🔍 Searching for roster elements:")
                
                # Look for tables
                tables = soup.find_all('table')
                print(f"Found {len(tables)} tables")
                
                # Look for roster-related divs
                roster_divs = soup.find_all('div', class_=lambda x: x and 'roster' in x.lower())
                print(f"Found {len(roster_divs)} roster divs")
                
                # Look for player-related elements
                player_elements = soup.find_all(lambda tag: tag.name and 'player' in str(tag.get('class', [])).lower())
                print(f"Found {len(player_elements)} player elements")
                
                # Try to find any structured data
                scripts = soup.find_all('script', type='application/ld+json')
                print(f"Found {len(scripts)} JSON-LD scripts")
                
                # Look for any elements containing player names
                text_content = soup.get_text()
                common_player_indicators = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']
                found_positions = [pos for pos in common_player_indicators if pos in text_content]
                print(f"Found positions in text: {found_positions}")
                
                # Try to extract some sample data
                if tables:
                    print("\n📊 Sample table data:")
                    for i, table in enumerate(tables[:2]):  # Check first 2 tables
                        rows = table.find_all('tr')
                        print(f"Table {i+1}: {len(rows)} rows")
                        
                        if rows:
                            # Show first few rows
                            for j, row in enumerate(rows[:3]):
                                cells = row.find_all(['td', 'th'])
                                cell_texts = [cell.get_text(strip=True) for cell in cells]
                                print(f"  Row {j+1}: {cell_texts}")
                
                # Look for roster data in script tags (React apps often use this)
                for script in soup.find_all('script'):
                    script_text = script.get_text()
                    if 'roster' in script_text.lower() or 'players' in script_text.lower():
                        print(f"\n🔍 Found roster/player data in script tag:")
                        print(f"Script length: {len(script_text)} characters")
                        # Look for JSON-like structures
                        if '{' in script_text and '}' in script_text:
                            print("Contains JSON-like data")
                            # Try to find player names
                            if any(name in script_text for name in ['Brock', 'Purdy', 'McCaffrey', 'Deebo']):
                                print("✅ Found 49ers player names in script!")
                
                break  # If successful, don't try other URLs
                
            else:
                print(f"❌ Failed with status {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        time.sleep(1)  # Rate limiting

def test_alternative_sources():
    """Test alternative sources for NFL roster data."""
    
    print("\n\n🔄 Testing Alternative Sources")
    print("=" * 60)
    
    # Test ESPN
    espn_url = "https://www.espn.com/nfl/team/roster/_/name/sf"
    print(f"\n🔍 Testing ESPN: {espn_url}")
    
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        response = session.get(espn_url, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            tables = soup.find_all('table')
            print(f"Found {len(tables)} tables")
            
            # Look for roster tables
            for i, table in enumerate(tables):
                rows = table.find_all('tr')
                if len(rows) > 5:  # Likely a roster table
                    print(f"\nTable {i+1} sample data:")
                    for j, row in enumerate(rows[:3]):
                        cells = row.find_all(['td', 'th'])
                        cell_texts = [cell.get_text(strip=True) for cell in cells]
                        print(f"  Row {j+1}: {cell_texts}")
                        
    except Exception as e:
        print(f"❌ ESPN Error: {e}")

if __name__ == "__main__":
    print("🏈 NFL Roster Scraping Test")
    print("=" * 60)
    
    test_nfl_roster_scraping()
    test_alternative_sources()
    
    print("\n\n✅ Test completed!")