"""
Enhanced Age Collection with Wikipedia Fallback
Tries NFL.com first, then Wikipedia if that fails
"""

import logging
import re
from datetime import datetime
from typing import Optional
import requests
from bs4 import BeautifulSoup
import trafilatura

logger = logging.getLogger(__name__)

class EnhancedAgeCollector:
    """Collects player age with multiple fallback sources"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def get_player_age(self, player_name: str, team: str) -> Optional[int]:
        """Get player age trying multiple sources"""
        
        # Try NFL.com first
        age = self._get_age_from_nfl_com(player_name, team)
        if age:
            logger.info(f"Found age {age} for {player_name} from NFL.com")
            return age
        
        # Try ESPN as secondary
        age = self._get_age_from_espn(player_name, team)
        if age:
            logger.info(f"Found age {age} for {player_name} from ESPN")
            return age
        
        # Wikipedia fallback
        age = self._get_age_from_wikipedia(player_name)
        if age:
            logger.info(f"Found age {age} for {player_name} from Wikipedia (fallback)")
            return age
        
        logger.warning(f"Could not find age for {player_name} from any source")
        return None
    
    def _get_age_from_nfl_com(self, player_name: str, team: str) -> Optional[int]:
        """Try to get age from NFL.com roster"""
        try:
            # Convert team name to NFL.com format
            team_slug = self._team_to_nfl_slug(team)
            
            urls = [
                f"https://www.nfl.com/teams/{team_slug}/roster",
                f"https://www.nfl.com/players/{player_name.lower().replace(' ', '-')}"
            ]
            
            for url in urls:
                try:
                    response = self.session.get(url, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Look for age in various formats
                        age_patterns = [
                            r'Age:\s*(\d+)',
                            r'AGE:\s*(\d+)',
                            r'(\d+)\s*years\s*old',
                            r'Age\s*(\d+)'
                        ]
                        
                        text = soup.get_text()
                        for pattern in age_patterns:
                            match = re.search(pattern, text, re.IGNORECASE)
                            if match:
                                age = int(match.group(1))
                                if 18 <= age <= 50:  # Reasonable age range
                                    return age
                        
                        # Look for birth date and calculate age
                        birth_date = self._extract_birth_date_from_text(text)
                        if birth_date:
                            age = self._calculate_age_from_date(birth_date)
                            if age:
                                return age
                                
                except Exception as e:
                    logger.debug(f"Error getting age from {url}: {e}")
                    continue
            
        except Exception as e:
            logger.debug(f"Error getting age from NFL.com for {player_name}: {e}")
        
        return None
    
    def _get_age_from_espn(self, player_name: str, team: str) -> Optional[int]:
        """Try to get age from ESPN"""
        try:
            # Search ESPN for the player
            search_url = f"https://www.espn.com/nfl/players/_/search/{player_name.replace(' ', '%20')}"
            
            response = self.session.get(search_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for age information
                age_patterns = [
                    r'Age:\s*(\d+)',
                    r'(\d+)\s*years\s*old',
                    r'Age\s*(\d+)'
                ]
                
                text = soup.get_text()
                for pattern in age_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        age = int(match.group(1))
                        if 18 <= age <= 50:
                            return age
                
        except Exception as e:
            logger.debug(f"Error getting age from ESPN for {player_name}: {e}")
        
        return None
    
    def _get_age_from_wikipedia(self, player_name: str) -> Optional[int]:
        """Fallback: Get age from Wikipedia"""
        try:
            # Try multiple Wikipedia URL formats
            wiki_urls = [
                f"https://en.wikipedia.org/wiki/{player_name.replace(' ', '_')}",
                f"https://en.wikipedia.org/wiki/{player_name.replace(' ', '_')}_(American_football)",
                f"https://en.wikipedia.org/wiki/{player_name.replace(' ', '_')}_(football_player)",
                f"https://en.wikipedia.org/wiki/{player_name.replace(' ', '_')}_(NFL)"
            ]
            
            for url in wiki_urls:
                try:
                    # Use trafilatura for better content extraction
                    downloaded = trafilatura.fetch_url(url)
                    if downloaded:
                        text = trafilatura.extract(downloaded)
                        if text:
                            # Look for birth date patterns
                            birth_date = self._extract_birth_date_from_text(text)
                            if birth_date:
                                age = self._calculate_age_from_date(birth_date)
                                if age:
                                    return age
                            
                            # Direct age patterns
                            age_patterns = [
                                r'age\s*(\d+)',
                                r'(\d+)\s*years\s*old',
                                r'born.*?(\d{4})',  # Extract birth year
                            ]
                            
                            for pattern in age_patterns:
                                match = re.search(pattern, text, re.IGNORECASE)
                                if match:
                                    if 'born' in pattern:
                                        # Calculate age from birth year
                                        birth_year = int(match.group(1))
                                        current_year = datetime.now().year
                                        age = current_year - birth_year
                                        if 18 <= age <= 50:
                                            return age
                                    else:
                                        age = int(match.group(1))
                                        if 18 <= age <= 50:
                                            return age
                    
                except Exception as e:
                    logger.debug(f"Error getting age from {url}: {e}")
                    continue
            
        except Exception as e:
            logger.debug(f"Error getting age from Wikipedia for {player_name}: {e}")
        
        return None
    
    def _extract_birth_date_from_text(self, text: str) -> Optional[str]:
        """Extract birth date from text"""
        # Common birth date patterns
        patterns = [
            r'born\s*:?\s*([A-Za-z]+ \d{1,2},? \d{4})',
            r'birth\s*date\s*:?\s*([A-Za-z]+ \d{1,2},? \d{4})',
            r'(\d{1,2}/\d{1,2}/\d{4})',
            r'(\d{4}-\d{2}-\d{2})',
            r'([A-Za-z]+ \d{1,2},? \d{4})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _calculate_age_from_date(self, birth_date_str: str) -> Optional[int]:
        """Calculate age from birth date string"""
        if not birth_date_str:
            return None
        
        try:
            # Try different date formats
            formats = [
                '%B %d, %Y',  # January 1, 1990
                '%B %d %Y',   # January 1 1990
                '%m/%d/%Y',   # 01/01/1990
                '%d/%m/%Y',   # 01/01/1990
                '%Y-%m-%d',   # 1990-01-01
            ]
            
            for fmt in formats:
                try:
                    birth_dt = datetime.strptime(birth_date_str, fmt)
                    today = datetime.now()
                    age = today.year - birth_dt.year - ((today.month, today.day) < (birth_dt.month, birth_dt.day))
                    if 18 <= age <= 50:
                        return age
                except ValueError:
                    continue
            
            # Try extracting just the year
            year_match = re.search(r'(\d{4})', birth_date_str)
            if year_match:
                birth_year = int(year_match.group(1))
                current_year = datetime.now().year
                age = current_year - birth_year
                if 18 <= age <= 50:
                    return age
                    
        except Exception as e:
            logger.debug(f"Error calculating age from '{birth_date_str}': {e}")
        
        return None
    
    def _team_to_nfl_slug(self, team: str) -> str:
        """Convert team name to NFL.com URL slug"""
        team_slugs = {
            '49ers': 'san-francisco-49ers',
            'bears': 'chicago-bears',
            'bengals': 'cincinnati-bengals',
            'bills': 'buffalo-bills',
            'broncos': 'denver-broncos',
            'browns': 'cleveland-browns',
            'buccaneers': 'tampa-bay-buccaneers',
            'cardinals': 'arizona-cardinals',
            'chargers': 'los-angeles-chargers',
            'chiefs': 'kansas-city-chiefs',
            'colts': 'indianapolis-colts',
            'commanders': 'washington-commanders',
            'cowboys': 'dallas-cowboys',
            'dolphins': 'miami-dolphins',
            'eagles': 'philadelphia-eagles',
            'falcons': 'atlanta-falcons',
            'giants': 'new-york-giants',
            'jaguars': 'jacksonville-jaguars',
            'jets': 'new-york-jets',
            'lions': 'detroit-lions',
            'packers': 'green-bay-packers',
            'panthers': 'carolina-panthers',
            'patriots': 'new-england-patriots',
            'raiders': 'las-vegas-raiders',
            'rams': 'los-angeles-rams',
            'ravens': 'baltimore-ravens',
            'saints': 'new-orleans-saints',
            'seahawks': 'seattle-seahawks',
            'steelers': 'pittsburgh-steelers',
            'texans': 'houston-texans',
            'titans': 'tennessee-titans',
            'vikings': 'minnesota-vikings'
        }
        
        return team_slugs.get(team.lower(), team.lower())