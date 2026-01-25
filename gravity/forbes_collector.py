"""
Forbes Collector - Scrape endorsement values from Forbes highest-paid athletes lists
"""

import requests
from bs4 import BeautifulSoup
import re
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ForbesCollector:
    """Collect endorsement data from Forbes highest-paid athletes lists"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_endorsement_value(self, player_name: str, sport: str = "NFL") -> Optional[Dict]:
        """
        Scrape Forbes for off-field earnings (endorsements).
        
        Args:
            player_name: Full player name
            sport: Sport context (e.g., "NFL", "NBA")
            
        Returns:
            Dictionary with endorsement data or None if not found:
            {
                'estimated_value': int,  # Annual endorsement value in dollars
                'source': 'Forbes',
                'year': int,
                'total_earnings': int,  # Total earnings including salary
                'on_field_earnings': int,  # Salary/contract earnings
                'list_rank': int  # Ranking on Forbes list
            }
        """
        try:
            current_year = datetime.now().year
            
            # Try current and previous year lists
            for year in [current_year, current_year - 1]:
                logger.info(f"   💰 Searching Forbes {year} highest-paid athletes for {player_name}...")
                
                # Method 1: Try direct athlete page
                result = self._try_athlete_page(player_name, year)
                if result:
                    return result
                
                # Method 2: Search Forbes site
                result = self._search_forbes(player_name, year)
                if result:
                    return result
            
            logger.info(f"   ℹ️  {player_name} not found on Forbes lists")
            return None
            
        except Exception as e:
            logger.debug(f"Forbes collection failed for {player_name}: {e}")
            return None
    
    def _try_athlete_page(self, player_name: str, year: int) -> Optional[Dict]:
        """Try to access direct Forbes athlete profile page"""
        try:
            # Forbes URL format: /profile/athlete-name/
            name_slug = player_name.lower().replace(' ', '-')
            url = f"https://www.forbes.com/profile/{name_slug}/"
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract earnings data from profile
                data = self._parse_athlete_profile(soup, player_name, year)
                if data:
                    logger.info(f"   ✅ Forbes profile found for {player_name}")
                    return data
            
            return None
            
        except Exception as e:
            logger.debug(f"Forbes athlete page access failed: {e}")
            return None
    
    def _search_forbes(self, player_name: str, year: int) -> Optional[Dict]:
        """Search Forbes for the player"""
        try:
            # Search Forbes for the player
            search_query = f"{player_name} highest paid athletes {year}"
            search_url = f"https://www.forbes.com/search/?q={search_query.replace(' ', '%20')}"
            
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for athlete earnings articles
                articles = soup.find_all('a', href=True)
                
                for article in articles:
                    href = article['href']
                    text = article.get_text().lower()
                    
                    # Check if it's about this player
                    if player_name.lower() in text and ('earnings' in text or 'paid' in text):
                        # Try to extract from article
                        article_url = href if href.startswith('http') else f"https://www.forbes.com{href}"
                        data = self._parse_athlete_article(article_url, player_name, year)
                        if data:
                            return data
            
            return None
            
        except Exception as e:
            logger.debug(f"Forbes search failed: {e}")
            return None
    
    def _parse_athlete_profile(self, soup: BeautifulSoup, player_name: str, year: int) -> Optional[Dict]:
        """Parse athlete profile page for earnings data"""
        try:
            result = {
                'estimated_value': 0,
                'source': 'Forbes',
                'year': year,
                'total_earnings': 0,
                'on_field_earnings': 0,
                'list_rank': None
            }
            
            # Look for earnings data in the page text
            text = soup.get_text()
            
            # Pattern: "Total Earnings: $XX million" or similar
            total_match = re.search(r'total[\s\w]*earnings[:\s]*\$?([\d.]+)\s*(million|m)', text, re.IGNORECASE)
            if total_match:
                value = float(total_match.group(1))
                if 'million' in total_match.group(2).lower() or 'm' == total_match.group(2).lower():
                    value *= 1_000_000
                result['total_earnings'] = int(value)
            
            # Pattern: "On-field: $XX million" or "Salary: $XX million"
            on_field_match = re.search(r'(on[- ]field|salary|contract)[:\s]*\$?([\d.]+)\s*(million|m)', text, re.IGNORECASE)
            if on_field_match:
                value = float(on_field_match.group(2))
                if 'million' in on_field_match.group(3).lower() or 'm' == on_field_match.group(3).lower():
                    value *= 1_000_000
                result['on_field_earnings'] = int(value)
            
            # Pattern: "Off-field: $XX million" or "Endorsements: $XX million"
            off_field_match = re.search(r'(off[- ]field|endorsement)[:\s]*\$?([\d.]+)\s*(million|m)', text, re.IGNORECASE)
            if off_field_match:
                value = float(off_field_match.group(2))
                if 'million' in off_field_match.group(3).lower() or 'm' == off_field_match.group(3).lower():
                    value *= 1_000_000
                result['estimated_value'] = int(value)
            else:
                # Calculate from total - on_field if not directly stated
                if result['total_earnings'] > 0 and result['on_field_earnings'] > 0:
                    result['estimated_value'] = result['total_earnings'] - result['on_field_earnings']
            
            # Look for ranking
            rank_match = re.search(r'#(\d+)', text)
            if rank_match:
                result['list_rank'] = int(rank_match.group(1))
            
            # Only return if we found meaningful data
            if result['estimated_value'] > 0 or result['total_earnings'] > 0:
                return result
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to parse Forbes profile: {e}")
            return None
    
    def _parse_athlete_article(self, url: str, player_name: str, year: int) -> Optional[Dict]:
        """Parse Forbes article about athlete earnings"""
        try:
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                return self._parse_athlete_profile(soup, player_name, year)
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to parse Forbes article: {e}")
            return None

