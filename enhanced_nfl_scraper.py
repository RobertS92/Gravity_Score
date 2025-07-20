#!/usr/bin/env python3
"""
Enhanced NFL Data Scraper - Complete Team Roster Extraction
Integrates improved scraping methods to extract full team rosters (90+ players).
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
from urllib.parse import quote_plus
import logging
from datetime import datetime
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedNFLScraper:
    """Enhanced NFL scraper that extracts complete team rosters from multiple sources."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1'
        })
        
        # NFL Teams mapping
        self.nfl_teams = {
            "49ers": "san-francisco-49ers",
            "bears": "chicago-bears",
            "bengals": "cincinnati-bengals",
            "bills": "buffalo-bills",
            "broncos": "denver-broncos",
            "browns": "cleveland-browns",
            "buccaneers": "tampa-bay-buccaneers",
            "cardinals": "arizona-cardinals",
            "chargers": "los-angeles-chargers",
            "chiefs": "kansas-city-chiefs",
            "colts": "indianapolis-colts",
            "commanders": "washington-commanders",
            "cowboys": "dallas-cowboys",
            "dolphins": "miami-dolphins",
            "eagles": "philadelphia-eagles",
            "falcons": "atlanta-falcons",
            "giants": "new-york-giants",
            "jaguars": "jacksonville-jaguars",
            "jets": "new-york-jets",
            "lions": "detroit-lions",
            "packers": "green-bay-packers",
            "panthers": "carolina-panthers",
            "patriots": "new-england-patriots",
            "raiders": "las-vegas-raiders",
            "rams": "los-angeles-rams",
            "ravens": "baltimore-ravens",
            "saints": "new-orleans-saints",
            "seahawks": "seattle-seahawks",
            "steelers": "pittsburgh-steelers",
            "texans": "houston-texans",
            "titans": "tennessee-titans",
            "vikings": "minnesota-vikings"
        }
        
        # ESPN team mapping
        self.espn_teams = {
            "49ers": "sf",
            "bears": "chi",
            "bengals": "cin",
            "bills": "buf",
            "broncos": "den",
            "browns": "cle",
            "buccaneers": "tb",
            "cardinals": "ari",
            "chargers": "lac",
            "chiefs": "kc",
            "colts": "ind",
            "commanders": "wsh",
            "cowboys": "dal",
            "dolphins": "mia",
            "eagles": "phi",
            "falcons": "atl",
            "giants": "nyg",
            "jaguars": "jax",
            "jets": "nyj",
            "lions": "det",
            "packers": "gb",
            "panthers": "car",
            "patriots": "ne",
            "raiders": "lv",
            "rams": "lar",
            "ravens": "bal",
            "saints": "no",
            "seahawks": "sea",
            "steelers": "pit",
            "texans": "hou",
            "titans": "ten",
            "vikings": "min"
        }
    
    def extract_complete_team_roster(self, team: str) -> List[Dict[str, Any]]:
        """Extract complete team roster using multiple sources."""
        logger.info(f"Extracting complete roster for {team}")
        
        all_players = []
        
        # Method 1: NFL.com (Primary source)
        nfl_players = self._scrape_nfl_com_roster(team)
        if nfl_players:
            all_players.extend(nfl_players)
            logger.info(f"NFL.com: Found {len(nfl_players)} players")
        
        # Method 2: ESPN (Secondary source)
        espn_players = self._scrape_espn_roster(team)
        if espn_players:
            # Merge with NFL.com data (avoid duplicates)
            all_players = self._merge_player_data(all_players, espn_players)
            logger.info(f"ESPN: Added/merged {len(espn_players)} players")
        
        # Method 3: Pro Football Reference (Tertiary source)
        pfr_players = self._scrape_pfr_roster(team)
        if pfr_players:
            all_players = self._merge_player_data(all_players, pfr_players)
            logger.info(f"PFR: Added/merged {len(pfr_players)} players")
        
        # Clean and validate data
        validated_players = []
        for player in all_players:
            if player.get('name') and player.get('position'):
                validated_players.append(self._clean_player_data(player))
        
        logger.info(f"✅ Total validated players for {team}: {len(validated_players)}")
        return validated_players
    
    def _scrape_nfl_com_roster(self, team: str) -> List[Dict[str, Any]]:
        """Scrape NFL.com roster page."""
        try:
            team_slug = self.nfl_teams.get(team.lower(), team.lower())
            url = f"https://www.nfl.com/teams/{team_slug}/roster/"
            
            time.sleep(2)  # Rate limiting
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            players = []
            
            # Look for roster table
            roster_table = soup.find('table', class_='d3-o-table')
            if not roster_table:
                roster_table = soup.find('table')
            
            if roster_table:
                rows = roster_table.find_all('tr')[1:]  # Skip header
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 4:
                        # Extract player data
                        name_cell = cells[0]
                        name_link = name_cell.find('a')
                        name = name_link.get_text().strip() if name_link else name_cell.get_text().strip()
                        
                        # Get raw height and convert immediately
                        raw_height = cells[4].get_text().strip() if len(cells) > 4 else None
                        converted_height = self._convert_height_from_inches(raw_height)
                        
                        player_data = {
                            'name': name,
                            'jersey_number': self._extract_number(cells[1].get_text()),
                            'position': cells[2].get_text().strip(),
                            'status': cells[3].get_text().strip() if len(cells) > 3 else None,
                            'height': converted_height,
                            'weight': self._extract_weight(cells[5].get_text()) if len(cells) > 5 else None,
                            'experience': cells[6].get_text().strip() if len(cells) > 6 else None,
                            'college': cells[7].get_text().strip() if len(cells) > 7 else None,
                            'team': team,
                            'data_source': 'nfl.com'
                        }
                        
                        if name and name != '--':
                            players.append(player_data)
            
            # Alternative: Look for player cards
            if not players:
                player_cards = soup.find_all('div', class_='nfl-c-roster-card')
                for card in player_cards:
                    name_elem = card.find('h3') or card.find('h4') or card.find('h5')
                    if name_elem:
                        name = name_elem.get_text().strip()
                        
                        # Extract other data from card
                        details = card.find_all('span') + card.find_all('div')
                        player_data = {
                            'name': name,
                            'team': team,
                            'data_source': 'nfl.com'
                        }
                        
                        for detail in details:
                            text = detail.get_text().strip()
                            if text.startswith('#'):
                                player_data['jersey_number'] = self._extract_number(text)
                            elif text in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF', 'ST']:
                                player_data['position'] = text
                        
                        players.append(player_data)
            
            return players
            
        except Exception as e:
            logger.error(f"Error scraping NFL.com roster for {team}: {e}")
            return []
    
    def _scrape_espn_roster(self, team: str) -> List[Dict[str, Any]]:
        """Scrape ESPN roster page."""
        try:
            team_slug = self.espn_teams.get(team.lower(), team.lower())
            url = f"https://www.espn.com/nfl/team/roster/_/name/{team_slug}"
            
            time.sleep(2)  # Rate limiting
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            players = []
            
            # Look for roster tables
            roster_tables = soup.find_all('table', class_='Table')
            
            for table in roster_tables:
                rows = table.find_all('tr')[1:]  # Skip header
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        # Extract player name (usually first cell)
                        name_cell = cells[0]
                        name_link = name_cell.find('a')
                        name = name_link.get_text().strip() if name_link else name_cell.get_text().strip()
                        
                        player_data = {
                            'name': name,
                            'jersey_number': self._extract_number(cells[1].get_text()) if len(cells) > 1 else None,
                            'position': cells[2].get_text().strip() if len(cells) > 2 else None,
                            'height': cells[3].get_text().strip() if len(cells) > 3 else None,
                            'weight': self._extract_weight(cells[4].get_text()) if len(cells) > 4 else None,
                            'age': self._extract_number(cells[5].get_text()) if len(cells) > 5 else None,
                            'team': team,
                            'data_source': 'espn.com'
                        }
                        
                        if name and name != '--':
                            players.append(player_data)
            
            return players
            
        except Exception as e:
            logger.error(f"Error scraping ESPN roster for {team}: {e}")
            return []
    
    def _scrape_pfr_roster(self, team: str) -> List[Dict[str, Any]]:
        """Scrape Pro Football Reference roster page."""
        try:
            # PFR uses different team abbreviations
            pfr_mapping = {
                '49ers': 'sfo', 'bears': 'chi', 'bengals': 'cin', 'bills': 'buf',
                'broncos': 'den', 'browns': 'cle', 'buccaneers': 'tam', 'cardinals': 'crd',
                'chargers': 'lac', 'chiefs': 'kan', 'colts': 'clt', 'commanders': 'was',
                'cowboys': 'dal', 'dolphins': 'mia', 'eagles': 'phi', 'falcons': 'atl',
                'giants': 'nyg', 'jaguars': 'jax', 'jets': 'nyj', 'lions': 'det',
                'packers': 'gnb', 'panthers': 'car', 'patriots': 'nwe', 'raiders': 'rai',
                'rams': 'ram', 'ravens': 'rav', 'saints': 'nor', 'seahawks': 'sea',
                'steelers': 'pit', 'texans': 'htx', 'titans': 'oti', 'vikings': 'min'
            }
            
            team_slug = pfr_mapping.get(team.lower(), team.lower())
            url = f"https://www.pro-football-reference.com/teams/{team_slug}/2024_roster.htm"
            
            time.sleep(3)  # Be respectful to PFR
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            players = []
            
            # Look for roster table
            roster_table = soup.find('table', id='games_played_team')
            if not roster_table:
                roster_table = soup.find('table', {'data-stat': 'player'})
            
            if roster_table:
                rows = roster_table.find_all('tr')[1:]  # Skip header
                for row in rows:
                    if 'thead' in str(row):  # Skip sub-headers
                        continue
                    
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        # Extract player data using data-stat attributes
                        player_data = {
                            'team': team,
                            'data_source': 'pro-football-reference.com'
                        }
                        
                        for cell in cells:
                            stat = cell.get('data-stat')
                            value = cell.get_text().strip()
                            
                            if stat == 'player':
                                link = cell.find('a')
                                if link:
                                    player_data['name'] = link.get_text().strip()
                                    player_data['pfr_id'] = link.get('href', '').split('/')[-1].replace('.htm', '')
                            elif stat == 'pos':
                                player_data['position'] = value
                            elif stat == 'jersey_number':
                                player_data['jersey_number'] = self._extract_number(value)
                            elif stat == 'age':
                                player_data['age'] = self._extract_number(value)
                            elif stat == 'height':
                                player_data['height'] = value
                            elif stat == 'weight':
                                player_data['weight'] = self._extract_weight(value)
                            elif stat == 'college':
                                player_data['college'] = value
                        
                        if player_data.get('name'):
                            players.append(player_data)
            
            return players
            
        except Exception as e:
            logger.error(f"Error scraping PFR roster for {team}: {e}")
            return []
    
    def _merge_player_data(self, existing_players: List[Dict[str, Any]], new_players: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge player data from multiple sources, avoiding duplicates."""
        merged = existing_players.copy()
        
        for new_player in new_players:
            # Check if player already exists (by name similarity)
            found = False
            for existing_player in merged:
                if self._names_similar(existing_player.get('name', ''), new_player.get('name', '')):
                    # Merge data (new data takes precedence for missing fields)
                    for key, value in new_player.items():
                        if value and not existing_player.get(key):
                            existing_player[key] = value
                    found = True
                    break
            
            if not found:
                merged.append(new_player)
        
        return merged
    
    def _names_similar(self, name1: str, name2: str) -> bool:
        """Check if two names are similar (handles variations)."""
        if not name1 or not name2:
            return False
        
        # Simple similarity check
        name1_clean = re.sub(r'[^\w\s]', '', name1.lower()).strip()
        name2_clean = re.sub(r'[^\w\s]', '', name2.lower()).strip()
        
        return name1_clean == name2_clean
    
    def _clean_player_data(self, player_data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and standardize player data."""
        cleaned = player_data.copy()
        
        # Clean name
        if cleaned.get('name'):
            cleaned['name'] = re.sub(r'[^\w\s\-\.]', '', cleaned['name']).strip()
        
        # FIXED: NFL.com stores height as total inches - convert to feet'inches"
        if cleaned.get('height'):
            height = cleaned['height']
            if isinstance(height, str) and height.strip():
                height_clean = height.strip()
                # NFL.com format: just total inches (e.g., "76" = 6'4")
                if re.match(r'^\d+$', height_clean):
                    total_inches = int(height_clean)
                    feet = total_inches // 12
                    inches = total_inches % 12
                    cleaned['height'] = f"{feet}'{inches}\""
                # Already in feet'inches" format
                elif re.search(r"\d+'\d+\"", height_clean):
                    cleaned['height'] = height_clean
                # Format like "6-3" or "6 3"
                elif re.search(r'(\d+)[-\s](\d+)', height_clean):
                    height_match = re.search(r'(\d+)[-\s](\d+)', height_clean)
                    feet, inches = height_match.groups()
                    cleaned['height'] = f"{feet}'{inches}\""
                else:
                    # Unknown format, keep original
                    cleaned['height'] = height_clean
        
        # Ensure weight is integer
        if cleaned.get('weight') and isinstance(cleaned['weight'], str):
            cleaned['weight'] = self._extract_weight(cleaned['weight'])
        
        # Add extraction timestamp
        cleaned['scraped_at'] = datetime.now().isoformat()
        
        return cleaned
    
    def _extract_number(self, text: str) -> Optional[int]:
        """Extract number from text."""
        if not text:
            return None
        
        match = re.search(r'\d+', str(text))
        return int(match.group()) if match else None
    
    def _extract_weight(self, text: str) -> Optional[int]:
        """Extract weight from text."""
        if not text:
            return None
        
        # Remove common weight suffixes
        weight_text = re.sub(r'(lbs?|pounds?)', '', str(text), flags=re.IGNORECASE)
        match = re.search(r'\d+', weight_text)
        return int(match.group()) if match else None
    
    def _convert_height_from_inches(self, height_str: str) -> Optional[str]:
        """Convert height from total inches to feet'inches\" format."""
        if not height_str or not height_str.strip():
            return None
        
        height_clean = height_str.strip()
        
        # NFL.com format: just total inches (e.g., "76" = 6'4")
        if re.match(r'^\d+$', height_clean):
            total_inches = int(height_clean)
            feet = total_inches // 12
            inches = total_inches % 12
            return f"{feet}'{inches}\""
        
        # Already in correct format
        return height_clean


def main():
    """Main function to test the enhanced scraper."""
    scraper = EnhancedNFLScraper()
    
    # Test with 49ers
    test_team = "49ers"
    players = scraper.extract_complete_team_roster(test_team)
    
    print(f"\n📊 RESULTS FOR {test_team.upper()}")
    print("=" * 50)
    print(f"Total players found: {len(players)}")
    
    if players:
        print("\n🔍 Sample players:")
        for i, player in enumerate(players[:5]):
            print(f"{i+1}. {player.get('name', 'N/A')} - {player.get('position', 'N/A')} - #{player.get('jersey_number', 'N/A')}")
        
        # Save to file
        with open(f'{test_team}_roster.json', 'w') as f:
            json.dump(players, f, indent=2, default=str)
        
        print(f"\n💾 Data saved to {test_team}_roster.json")
    else:
        print("❌ No players found")


if __name__ == "__main__":
    main()