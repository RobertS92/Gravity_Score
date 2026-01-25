"""
Rivals NIL Connector
Recruiting and NIL coverage platform
"""

from typing import Dict, Any, Optional, List
import re
import logging
import asyncio
from gravity.nil.connectors.base import BaseNILConnector

logger = logging.getLogger(__name__)


class RivalsConnector(BaseNILConnector):
    """
    Connector for Rivals - Recruiting and NIL platform
    Rivals provides:
    - Recruiting rankings
    - NIL rankings and estimates
    - Deal announcements
    - Transfer portal coverage
    """
    
    BASE_URL = "https://n.rivals.com"
    SEARCH_URL = "https://n.rivals.com/search"
    
    def get_source_name(self) -> str:
        return "rivals"
    
    def get_source_reliability_weight(self) -> float:
        return 0.75  # Tier 3: Journalistic coverage
    
    async def fetch_raw_async(
        self,
        athlete_name: str,
        school: Optional[str] = None,
        sport: Optional[str] = None,
        **filters
    ) -> Optional[Dict[str, Any]]:
        """Async fetch raw data from Rivals"""
        try:
            search_query = athlete_name.replace(' ', '+')
            url = f"{self.SEARCH_URL}?q={search_query}"
            
            logger.debug(f"Fetching Rivals data (async): {url}")
            
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
                except Exception as e:
                    logger.debug(f"Failed to fetch Rivals profile: {e}")
            
            return {
                'search_results': soup.get_text(),
                'profile_url': profile_url,
                'profile_data': profile_data,
                'raw_html': response.text,
                'athlete_name': athlete_name
            }
            
        except Exception as e:
            logger.error(f"Rivals fetch failed for {athlete_name}: {e}")
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
        Normalize Rivals data
        
        Args:
            raw_data: Raw response
        
        Returns:
            Normalized data
        """
        normalized = {
            'recruiting_ranking': None,
            'recruiting_stars': None,
            'nil_ranking': None,
            'nil_valuation': None,
            'nil_deals': [],
            'profile_url': raw_data.get('profile_url')
        }
        
        # Combine text sources
        text = (raw_data.get('search_results', '') + ' ' + 
                (raw_data.get('profile_data', '') or '') + ' ' +
                (raw_data.get('nil_data', '') or ''))
        
        # Extract recruiting info
        ranking = self._extract_recruiting_ranking(text)
        if ranking:
            normalized['recruiting_ranking'] = ranking
        
        stars = self._extract_star_rating(text)
        if stars:
            normalized['recruiting_stars'] = stars
        
        # Extract NIL info
        nil_ranking = self._extract_nil_ranking(text)
        if nil_ranking:
            normalized['nil_ranking'] = nil_ranking
        
        valuation = self._extract_nil_valuation(text)
        if valuation:
            normalized['nil_valuation'] = valuation
        
        # Extract deals
        deals = self._extract_nil_deals(text)
        if deals:
            normalized['nil_deals'] = deals
        
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
                    # Check if it's a player profile
                    if '/prospect/' in href or '/player/' in href or '/recruit/' in href:
                        if href.startswith('http'):
                            return href
                        elif href.startswith('/'):
                            return f"{self.BASE_URL}{href}"
            
            return None
        except Exception as e:
            logger.debug(f"Failed to find Rivals profile: {e}")
            return None
    
    def _fetch_nil_rankings(self, athlete_name: str, school: Optional[str]) -> Optional[str]:
        """Fetch NIL-specific rankings page"""
        try:
            # Rivals has NIL rankings pages
            nil_url = f"{self.BASE_URL}/nil-rankings"
            response = self.fetch_url(nil_url)
            
            if response:
                soup = self.parse_html(response.text)
                text = soup.get_text()
                
                # Check if athlete is mentioned
                if athlete_name.lower() in text.lower():
                    return text
            
            return None
        except Exception as e:
            logger.debug(f"Failed to fetch NIL rankings: {e}")
            return None
    
    def _extract_recruiting_ranking(self, text: str) -> Optional[int]:
        """Extract national recruiting ranking"""
        patterns = [
            r'#(\d+)\s+(?:overall|national)',
            r'ranked\s+#?(\d+)',
            r'national\s+ranking.*?#?(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                ranking = int(match.group(1))
                if ranking < 10000:  # Sanity check
                    return ranking
        
        return None
    
    def _extract_star_rating(self, text: str) -> Optional[int]:
        """Extract star rating"""
        patterns = [
            r'(\d)\s*-?\s*star',
            r'(\d)\s*★'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                stars = int(match.group(1))
                if 3 <= stars <= 5:
                    return stars
        
        return None
    
    def _extract_nil_ranking(self, text: str) -> Optional[int]:
        """Extract NIL ranking"""
        patterns = [
            r'nil\s+(?:rank|ranking).*?#?(\d+)',
            r'#(\d+)\s+nil'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        return None
    
    def _extract_nil_valuation(self, text: str) -> Optional[float]:
        """Extract NIL valuation with enhanced patterns"""
        patterns = [
            # Exact
            r'nil\s+(?:value|valuation)[:\s]+\$\s*([\d,.]+)\s*([KMB])?',
            
            # Reversed
            r'\$\s*([\d,.]+)\s*([KMB])?\s+(?:in\s+)?nil',
            
            # Estimated
            r'estimated\s+(?:at\s+)?\$\s*([\d,.]+)\s*([KMB])?',
            
            # Parentheses
            r'\(nil[:\s]+\$\s*([\d,.]+)\s*([KMB])?\)',
            
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
        """Extract NIL deal mentions"""
        deals = []
        
        patterns = [
            r'(?:signs?|announces?)\s+(?:deal|partnership)\s+with\s+([\w\s&]+?)(?:\.|,|\n)',
            r'([\w\s&]+?)\s+(?:partnership|endorsement)',
            r'nil\s+deal.*?([\w\s&]{3,30})'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                brand_name = match.group(1).strip()
                if 3 < len(brand_name) < 50:
                    # Filter out common false positives
                    if brand_name.lower() not in ['the', 'and', 'with', 'for', 'from']:
                        deals.append({
                            'brand': brand_name,
                            'type': 'Reported Deal',
                            'source': 'rivals'
                        })
        
        # Deduplicate
        seen = set()
        unique_deals = []
        for deal in deals:
            key = deal['brand'].lower()
            if key not in seen:
                seen.add(key)
                unique_deals.append(deal)
        
        return unique_deals[:10]
