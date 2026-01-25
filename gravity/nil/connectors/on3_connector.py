"""
On3.com NIL Connector
Primary NIL platform with verified valuations and rankings
"""

from typing import Dict, Any, Optional, List
import re
import logging
import asyncio
from gravity.nil.connectors.base import BaseNILConnector, DataNotFoundError

logger = logging.getLogger(__name__)


class On3Connector(BaseNILConnector):
    """
    Connector for On3.com - primary NIL data source
    On3 provides:
    - NIL valuations
    - National rankings
    - Deal announcements
    - Brand partnerships
    """
    
    BASE_URL = "https://www.on3.com"
    SEARCH_URL = "https://www.on3.com/db/search/"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.rate_limit_delay = 0.5  # Reduce to 0.5s for stable On3
    
    def get_source_name(self) -> str:
        return "on3"
    
    def get_source_reliability_weight(self) -> float:
        return 0.95  # Tier 1: Most reliable NIL data
    
    async def fetch_raw_async(
        self,
        athlete_name: str,
        school: Optional[str] = None,
        sport: Optional[str] = None,
        **filters
    ) -> Optional[Dict[str, Any]]:
        """
        Async fetch raw data from On3.com
        Fetches search and profile pages in parallel when possible
        
        Args:
            athlete_name: Name of athlete
            school: School/college name
            sport: Sport type
        
        Returns:
            Raw HTML and extracted data
        """
        try:
            # Build search URL
            search_query = athlete_name.replace(' ', '+')
            search_url = f"{self.SEARCH_URL}?q={search_query}"
            
            logger.debug(f"Fetching On3 data (async): {search_url}")
            
            # Fetch search page
            client = await self.get_async_client()
            search_response = await client.get(search_url, timeout=15.0)
            
            if not search_response or search_response.status_code != 200:
                return None
            
            # Parse HTML
            soup = self.parse_html(search_response.text)
            
            # Extract profile link if available
            profile_url = self._find_profile_link(soup, athlete_name)
            
            # If profile found, fetch it (no extra delay needed)
            profile_data = None
            if profile_url:
                try:
                    profile_response = await client.get(profile_url, timeout=15.0)
                    if profile_response and profile_response.status_code == 200:
                        profile_soup = self.parse_html(profile_response.text)
                        profile_data = profile_soup.get_text()
                except Exception as e:
                    logger.debug(f"Failed to fetch On3 profile: {e}")
            
            return {
                'search_html': soup.get_text(),
                'profile_url': profile_url,
                'profile_data': profile_data,
                'raw_html': search_response.text,
                'athlete_name': athlete_name  # Store for AI context
            }
            
        except Exception as e:
            logger.error(f"On3 fetch failed for {athlete_name}: {e}")
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
        Maintained for backward compatibility
        
        Args:
            athlete_name: Name of athlete
            school: School/college name
            sport: Sport type
        
        Returns:
            Raw HTML and extracted data
        """
        return asyncio.run(self.fetch_raw_async(athlete_name, school, sport, **filters))
    
    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize On3 data into canonical schema
        
        Args:
            raw_data: Raw response from fetch_raw()
        
        Returns:
            Normalized data
        """
        normalized = {
            'nil_valuation': None,
            'nil_ranking': None,
            'nil_deals': [],
            'profile_url': raw_data.get('profile_url')
        }
        
        # Combine search and profile text
        text = raw_data.get('search_html', '') + ' ' + (raw_data.get('profile_data', '') or '')
        text_lower = text.lower()
        athlete_name = raw_data.get('athlete_name', '')
        
        # Extract NIL valuation
        valuation = self._extract_valuation(text)
        if valuation:
            normalized['nil_valuation'] = valuation
        
        # Extract ranking
        ranking = self._extract_ranking(text)
        if ranking:
            normalized['nil_ranking'] = ranking
        
        # Extract deals with AI fallback
        deals = self._extract_deals(text, athlete_name)
        if deals:
            normalized['nil_deals'] = deals
        
        return normalized
    
    def _find_profile_link(self, soup, athlete_name: str) -> Optional[str]:
        """Find athlete profile link in search results"""
        try:
            # Look for links containing athlete name
            name_parts = athlete_name.lower().split()
            
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                link_text = link.get_text().lower()
                
                # Check if link text matches athlete name
                if all(part in link_text for part in name_parts):
                    if href.startswith('/'):
                        return f"{self.BASE_URL}{href}"
                    elif href.startswith('http'):
                        return href
            
            return None
        except Exception as e:
            logger.debug(f"Failed to find profile link: {e}")
            return None
    
    def _extract_valuation(self, text: str) -> Optional[float]:
        """
        Extract NIL valuation from text with enhanced patterns
        
        Supports:
        - Exact: "NIL Valuation: $1.2M"
        - Reversed: "$1.2M NIL"
        - Parentheses: "(NIL: $1.2M)"
        - Estimated: "estimated at $1.2M"
        - Range: "$1M-$1.5M" (returns average)
        """
        patterns = [
            # Exact: "NIL Valuation: $1.2M"
            r'nil\s+valuation[:\s]+\$\s*([\d,.]+)\s*([KMB])?',
            
            # Reversed: "$1.2M NIL"
            r'\$\s*([\d,.]+)\s*([KMB])?\s+nil',
            
            # Parentheses: "(NIL: $1.2M)"
            r'\(nil[:\s]+\$\s*([\d,.]+)\s*([KMB])?\)',
            
            # Estimated: "estimated at $1.2M"
            r'estimated\s+(?:at\s+)?\$\s*([\d,.]+)\s*([KMB])?',
            
            # Range: "$1M-$1.5M" or "$1M to $1.5M"
            r'\$\s*([\d,.]+)\s*([KMB])?\s*(?:-|to)\s*\$\s*([\d,.]+)\s*([KMB])?',
            
            # General valuation pattern
            r'valuation.*?\$\s*([\d,.]+)\s*([KMB])?',
            r'\$\s*([\d,.]+)\s*([KMB])?\s*valuation'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Handle range (4 groups)
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
    
    def _extract_ranking(self, text: str) -> Optional[int]:
        """
        Extract NIL ranking from text
        
        On3 shows rankings like:
        - "#42 NIL ranking"
        - "Ranked #15 in NIL"
        """
        patterns = [
            r'nil.*?rank.*?#?(\d+)',
            r'#(\d+).*?nil.*?rank',
            r'ranked?\s+#?(\d+).*?nil'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        return None
    
    def _extract_deals(self, text: str, athlete_name: str = None) -> List[Dict[str, Any]]:
        """
        Extract NIL deals from text with AI fallback
        
        Args:
            text: Text to extract from
            athlete_name: Athlete name for AI context
        
        Returns:
            List of deal dictionaries
        """
        # Try regex extraction first
        deals = self._extract_deals_regex(text)
        
        # If few/no deals found and athlete_name provided, try AI
        if len(deals) < 2 and athlete_name:
            logger.debug(f"On3: Only {len(deals)} deals found via regex, trying AI fallback for {athlete_name}")
            ai_deals = self.extract_with_ai_fallback(
                text=text,
                extraction_type='nil_deals',
                athlete_name=athlete_name,
                use_ai=True
            )
            if ai_deals and isinstance(ai_deals, list):
                for ai_deal in ai_deals:
                    if ai_deal.get('brand'):
                        deals.append({
                            'brand': ai_deal['brand'],
                            'type': ai_deal.get('type', 'Partnership'),
                            'value': ai_deal.get('value'),
                            'source': 'on3_ai',
                            'is_local': False
                        })
        
        return deals[:10]  # Limit to top 10
    
    def _extract_deals_regex(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract NIL deals using regex patterns
        
        Args:
            text: Text to extract from
        
        Returns:
            List of deal dictionaries
        """
        deals = []
        
        # Common NIL brand list (subset for On3 detection)
        brands = [
            'nike', 'adidas', 'jordan', 'under armour', 'puma',
            'gatorade', 'powerade', 'body armor',
            'ea sports', '2k sports', 'madden',
            'state farm', 'geico', 'progressive',
            'apple', 'samsung', 'beats',
            'mcdonalds', 'subway', 'chipotle'
        ]
        
        text_lower = text.lower()
        
        # Look for brand mentions near deal keywords
        for brand in brands:
            if brand in text_lower:
                # Check if near deal keywords
                brand_index = text_lower.find(brand)
                context_start = max(0, brand_index - 100)
                context_end = min(len(text_lower), brand_index + len(brand) + 100)
                context = text_lower[context_start:context_end]
                
                deal_keywords = ['partnership', 'deal', 'sponsor', 'endorsement', 'signs', 'announces']
                if any(keyword in context for keyword in deal_keywords):
                    deals.append({
                        'brand': brand.title(),
                        'type': self._categorize_brand(brand),
                        'source': 'on3',
                        'is_local': False
                    })
        
        return deals
    
    def _extract_by_type(self, text: str, extraction_type: str) -> Optional[Any]:
        """
        Dispatch to appropriate regex extraction method for AI integration
        
        Args:
            text: Text to extract from
            extraction_type: Type of extraction
        
        Returns:
            Extracted data or None
        """
        if extraction_type == 'nil_deals':
            return self._extract_deals_regex(text)
        return None
    
    def _categorize_brand(self, brand: str) -> str:
        """Categorize brand into type"""
        brand_lower = brand.lower()
        
        if brand_lower in ['nike', 'adidas', 'jordan', 'under armour', 'puma']:
            return 'Apparel'
        elif brand_lower in ['gatorade', 'powerade', 'body armor']:
            return 'Sports Drink'
        elif brand_lower in ['ea sports', '2k sports', 'madden']:
            return 'Gaming'
        elif brand_lower in ['state farm', 'geico', 'progressive']:
            return 'Insurance'
        elif brand_lower in ['apple', 'samsung', 'beats']:
            return 'Technology'
        elif brand_lower in ['mcdonalds', 'subway', 'chipotle']:
            return 'Food & Beverage'
        else:
            return 'Other'
