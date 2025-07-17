"""NFL sites data extraction (NFL.com, ESPN, Pro Football Reference)."""

import re
import logging
import requests
from typing import Dict, List, Optional, Any, Tuple
from bs4 import BeautifulSoup
import trafilatura

from ..core.exceptions import ExtractionError, ScrapingError
from ..core.utils import get_user_agent, polite_delay, check_robots_txt, clean_text


class NFLSitesExtractor:
    """Extractor for NFL official sites and major sports sites."""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("nfl_gravity.extractors.nfl_sites")
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': get_user_agent()})
        
        # Site-specific configurations
        self.sites = {
            'nfl.com': {
                'base_url': 'https://www.nfl.com',
                'roster_path': '/teams/{team}/roster',
                'player_path': '/players/{player_id}/'
            },
            'espn.com': {
                'base_url': 'https://www.espn.com',
                'roster_path': '/nfl/team/roster/_/name/{team}',
                'player_path': '/nfl/player/_/id/{player_id}'
            },
            'pro-football-reference.com': {
                'base_url': 'https://www.pro-football-reference.com',
                'roster_path': '/teams/{team}/2024_roster.htm',
                'player_path': '/players/{letter}/{player_id}.htm'
            }
        }
    
    def extract_team_roster(self, team: str, site: str = 'nfl.com') -> List[Dict[str, Any]]:
        """
        Extract team roster from specified site.
        
        Args:
            team: Team name (e.g., 'chiefs', 'patriots')
            site: Site to scrape from ('nfl.com', 'espn.com', 'pro-football-reference.com')
            
        Returns:
            List of player dictionaries
        """
        try:
            if site not in self.sites:
                raise ValueError(f"Unsupported site: {site}")
            
            roster_url = self._build_roster_url(team, site)
            
            # Check robots.txt
            if not check_robots_txt(roster_url):
                self.logger.warning(f"Robots.txt disallows scraping {roster_url}")
                return []
            
            # Extract roster data
            roster_data = self._scrape_roster_page(roster_url, site)
            
            self.logger.info(f"Extracted {len(roster_data)} players from {team} roster on {site}")
            return roster_data
            
        except Exception as e:
            self.logger.error(f"Error extracting roster for {team} from {site}: {e}")
            raise ExtractionError(f"Failed to extract roster: {e}")
    
    def extract_player_details(self, player_id: str, site: str = 'nfl.com') -> Dict[str, Any]:
        """
        Extract detailed player information from specified site.
        
        Args:
            player_id: Player identifier for the site
            site: Site to scrape from
            
        Returns:
            Player data dictionary
        """
        try:
            if site not in self.sites:
                raise ValueError(f"Unsupported site: {site}")
            
            player_url = self._build_player_url(player_id, site)
            
            # Check robots.txt
            if not check_robots_txt(player_url):
                self.logger.warning(f"Robots.txt disallows scraping {player_url}")
                return {}
            
            # Extract player data
            player_data = self._scrape_player_page(player_url, site)
            player_data['data_source'] = site
            
            self.logger.info(f"Extracted player details for {player_id} from {site}")
            return player_data
            
        except Exception as e:
            self.logger.error(f"Error extracting player {player_id} from {site}: {e}")
            return {}
    
    def _build_roster_url(self, team: str, site: str) -> str:
        """Build roster URL for specified team and site."""
        site_config = self.sites[site]
        team_mapping = self._get_team_mapping(site)
        
        site_team = team_mapping.get(team.lower(), team.lower())
        roster_path = site_config['roster_path'].format(team=site_team)
        
        return site_config['base_url'] + roster_path
    
    def _build_player_url(self, player_id: str, site: str) -> str:
        """Build player URL for specified player and site."""
        site_config = self.sites[site]
        
        if site == 'pro-football-reference.com':
            # PFR uses first letter of last name in URL
            letter = player_id[0].lower()
            player_path = site_config['player_path'].format(letter=letter, player_id=player_id)
        else:
            player_path = site_config['player_path'].format(player_id=player_id)
        
        return site_config['base_url'] + player_path
    
    def _get_team_mapping(self, site: str) -> Dict[str, str]:
        """Get team name mapping for specific site."""
        if site == 'nfl.com':
            return {
                '49ers': 'san-francisco-49ers', 'bears': 'chicago-bears', 'bengals': 'cincinnati-bengals', 'bills': 'buffalo-bills',
                'broncos': 'denver-broncos', 'browns': 'cleveland-browns', 'buccaneers': 'tampa-bay-buccaneers', 'cardinals': 'arizona-cardinals',
                'chargers': 'los-angeles-chargers', 'chiefs': 'kansas-city-chiefs', 'colts': 'indianapolis-colts', 'commanders': 'washington-commanders',
                'cowboys': 'dallas-cowboys', 'dolphins': 'miami-dolphins', 'eagles': 'philadelphia-eagles', 'falcons': 'atlanta-falcons',
                'giants': 'new-york-giants', 'jaguars': 'jacksonville-jaguars', 'jets': 'new-york-jets', 'lions': 'detroit-lions',
                'packers': 'green-bay-packers', 'panthers': 'carolina-panthers', 'patriots': 'new-england-patriots', 'raiders': 'las-vegas-raiders',
                'rams': 'los-angeles-rams', 'ravens': 'baltimore-ravens', 'saints': 'new-orleans-saints', 'seahawks': 'seattle-seahawks',
                'steelers': 'pittsburgh-steelers', 'texans': 'houston-texans', 'titans': 'tennessee-titans', 'vikings': 'minnesota-vikings'
            }
        elif site == 'espn.com':
            return {
                '49ers': 'sf', 'bears': 'chi', 'bengals': 'cin', 'bills': 'buf',
                'broncos': 'den', 'browns': 'cle', 'buccaneers': 'tb', 'cardinals': 'ari',
                'chargers': 'lac', 'chiefs': 'kc', 'colts': 'ind', 'commanders': 'wsh',
                'cowboys': 'dal', 'dolphins': 'mia', 'eagles': 'phi', 'falcons': 'atl',
                'giants': 'nyg', 'jaguars': 'jax', 'jets': 'nyj', 'lions': 'det',
                'packers': 'gb', 'panthers': 'car', 'patriots': 'ne', 'raiders': 'lv',
                'rams': 'lar', 'ravens': 'bal', 'saints': 'no', 'seahawks': 'sea',
                'steelers': 'pit', 'texans': 'hou', 'titans': 'ten', 'vikings': 'min'
            }
        else:  # pro-football-reference.com
            return {
                '49ers': 'sfo', 'bears': 'chi', 'bengals': 'cin', 'bills': 'buf',
                'broncos': 'den', 'browns': 'cle', 'buccaneers': 'tam', 'cardinals': 'crd',
                'chargers': 'sdg', 'chiefs': 'kan', 'colts': 'clt', 'commanders': 'was',
                'cowboys': 'dal', 'dolphins': 'mia', 'eagles': 'phi', 'falcons': 'atl',
                'giants': 'nyg', 'jaguars': 'jax', 'jets': 'nyj', 'lions': 'det',
                'packers': 'gnb', 'panthers': 'car', 'patriots': 'nwe', 'raiders': 'rai',
                'rams': 'ram', 'ravens': 'rav', 'saints': 'nor', 'seahawks': 'sea',
                'steelers': 'pit', 'texans': 'htx', 'titans': 'oti', 'vikings': 'min'
            }
    
    def _scrape_roster_page(self, url: str, site: str) -> List[Dict[str, Any]]:
        """Scrape roster data from the specified URL."""
        try:
            polite_delay(self.config.request_delay_min, self.config.request_delay_max)
            
            response = self.session.get(url, timeout=self.config.request_timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Site-specific parsing
            if site == 'nfl.com':
                return self._parse_nfl_roster(soup)
            elif site == 'espn.com':
                return self._parse_espn_roster(soup)
            elif site == 'pro-football-reference.com':
                return self._parse_pfr_roster(soup)
            else:
                return []
                
        except requests.RequestException as e:
            self.logger.error(f"HTTP error scraping {url}: {e}")
            raise ScrapingError(f"Failed to fetch roster page: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing roster from {url}: {e}")
            return []
    
    def _parse_nfl_roster(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse NFL.com roster page."""
        players = []
        
        # Look for roster table or player cards
        roster_table = soup.find('table') or soup.find('div', class_='roster')
        
        if roster_table:
            # Parse table rows
            for row in roster_table.find_all('tr')[1:]:  # Skip header
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    # NFL.com roster structure: Player, No, Pos, Status, Height, Weight, Experience, College
                    player_data = {
                        'name': clean_text(cells[0].get_text()),
                        'jersey_number': self._extract_number(cells[1].get_text()),
                        'position': clean_text(cells[2].get_text()),
                        'status': clean_text(cells[3].get_text()) if len(cells) > 3 else None,
                        'height': clean_text(cells[4].get_text()) if len(cells) > 4 else None,
                        'weight': self._extract_weight(cells[5].get_text()) if len(cells) > 5 else None,
                        'experience': clean_text(cells[6].get_text()) if len(cells) > 6 else None,
                        'college': clean_text(cells[7].get_text()) if len(cells) > 7 else None,
                        'data_source': 'nfl.com'
                    }
                    
                    if player_data['name'] and player_data['name'].strip():
                        players.append(player_data)
        
        return players
    
    def _parse_espn_roster(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse ESPN roster page."""
        players = []
        
        # ESPN typically uses different table structures
        roster_sections = soup.find_all('div', class_='ResponsiveTable')
        
        for section in roster_sections:
            table = section.find('table')
            if table:
                for row in table.find_all('tr')[1:]:  # Skip header
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        # Extract player name from link if available
                        name_cell = cells[0]
                        player_link = name_cell.find('a')
                        player_name = clean_text(player_link.get_text() if player_link else name_cell.get_text())
                        
                        player_data = {
                            'name': player_name,
                            'jersey_number': self._extract_number(cells[1].get_text()) if len(cells) > 1 else None,
                            'position': clean_text(cells[2].get_text()) if len(cells) > 2 else None,
                            'data_source': 'espn.com'
                        }
                        
                        # Extract additional data if available
                        if len(cells) > 3:
                            player_data['height'] = clean_text(cells[3].get_text())
                        if len(cells) > 4:
                            player_data['weight'] = self._extract_weight(cells[4].get_text())
                        if len(cells) > 5:
                            player_data['age'] = self._extract_number(cells[5].get_text())
                        
                        if player_data['name']:
                            players.append(player_data)
        
        return players
    
    def _parse_pfr_roster(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse Pro Football Reference roster page."""
        players = []
        
        # PFR uses specific table IDs
        roster_table = soup.find('table', id='games_played_team')
        if not roster_table:
            roster_table = soup.find('table', {'data-stat': 'player'})
        
        if roster_table:
            for row in roster_table.find_all('tr')[1:]:  # Skip header
                if 'thead' in str(row):  # Skip sub-headers
                    continue
                    
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    # PFR has detailed player links
                    name_cell = cells[0] if cells[0].get('data-stat') == 'player' else cells[1]
                    player_link = name_cell.find('a')
                    
                    if player_link:
                        player_data = {
                            'name': clean_text(player_link.get_text()),
                            'pfr_id': player_link.get('href', '').split('/')[-1].replace('.htm', ''),
                            'data_source': 'pro-football-reference.com'
                        }
                        
                        # Extract other stats based on data-stat attributes
                        for cell in cells:
                            stat = cell.get('data-stat')
                            if stat:
                                value = clean_text(cell.get_text())
                                if stat == 'pos':
                                    player_data['position'] = value
                                elif stat == 'jersey_number':
                                    player_data['jersey_number'] = self._extract_number(value)
                                elif stat == 'age':
                                    player_data['age'] = self._extract_number(value)
                                elif stat == 'height':
                                    player_data['height'] = value
                                elif stat == 'weight':
                                    player_data['weight'] = self._extract_weight(value)
                        
                        if player_data['name']:
                            players.append(player_data)
        
        return players
    
    def _scrape_player_page(self, url: str, site: str) -> Dict[str, Any]:
        """Scrape individual player page."""
        try:
            polite_delay(self.config.request_delay_min, self.config.request_delay_max)
            
            response = self.session.get(url, timeout=self.config.request_timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract text content for LLM processing
            text_content = trafilatura.extract(str(soup))
            
            player_data = {
                'player_url': url,
                'content_text': text_content[:5000] if text_content else '',  # Limit content length
            }
            
            # Site-specific parsing for structured data
            if site == 'nfl.com':
                structured_data = self._parse_nfl_player(soup)
            elif site == 'espn.com':
                structured_data = self._parse_espn_player(soup)
            elif site == 'pro-football-reference.com':
                structured_data = self._parse_pfr_player(soup)
            else:
                structured_data = {}
            
            player_data.update(structured_data)
            return player_data
            
        except requests.RequestException as e:
            self.logger.error(f"HTTP error scraping player {url}: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Error parsing player from {url}: {e}")
            return {}
    
    def _parse_nfl_player(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Parse NFL.com player page for structured data."""
        data = {}
        
        # Look for player stats and bio information
        bio_section = soup.find('div', class_='player-bio') or soup.find('section', class_='bio')
        
        if bio_section:
            # Extract basic info
            for item in bio_section.find_all(['dt', 'dd', 'span', 'div']):
                text = clean_text(item.get_text())
                if 'Height:' in text or 'height' in text.lower():
                    height_match = re.search(r"(\d+'\d+\")", text)
                    if height_match:
                        data['height'] = height_match.group(1)
                elif 'Weight:' in text or 'weight' in text.lower():
                    weight_match = re.search(r'(\d+)', text)
                    if weight_match:
                        data['weight'] = int(weight_match.group(1))
                elif 'College:' in text or 'college' in text.lower():
                    college_match = re.search(r'College:\s*(.+)', text)
                    if college_match:
                        data['college'] = college_match.group(1).strip()
        
        return data
    
    def _parse_espn_player(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Parse ESPN player page for structured data."""
        data = {}
        
        # ESPN player pages have different structure
        player_header = soup.find('div', class_='PlayerHeader')
        
        if player_header:
            # Extract player details
            details = player_header.find_all('li')
            for detail in details:
                text = clean_text(detail.get_text())
                if 'HT' in text or 'Height' in text:
                    height_match = re.search(r"(\d+'\d+\")", text)
                    if height_match:
                        data['height'] = height_match.group(1)
                elif 'WT' in text or 'Weight' in text:
                    weight_match = re.search(r'(\d+)', text)
                    if weight_match:
                        data['weight'] = int(weight_match.group(1))
        
        return data
    
    def _parse_pfr_player(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Parse Pro Football Reference player page for structured data."""
        data = {}
        
        # PFR has detailed player information in specific divs
        info_div = soup.find('div', id='info')
        
        if info_div:
            for p in info_div.find_all('p'):
                text = clean_text(p.get_text())
                if 'Born:' in text:
                    # Extract birth date and location
                    date_match = re.search(r'Born: .* (\d{4})', text)
                    if date_match:
                        data['birth_year'] = int(date_match.group(1))
                elif 'College:' in text:
                    college_match = re.search(r'College: (.+)', text)
                    if college_match:
                        data['college'] = college_match.group(1).strip()
                elif 'Draft:' in text:
                    # Extract draft information
                    draft_match = re.search(r'Draft: .* (\d{4}) NFL Draft, (\d+)\w* round \((\d+)\w* pick\)', text)
                    if draft_match:
                        data['draft_year'] = int(draft_match.group(1))
                        data['draft_round'] = int(draft_match.group(2))
                        data['draft_pick'] = int(draft_match.group(3))
        
        return data
    
    def _extract_number(self, text: str) -> Optional[int]:
        """Extract number from text."""
        if not text:
            return None
        
        match = re.search(r'\d+', text.strip())
        return int(match.group()) if match else None
    
    def _extract_weight(self, text: str) -> Optional[int]:
        """Extract weight from text."""
        if not text:
            return None
        
        # Look for weight in lbs
        match = re.search(r'(\d+)\s*lbs?', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        # Just extract first number if no 'lbs'
        match = re.search(r'\d+', text.strip())
        return int(match.group()) if match else None
