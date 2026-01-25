"""
INFLCR NIL Connector
Social analytics and NIL platform
"""

from typing import Dict, Any, Optional, List
import re
import logging
import asyncio
from gravity.nil.connectors.base import BaseNILConnector

logger = logging.getLogger(__name__)


class INFLCRConnector(BaseNILConnector):
    """
    Connector for INFLCR - Social analytics and NIL platform
    INFLCR provides:
    - Social media analytics
    - Content engagement metrics
    - NIL deal activity
    - Brand partnerships
    """
    
    BASE_URL = "https://inflcr.com"
    
    def get_source_name(self) -> str:
        return "inflcr"
    
    def get_source_reliability_weight(self) -> float:
        return 0.85  # Tier 2: Reliable social metrics
    
    async def fetch_raw_async(
        self,
        athlete_name: str,
        school: Optional[str] = None,
        sport: Optional[str] = None,
        **filters
    ) -> Optional[Dict[str, Any]]:
        """
        Async fetch raw data from INFLCR
        
        Args:
            athlete_name: Name of athlete
            school: School/college name
            sport: Sport type
        
        Returns:
            Raw data from INFLCR
        """
        try:
            if not school:
                logger.debug("INFLCR requires school name for search")
                return None
            
            school_slug = school.lower().replace(' ', '-').replace("'", '')
            urls = [
                f"{self.BASE_URL}/athletes/{school_slug}",
                f"{self.BASE_URL}/schools/{school_slug}/athletes"
            ]
            
            logger.debug(f"Fetching INFLCR data (async): {urls[0]}")
            
            client = await self.get_async_client()
            
            # Try both URLs
            for url in urls:
                try:
                    response = await client.get(url, timeout=15.0)
                    if response and response.status_code == 200:
                        soup = self.parse_html(response.text)
                        text = soup.get_text()
                        
                        if athlete_name.lower() in text.lower():
                            return {
                                'school_page': text,
                                'url': url,
                                'raw_html': response.text,
                                'athlete_name': athlete_name
                            }
                except Exception as e:
                    logger.debug(f"Failed to fetch {url}: {e}")
            
            return None
            
        except Exception as e:
            logger.error(f"INFLCR fetch failed for {athlete_name}: {e}")
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
        Normalize INFLCR data
        
        Args:
            raw_data: Raw response
        
        Returns:
            Normalized data
        """
        normalized = {
            'social_metrics': {},
            'engagement_rate': None,
            'content_activity': {},
            'nil_deals': [],
            'url': raw_data.get('url')
        }
        
        text = raw_data.get('school_page', '')
        
        # Extract social metrics
        social = self._extract_social_metrics(text)
        if social:
            normalized['social_metrics'] = social
        
        # Extract engagement rate
        engagement = self._extract_engagement_rate(text)
        if engagement:
            normalized['engagement_rate'] = engagement
        
        # Extract content activity
        content = self._extract_content_activity(text)
        if content:
            normalized['content_activity'] = content
        
        # Extract deal mentions
        deals = self._extract_deals(text)
        if deals:
            normalized['nil_deals'] = deals
        
        return normalized
    
    def _extract_social_metrics(self, text: str) -> Dict[str, Any]:
        """Extract social media metrics"""
        metrics = {}
        
        # Followers
        patterns = {
            'total_followers': r'(\d+(?:,\d+)*)\s*total\s*followers',
            'instagram_followers': r'instagram.*?(\d+(?:,\d+)*)\s*followers',
            'twitter_followers': r'twitter.*?(\d+(?:,\d+)*)\s*followers',
            'tiktok_followers': r'tiktok.*?(\d+(?:,\d+)*)\s*followers'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                count = int(match.group(1).replace(',', ''))
                metrics[key] = count
        
        # Reach/impressions
        reach_pattern = r'(\d+(?:,\d+)*)\s*(?:reach|impressions)'
        match = re.search(reach_pattern, text, re.IGNORECASE)
        if match:
            metrics['reach'] = int(match.group(1).replace(',', ''))
        
        return metrics
    
    def _extract_engagement_rate(self, text: str) -> Optional[float]:
        """Extract engagement rate percentage"""
        patterns = [
            r'engagement.*?(\d+(?:\.\d+)?)\s*%',
            r'(\d+(?:\.\d+)?)\s*%\s*engagement'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        
        return None
    
    def _extract_content_activity(self, text: str) -> Dict[str, int]:
        """Extract content posting activity"""
        activity = {}
        
        # Posts per week/month
        patterns = {
            'posts_per_week': r'(\d+)\s*posts?\s*per\s*week',
            'posts_per_month': r'(\d+)\s*posts?\s*per\s*month',
            'total_posts': r'(\d+)\s*total\s*posts?'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                activity[key] = int(match.group(1))
        
        return activity
    
    def _extract_deals(self, text: str) -> List[Dict[str, Any]]:
        """Extract NIL deal mentions"""
        deals = []
        
        # Look for brand partnerships
        brand_pattern = r'(?:partnership|deal|sponsor)\s+with\s+([\w\s&]+?)(?:\.|,|\n)'
        matches = re.finditer(brand_pattern, text, re.IGNORECASE)
        
        for match in matches:
            brand_name = match.group(1).strip()
            if 3 < len(brand_name) < 50:
                deals.append({
                    'brand': brand_name,
                    'type': 'Social Content',
                    'source': 'inflcr'
                })
        
        return deals[:5]
