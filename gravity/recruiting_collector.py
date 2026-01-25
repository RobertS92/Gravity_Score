"""
Recruiting Collector - Collect high school recruiting data from multiple sources
"""

import requests
from bs4 import BeautifulSoup
import re
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class RecruitingCollector:
    """Collect high school recruiting data from 247Sports, Rivals, and ESPN"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def collect_recruiting_data(self, player_name: str, college: str, draft_year: Optional[int] = None) -> Dict:
        """
        Collect high school recruiting data for a player.
        
        Args:
            player_name: Full player name
            college: College the player attended
            draft_year: Year player was drafted (used to estimate recruiting year)
            
        Returns:
            Dictionary with recruiting data:
            {
                'stars': int,  # Star rating (3, 4, or 5)
                'national_rank': int,  # National ranking
                'position_rank': int,  # Position ranking
                'state_rank': int,  # State ranking
                'high_school': str,  # High school name
                'hometown': str,  # City, State
                'source': str  # Data source
            }
        """
        result = {
            'stars': None,
            'national_rank': None,
            'position_rank': None,
            'state_rank': None,
            'high_school': None,
            'hometown': None,
            'source': None
        }
        
        # Calculate recruiting year (typically draft_year - 4 or 5)
        recruiting_year = None
        if draft_year:
            # Most players are drafted 3-4 years after high school
            # Try both years
            recruiting_year = draft_year - 4
        
        logger.info(f"   🏈 Collecting recruiting data for {player_name} (est. class: {recruiting_year})")
        
        # Try 247Sports first (most comprehensive)
        data = self._get_247sports_data(player_name, recruiting_year, college)
        if data and data.get('stars'):
            result.update(data)
            result['source'] = '247Sports'
            logger.info(f"   ✅ Found {data.get('stars')}⭐ recruit on 247Sports")
            return result
        
        # Try Rivals as backup
        data = self._get_rivals_data(player_name, recruiting_year, college)
        if data and data.get('stars'):
            result.update(data)
            result['source'] = 'Rivals'
            logger.info(f"   ✅ Found {data.get('stars')}⭐ recruit on Rivals")
            return result
        
        # Try ESPN Recruiting as last resort
        data = self._get_espn_recruiting_data(player_name, recruiting_year, college)
        if data and data.get('stars'):
            result.update(data)
            result['source'] = 'ESPN'
            logger.info(f"   ✅ Found {data.get('stars')}⭐ recruit on ESPN")
            return result
        
        logger.info(f"   ℹ️  No recruiting data found for {player_name}")
        return result
    
    def _get_247sports_data(self, player_name: str, recruiting_year: Optional[int], college: str) -> Optional[Dict]:
        """Get recruiting data from 247Sports"""
        try:
            # 247Sports search URL
            # Example: https://247sports.com/Season/2017-Football/CompositeRecruitRankings/
            
            if not recruiting_year:
                # Try recent years if no year provided
                current_year = datetime.now().year
                years_to_try = range(current_year - 10, current_year)
            else:
                # Try the recruiting year and adjacent years
                years_to_try = [recruiting_year - 1, recruiting_year, recruiting_year + 1]
            
            for year in years_to_try:
                url = f"https://247sports.com/Season/{year}-Football/CompositeRecruitRankings/"
                
                try:
                    response = self.session.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # Search for player in the rankings
                        # Look for player name in the page
                        page_text = soup.get_text().lower()
                        if player_name.lower() in page_text:
                            # Parse player data
                            data = self._parse_247sports_player(soup, player_name, college)
                            if data:
                                return data
                    
                except Exception as e:
                    logger.debug(f"247Sports year {year} failed: {e}")
                    continue
            
            return None
            
        except Exception as e:
            logger.debug(f"247Sports collection failed: {e}")
            return None
    
    def _parse_247sports_player(self, soup: BeautifulSoup, player_name: str, college: str) -> Optional[Dict]:
        """Parse 247Sports page for player data"""
        try:
            # Look for player row in rankings table
            # This is a simplified parser - actual implementation would need
            # to handle the specific HTML structure of 247Sports
            
            text = soup.get_text()
            
            # Try to find star rating near player name
            name_pos = text.lower().find(player_name.lower())
            if name_pos == -1:
                return None
            
            # Extract surrounding text (500 chars before and after)
            context = text[max(0, name_pos - 500):min(len(text), name_pos + 500)]
            
            result = {}
            
            # Look for star rating (pattern: "5 stars", "★★★★★", etc.)
            stars_match = re.search(r'(\d)\s*star', context, re.IGNORECASE)
            if stars_match:
                result['stars'] = int(stars_match.group(1))
            
            # Look for rankings (pattern: "#23 Overall", "#5 QB", etc.)
            overall_rank_match = re.search(r'#(\d+)\s*(overall|national)', context, re.IGNORECASE)
            if overall_rank_match:
                result['national_rank'] = int(overall_rank_match.group(1))
            
            pos_rank_match = re.search(r'#(\d+)\s*(QB|RB|WR|TE|OL|DL|LB|DB|K|P)', context, re.IGNORECASE)
            if pos_rank_match:
                result['position_rank'] = int(pos_rank_match.group(1))
            
            return result if result else None
            
        except Exception as e:
            logger.debug(f"Failed to parse 247Sports player: {e}")
            return None
    
    def _get_rivals_data(self, player_name: str, recruiting_year: Optional[int], college: str) -> Optional[Dict]:
        """Get recruiting data from Rivals"""
        try:
            # Rivals.com search
            # Similar approach to 247Sports but with Rivals URL structure
            
            logger.debug(f"Checking Rivals for {player_name}...")
            
            # Rivals search URL
            search_url = f"https://n.rivals.com/search?term={player_name.replace(' ', '+')}"
            
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Parse Rivals search results
                # This is a placeholder - actual implementation would parse Rivals HTML
                text = soup.get_text().lower()
                
                if player_name.lower() in text and (college.lower() in text if college else True):
                    # Found player, extract data
                    data = self._parse_rivals_player(soup, player_name)
                    if data:
                        return data
            
            return None
            
        except Exception as e:
            logger.debug(f"Rivals collection failed: {e}")
            return None
    
    def _parse_rivals_player(self, soup: BeautifulSoup, player_name: str) -> Optional[Dict]:
        """Parse Rivals page for player data"""
        try:
            text = soup.get_text()
            result = {}
            
            # Similar parsing logic to 247Sports
            stars_match = re.search(r'(\d)\s*star', text, re.IGNORECASE)
            if stars_match:
                result['stars'] = int(stars_match.group(1))
            
            rank_match = re.search(r'#(\d+)', text)
            if rank_match:
                result['national_rank'] = int(rank_match.group(1))
            
            return result if result else None
            
        except Exception as e:
            logger.debug(f"Failed to parse Rivals player: {e}")
            return None
    
    def _get_espn_recruiting_data(self, player_name: str, recruiting_year: Optional[int], college: str) -> Optional[Dict]:
        """Get recruiting data from ESPN Recruiting Database"""
        try:
            # ESPN Recruiting database
            logger.debug(f"Checking ESPN Recruiting for {player_name}...")
            
            # ESPN recruiting search
            # This is a placeholder - actual implementation would use ESPN's recruiting API/pages
            
            if not recruiting_year:
                return None
            
            # ESPN recruiting class URL pattern
            url = f"https://www.espn.com/college-sports/football/recruiting/playerrankings/_/view/rn300/class/{recruiting_year}"
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                text = soup.get_text().lower()
                
                if player_name.lower() in text:
                    data = self._parse_espn_recruiting(soup, player_name)
                    if data:
                        return data
            
            return None
            
        except Exception as e:
            logger.debug(f"ESPN Recruiting collection failed: {e}")
            return None
    
    def _parse_espn_recruiting(self, soup: BeautifulSoup, player_name: str) -> Optional[Dict]:
        """Parse ESPN recruiting page for player data"""
        try:
            text = soup.get_text()
            result = {}
            
            # ESPN uses different HTML structure
            # Look for star rating and rankings near player name
            stars_match = re.search(r'(\d)\s*star', text, re.IGNORECASE)
            if stars_match:
                result['stars'] = int(stars_match.group(1))
            
            rank_match = re.search(r'#(\d+)', text)
            if rank_match:
                result['national_rank'] = int(rank_match.group(1))
            
            return result if result else None
            
        except Exception as e:
            logger.debug(f"Failed to parse ESPN Recruiting: {e}")
            return None
