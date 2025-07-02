"""Wikipedia data extraction for NFL players."""

import re
import logging
import requests
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
import trafilatura

from ..core.exceptions import ExtractionError
from ..core.utils import get_user_agent, polite_delay, clean_text


class WikipediaExtractor:
    """Extractor for Wikipedia player and team data."""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("nfl_gravity.extractors.wikipedia")
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': get_user_agent()})
    
    def search_player(self, player_name: str, team: str = None) -> Optional[str]:
        """
        Search for a player's Wikipedia page.
        
        Args:
            player_name: Name of the player
            team: Optional team name for disambiguation
            
        Returns:
            Wikipedia URL if found, None otherwise
        """
        try:
            # Try Wikipedia search API
            search_url = "https://en.wikipedia.org/api/rest_v1/page/search"
            params = {
                'q': f"{player_name} NFL football",
                'limit': 5
            }
            
            if team:
                params['q'] += f" {team}"
            
            polite_delay(self.config.request_delay_min, self.config.request_delay_max)
            
            response = self.session.get(
                search_url,
                params=params,
                timeout=self.config.request_timeout
            )
            response.raise_for_status()
            
            search_results = response.json()
            
            # Look for the most relevant result
            for result in search_results.get('pages', []):
                title = result.get('title', '')
                description = result.get('description', '')
                
                # Check if this looks like a football player page
                if any(keyword in description.lower() for keyword in 
                       ['american football', 'quarterback', 'running back', 'wide receiver', 
                        'linebacker', 'defensive', 'nfl', 'football player']):
                    
                    wikipedia_url = f"https://en.wikipedia.org/wiki/{result['key']}"
                    self.logger.info(f"Found Wikipedia page: {wikipedia_url}")
                    return wikipedia_url
            
            self.logger.warning(f"No Wikipedia page found for {player_name}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error searching Wikipedia for {player_name}: {e}")
            return None
    
    def extract_player_data(self, wikipedia_url: str) -> Dict[str, Any]:
        """
        Extract player data from Wikipedia page.
        
        Args:
            wikipedia_url: URL of the Wikipedia page
            
        Returns:
            Dictionary containing extracted player data
        """
        try:
            polite_delay(self.config.request_delay_min, self.config.request_delay_max)
            
            response = self.session.get(wikipedia_url, timeout=self.config.request_timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            player_data = {
                'wikipedia_url': wikipedia_url,
                'data_source': 'wikipedia'
            }
            
            # Extract from infobox
            infobox_data = self._extract_infobox(soup)
            player_data.update(infobox_data)
            
            # Extract career highlights
            career_highlights = self._extract_career_highlights(soup)
            if career_highlights:
                player_data['career_highlights'] = career_highlights
            
            # Extract awards and honors
            awards = self._extract_awards(soup)
            if awards:
                player_data['awards'] = awards
            
            # Extract biographical information
            bio_data = self._extract_biography(soup)
            player_data.update(bio_data)
            
            # Extract statistics if available
            stats_data = self._extract_statistics(soup)
            player_data.update(stats_data)
            
            self.logger.info(f"Extracted data for player from {wikipedia_url}")
            return player_data
            
        except Exception as e:
            self.logger.error(f"Error extracting data from {wikipedia_url}: {e}")
            raise ExtractionError(f"Failed to extract Wikipedia data: {e}")
    
    def _extract_infobox(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract data from Wikipedia infobox."""
        data = {}
        
        # Find the infobox
        infobox = soup.find('table', class_='infobox')
        if not infobox:
            return data
        
        # Mapping of infobox labels to our field names
        field_mappings = {
            'Position': 'position',
            'Number': 'jersey_number',
            'Born': 'birth_info',
            'Height': 'height',
            'Weight': 'weight',
            'College': 'college',
            'NFL Draft': 'draft_info',
            'Career history': 'career_history',
            'Career highlights and awards': 'career_highlights_raw'
        }
        
        # Extract infobox rows
        for row in infobox.find_all('tr'):
            header = row.find('th')
            value = row.find('td')
            
            if header and value:
                header_text = clean_text(header.get_text())
                value_text = clean_text(value.get_text())
                
                # Map to our field names
                for label, field_name in field_mappings.items():
                    if label.lower() in header_text.lower():
                        data[field_name] = value_text
                        break
        
        # Parse specific fields
        data = self._parse_infobox_fields(data)
        
        return data
    
    def _parse_infobox_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse specific infobox fields into structured data."""
        parsed_data = {}
        
        # Parse birth information
        if 'birth_info' in data:
            birth_match = re.search(r'\((\d{4})-(\d{2})-(\d{2})\)', data['birth_info'])
            if birth_match:
                parsed_data['birth_date'] = f"{birth_match.group(1)}-{birth_match.group(2)}-{birth_match.group(3)}"
            
            # Extract age
            age_match = re.search(r'age (\d+)', data['birth_info'])
            if age_match:
                parsed_data['age'] = int(age_match.group(1))
        
        # Parse height
        if 'height' in data:
            height_match = re.search(r"(\d+)\s*ft\s*(\d+)\s*in", data['height'])
            if height_match:
                parsed_data['height'] = f"{height_match.group(1)}'{height_match.group(2)}\""
        
        # Parse weight
        if 'weight' in data:
            weight_match = re.search(r'(\d+)\s*lb', data['weight'])
            if weight_match:
                parsed_data['weight'] = int(weight_match.group(1))
        
        # Parse jersey number
        if 'jersey_number' in data:
            try:
                parsed_data['jersey_number'] = int(re.search(r'\d+', data['jersey_number']).group())
            except (AttributeError, ValueError):
                pass
        
        # Parse draft information
        if 'draft_info' in data:
            draft_match = re.search(r'(\d{4}).*?(\d+).*?(\d+)', data['draft_info'])
            if draft_match:
                parsed_data['draft_year'] = int(draft_match.group(1))
                parsed_data['draft_round'] = int(draft_match.group(2))
                parsed_data['draft_pick'] = int(draft_match.group(3))
        
        # Copy other fields as-is
        for key, value in data.items():
            if key not in ['birth_info', 'height', 'weight', 'jersey_number', 'draft_info']:
                parsed_data[key] = value
        
        return parsed_data
    
    def _extract_career_highlights(self, soup: BeautifulSoup) -> List[str]:
        """Extract career highlights from the page."""
        highlights = []
        
        # Look for career highlights sections
        for heading in soup.find_all(['h2', 'h3', 'h4']):
            if 'career' in heading.get_text().lower() and 'highlight' in heading.get_text().lower():
                # Find the following list or paragraph
                next_element = heading.find_next_sibling()
                while next_element:
                    if next_element.name == 'ul':
                        for li in next_element.find_all('li'):
                            highlight = clean_text(li.get_text())
                            if highlight:
                                highlights.append(highlight)
                        break
                    elif next_element.name in ['h2', 'h3', 'h4']:
                        break
                    next_element = next_element.find_next_sibling()
        
        return highlights
    
    def _extract_awards(self, soup: BeautifulSoup) -> List[str]:
        """Extract awards and honors from the page."""
        awards = []
        
        # Look for awards sections
        for heading in soup.find_all(['h2', 'h3', 'h4']):
            heading_text = heading.get_text().lower()
            if any(keyword in heading_text for keyword in ['award', 'honor', 'achievement', 'recognition']):
                # Find the following list
                next_element = heading.find_next_sibling()
                while next_element:
                    if next_element.name == 'ul':
                        for li in next_element.find_all('li'):
                            award = clean_text(li.get_text())
                            if award:
                                awards.append(award)
                        break
                    elif next_element.name in ['h2', 'h3', 'h4']:
                        break
                    next_element = next_element.find_next_sibling()
        
        return awards
    
    def _extract_biography(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract biographical information from the page content."""
        bio_data = {}
        
        # Extract the main content using trafilatura for better text extraction
        html_content = str(soup)
        text_content = trafilatura.extract(html_content)
        
        if text_content:
            # Look for college information
            college_match = re.search(r'attended (.*?) (?:University|College)', text_content, re.IGNORECASE)
            if college_match:
                bio_data['college'] = college_match.group(1).strip()
            
            # Look for hometown information
            hometown_match = re.search(r'born in (.*?),', text_content, re.IGNORECASE)
            if hometown_match:
                bio_data['hometown'] = hometown_match.group(1).strip()
        
        return bio_data
    
    def _extract_statistics(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract statistics from tables on the page."""
        stats_data = {}
        
        # Look for statistics tables
        for table in soup.find_all('table'):
            table_caption = table.find('caption')
            if table_caption and 'statistics' in table_caption.get_text().lower():
                # This is a basic implementation - could be expanded based on specific needs
                stats_data['has_statistics_table'] = True
                break
        
        return stats_data
