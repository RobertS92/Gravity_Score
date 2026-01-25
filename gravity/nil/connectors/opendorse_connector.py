"""
Opendorse NIL Connector
NIL marketplace with athlete profiles and deal announcements
"""

from typing import Dict, Any, Optional, List
import re
import logging
import asyncio
from gravity.nil.connectors.base import BaseNILConnector

logger = logging.getLogger(__name__)


class OpendorseConnector(BaseNILConnector):
    """
    Connector for Opendorse - NIL marketplace
    Opendorse provides:
    - Athlete profiles
    - Deal marketplace listings
    - Brand partnerships
    - Social metrics
    """
    
    BASE_URL = "https://opendorse.com"
    SEARCH_URL = "https://opendorse.com/athletes"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.rate_limit_delay = 0.5  # Reduce to 0.5s for stable Opendorse
    
    def get_source_name(self) -> str:
        return "opendorse"
    
    def get_source_reliability_weight(self) -> float:
        return 0.90  # Tier 1: High reliability
    
    async def fetch_raw_async(
        self,
        athlete_name: str,
        school: Optional[str] = None,
        sport: Optional[str] = None,
        **filters
    ) -> Optional[Dict[str, Any]]:
        """
        Async fetch raw data from Opendorse
        
        Args:
            athlete_name: Name of athlete
            school: School/college name
            sport: Sport type
        
        Returns:
            Raw data from Opendorse
        """
        try:
            # Try search page first
            search_query = athlete_name.replace(' ', '+')
            url = f"{self.SEARCH_URL}?q={search_query}"
            
            if school:
                url += f"&school={school.replace(' ', '+')}"
            
            logger.debug(f"Fetching Opendorse data (async): {url}")
            
            client = await self.get_async_client()
            response = await client.get(url, timeout=15.0)
            
            if not response or response.status_code != 200:
                return None
            
            soup = self.parse_html(response.text)
            
            # Find athlete profile link
            profile_url = self._find_profile_link(soup, athlete_name)
            
            # Fetch profile if found
            profile_data = None
            if profile_url:
                try:
                    profile_response = await client.get(profile_url, timeout=15.0)
                    if profile_response and profile_response.status_code == 200:
                        profile_soup = self.parse_html(profile_response.text)
                        profile_data = self._extract_profile_data(profile_soup)
                except Exception as e:
                    logger.debug(f"Failed to fetch Opendorse profile: {e}")
            
            return {
                'search_results': soup.get_text(),
                'profile_url': profile_url,
                'profile_data': profile_data,
                'raw_html': response.text,
                'athlete_name': athlete_name
            }
            
        except Exception as e:
            logger.error(f"Opendorse fetch failed for {athlete_name}: {e}")
            return None
    
    def fetch_raw(
        self,
        athlete_name: str,
        school: Optional[str] = None,
        sport: Optional[str] = None,
        **filters
    ) -> Optional[Dict[str, Any]]:
        """
        Sync wrapper around async fetch_raw
        
        Args:
            athlete_name: Name of athlete
            school: School/college name
            sport: Sport type
        
        Returns:
            Raw data from Opendorse
        """
        return asyncio.run(self.fetch_raw_async(athlete_name, school, sport, **filters))
    
    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Opendorse data
        
        Args:
            raw_data: Raw response
        
        Returns:
            Normalized data
        """
        normalized = {
            'nil_valuation': None,
            'nil_deals': [],
            'profile_url': raw_data.get('profile_url'),
            'social_metrics': {},
            'marketplace_listing': None
        }
        
        profile_data = raw_data.get('profile_data')
        if profile_data:
            # Extract valuation if listed
            if 'valuation' in profile_data:
                normalized['nil_valuation'] = profile_data['valuation']
            
            # Extract social metrics
            if 'social' in profile_data:
                normalized['social_metrics'] = profile_data['social']
            
            # Extract deals
            if 'deals' in profile_data:
                normalized['nil_deals'] = profile_data['deals']
            
            # Marketplace listing info
            if 'marketplace_active' in profile_data:
                normalized['marketplace_listing'] = {
                    'active': profile_data['marketplace_active'],
                    'rate': profile_data.get('marketplace_rate'),
                    'categories': profile_data.get('marketplace_categories', [])
                }
        
        return normalized
    
    def _find_profile_link(self, soup, athlete_name: str) -> Optional[str]:
        """Find athlete profile link in search results"""
        try:
            name_parts = athlete_name.lower().split()
            
            # Look for athlete cards or profile links
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                link_text = link.get_text().lower()
                
                # Check if all name parts are in link text
                if all(part in link_text for part in name_parts):
                    if '/athletes/' in href:
                        if href.startswith('http'):
                            return href
                        else:
                            return f"{self.BASE_URL}{href}"
            
            return None
        except Exception as e:
            logger.debug(f"Failed to find Opendorse profile: {e}")
            return None
    
    def _extract_profile_data(self, soup) -> Dict[str, Any]:
        """Extract structured data from profile page"""
        data = {}
        
        text = soup.get_text()
        text_lower = text.lower()
        
        # Extract valuation if shown
        valuation = self._extract_valuation_from_text(text)
        if valuation:
            data['valuation'] = valuation
        
        # Extract social follower counts
        social = self._extract_social_metrics(text)
        if social:
            data['social'] = social
        
        # Check if marketplace active
        if 'available for deals' in text_lower or 'contact for partnerships' in text_lower:
            data['marketplace_active'] = True
            
            # Try to extract rate
            rate = self._extract_marketplace_rate(text)
            if rate:
                data['marketplace_rate'] = rate
        
        # Extract deal mentions
        deals = self._extract_deal_mentions(text)
        if deals:
            data['deals'] = deals
        
        return data
    
    def _extract_valuation_from_text(self, text: str) -> Optional[float]:
        """Extract valuation from profile text with enhanced patterns"""
        patterns = [
            # Exact patterns
            r'estimated value[:\s]+\$\s*([\d,.]+)\s*([KMB])?',
            r'nil value[:\s]+\$\s*([\d,.]+)\s*([KMB])?',
            
            # Reversed
            r'\$\s*([\d,.]+)\s*([KMB])?\s+(?:nil\s+)?value',
            
            # Parentheses
            r'\((?:nil\s+)?value[:\s]+\$\s*([\d,.]+)\s*([KMB])?\)',
            
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
    
    def _extract_social_metrics(self, text: str) -> Dict[str, int]:
        """Extract social follower counts"""
        metrics = {}
        
        # Look for follower counts
        patterns = {
            'instagram': r'instagram.*?(\d+(?:,\d+)*)\s*followers',
            'twitter': r'twitter.*?(\d+(?:,\d+)*)\s*followers',
            'tiktok': r'tiktok.*?(\d+(?:,\d+)*)\s*followers'
        }
        
        for platform, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                count_str = match.group(1).replace(',', '')
                metrics[platform] = int(count_str)
        
        return metrics
    
    def _extract_marketplace_rate(self, text: str) -> Optional[float]:
        """Extract marketplace rate if listed"""
        patterns = [
            r'starting at.*?\$\s*([\d,.]+)',
            r'rate.*?\$\s*([\d,.]+)',
            r'\$\s*([\d,.]+)\s*per post'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1).replace(',', ''))
        
        return None
    
    def _extract_deal_mentions(self, text: str) -> List[Dict[str, Any]]:
        """Extract mentions of NIL deals from profile"""
        deals = []
        
        # Look for partnership mentions
        partnership_pattern = r'(?:partnership|deal|sponsor|endorsement)\s+with\s+([\w\s&]+?)(?:\.|,|\n)'
        matches = re.finditer(partnership_pattern, text, re.IGNORECASE)
        
        for match in matches:
            brand_name = match.group(1).strip()
            if len(brand_name) < 50:  # Reasonable brand name length
                deals.append({
                    'brand': brand_name,
                    'type': 'Partnership',
                    'source': 'opendorse'
                })
        
        return deals[:10]  # Limit to 10
