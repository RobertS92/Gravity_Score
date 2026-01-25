"""
247Sports NIL Connector
Recruiting and NIL coverage platform
"""

from typing import Dict, Any, Optional, List
import re
import logging
import asyncio
from gravity.nil.connectors.base import BaseNILConnector

logger = logging.getLogger(__name__)


class Sports247Connector(BaseNILConnector):
    """
    Connector for 247Sports - Recruiting and NIL platform
    247Sports provides:
    - Recruiting rankings
    - NIL deal coverage
    - Transfer portal news
    - Valuation estimates
    """
    
    BASE_URL = "https://247sports.com"
    SEARCH_URL = "https://247sports.com/Search"
    
    def get_source_name(self) -> str:
        return "247sports"
    
    def get_source_reliability_weight(self) -> float:
        return 0.75  # Tier 3: Journalistic coverage
    
    async def fetch_raw_async(
        self,
        athlete_name: str,
        school: Optional[str] = None,
        sport: Optional[str] = None,
        **filters
    ) -> Optional[Dict[str, Any]]:
        """Async fetch raw data from 247Sports"""
        try:
            search_query = athlete_name.replace(' ', '+')
            url = f"{self.SEARCH_URL}?searchterm={search_query}"
            
            logger.debug(f"Fetching 247Sports data (async): {url}")
            
            client = await self.get_async_client()
            response = await client.get(url, timeout=15.0)
            
            if not response or response.status_code != 200:
                return None
            
            soup = self.parse_html(response.text)
            profile_url = self._find_profile_link(soup, athlete_name, school)
            
            profile_data = None
            if profile_url:
                try:
                    profile_response = await client.get(profile_url, timeout=15.0)
                    if profile_response and profile_response.status_code == 200:
                        profile_soup = self.parse_html(profile_response.text)
                        profile_data = profile_soup.get_text()
                        
                        # Try NIL news tab
                        nil_url = profile_url.rstrip('/') + '/nil'
                        nil_response = await client.get(nil_url, timeout=15.0)
                        if nil_response and nil_response.status_code == 200:
                            profile_data += "\n\n" + self.parse_html(nil_response.text).get_text()
                except Exception as e:
                    logger.debug(f"Failed to fetch 247Sports profile: {e}")
            
            return {
                'search_results': soup.get_text(),
                'profile_url': profile_url,
                'profile_data': profile_data,
                'raw_html': response.text,
                'athlete_name': athlete_name
            }
            
        except Exception as e:
            logger.error(f"247Sports fetch failed for {athlete_name}: {e}")
            return None
    
    def fetch_raw(
        self,
        athlete_name: str,
        school: Optional[str] = None,
        sport: Optional[str] = None,
        **filters
    ) -> Optional[Dict[str, Any]]:
        """Sync wrapper around async fetch_raw"""
        return asyncio.run(self.fetch_raw_async(athlete_name, school, sport, **filters))
    
    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize 247Sports data
        
        Args:
            raw_data: Raw response
        
        Returns:
            Normalized data
        """
        normalized = {
            'recruiting_ranking': None,
            'recruiting_stars': None,
            'nil_valuation': None,
            'nil_deals': [],
            'transfer_portal_status': None,
            'profile_url': raw_data.get('profile_url')
        }
        
        # Combine text sources
        text = (raw_data.get('search_results', '') + ' ' + 
                (raw_data.get('profile_data', '') or ''))
        
        # Extract recruiting info
        ranking = self._extract_recruiting_ranking(text)
        if ranking:
            normalized['recruiting_ranking'] = ranking
        
        stars = self._extract_star_rating(text)
        if stars:
            normalized['recruiting_stars'] = stars
        
        # Extract NIL valuation
        valuation = self._extract_nil_valuation(text)
        if valuation:
            normalized['nil_valuation'] = valuation
        
        # Extract deals
        deals = self._extract_nil_deals(text)
        if deals:
            normalized['nil_deals'] = deals
        
        # Check transfer portal
        if 'transfer portal' in text.lower():
            normalized['transfer_portal_status'] = 'active'
        
        return normalized
    
    def _find_profile_link(self, soup, athlete_name: str, school: Optional[str] = None) -> Optional[str]:
        """Find player profile link"""
        try:
            name_parts = athlete_name.lower().split()
            
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                link_text = link.get_text().lower()
                
                # Check name match
                if all(part in link_text for part in name_parts):
                    # Check if it's a player profile link
                    if '/player/' in href or '/recruit/' in href:
                        if href.startswith('http'):
                            return href
                        else:
                            return f"{self.BASE_URL}{href}"
            
            return None
        except Exception as e:
            logger.debug(f"Failed to find 247Sports profile: {e}")
            return None
    
    def _fetch_nil_news(self, profile_url: str) -> Optional[str]:
        """Fetch NIL-specific news from profile"""
        try:
            # Try to access NIL news tab
            nil_url = profile_url.rstrip('/') + '/nil'
            response = self.fetch_url(nil_url)
            
            if response:
                soup = self.parse_html(response.text)
                return soup.get_text()
            
            return None
        except Exception as e:
            logger.debug(f"Failed to fetch NIL news: {e}")
            return None
    
    def _extract_recruiting_ranking(self, text: str) -> Optional[int]:
        """Extract national recruiting ranking"""
        patterns = [
            r'#(\d+)\s+national\s+recruit',
            r'ranked\s+#?(\d+)\s+nationally',
            r'national\s+ranking.*?#?(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        return None
    
    def _extract_star_rating(self, text: str) -> Optional[int]:
        """Extract star rating (3-5 stars)"""
        patterns = [
            r'(\d)\s*-?\s*star\s+(?:recruit|prospect)',
            r'(\d)\s*★'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                stars = int(match.group(1))
                if 3 <= stars <= 5:
                    return stars
        
        return None
    
    def _extract_nil_valuation(self, text: str) -> Optional[float]:
        """Extract NIL valuation from text with enhanced patterns"""
        patterns = [
            # Exact
            r'nil\s+(?:value|valuation)[:\s]+\$\s*([\d,.]+)\s*([KMB])?',
            
            # Reversed
            r'\$\s*([\d,.]+)\s*([KMB])?\s+nil',
            
            # With "worth"
            r'worth.*?\$\s*([\d,.]+)\s*([KMB])?.*?nil',
            
            # Parentheses
            r'\(nil[:\s]+\$\s*([\d,.]+)\s*([KMB])?\)',
            
            # Estimated
            r'estimated\s+(?:at\s+)?\$\s*([\d,.]+)\s*([KMB])?',
            
            # Range
            r'\$\s*([\d,.]+)\s*([KMB])?\s*(?:-|to)\s*\$\s*([\d,.]+)\s*([KMB])?'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Handle range
                if len(match.groups()) == 4 and match.group(3):
                    low = self.parse_currency_value(f"${match.group(1)}{match.group(2) or ''}")
                    high = self.parse_currency_value(f"${match.group(3)}{match.group(4) or ''}")
                    if low and high:
                        return (low + high) / 2
                    return low or high
                
                # Single value
                value_str = f"${match.group(1)}{match.group(2) or ''}"
                return self.parse_currency_value(value_str)
        
        return None
    
    def _extract_nil_deals(self, text: str) -> List[Dict[str, Any]]:
        """Extract NIL deal mentions from news/profile"""
        deals = []
        
        # Look for deal announcements
        patterns = [
            r'signs?\s+(?:nil\s+)?deal\s+with\s+([\w\s&]+?)(?:\.|,|\n)',
            r'([\w\s&]+?)\s+(?:partnership|endorsement)',
            r'announced?\s+(?:partnership|deal)\s+with\s+([\w\s&]+?)(?:\.|,|\n)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                brand_name = match.group(1).strip()
                if 3 < len(brand_name) < 50:
                    deals.append({
                        'brand': brand_name,
                        'type': 'Reported Deal',
                        'source': '247sports'
                    })
        
        return deals[:10]
