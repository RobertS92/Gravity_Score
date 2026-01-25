"""
Teamworks NIL Connector
Team management platform with official athlete data
"""

from typing import Dict, Any, Optional, List
import re
import logging
import asyncio
from gravity.nil.connectors.base import BaseNILConnector

logger = logging.getLogger(__name__)


class TeamworksConnector(BaseNILConnector):
    """
    Connector for Teamworks - Team management platform
    Teamworks provides:
    - Official team roster data
    - Team-sanctioned NIL deals
    - Compliance tracking
    - Athletic department partnerships
    """
    
    BASE_URL = "https://teamworks.com"
    
    def get_source_name(self) -> str:
        return "teamworks"
    
    def get_source_reliability_weight(self) -> float:
        return 0.80  # Tier 2: Official school data
    
    async def fetch_raw_async(
        self,
        athlete_name: str,
        school: Optional[str] = None,
        sport: Optional[str] = None,
        **filters
    ) -> Optional[Dict[str, Any]]:
        """Async fetch raw data from Teamworks"""
        try:
            if not school:
                logger.debug("Teamworks requires school name")
                return None
            
            school_slug = school.lower().replace(' ', '-')
            urls = [
                f"{self.BASE_URL}/partnerships/{school_slug}",
                f"{self.BASE_URL}/schools/{school_slug}",
                f"{self.BASE_URL}/nil/{school_slug}"
            ]
            
            client = await self.get_async_client()
            
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
            logger.error(f"Teamworks fetch failed for {athlete_name}: {e}")
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
        Normalize Teamworks data
        
        Args:
            raw_data: Raw response
        
        Returns:
            Normalized data
        """
        normalized = {
            'nil_deals': [],
            'team_sanctioned': [],
            'compliance_status': None,
            'url': raw_data.get('url')
        }
        
        text = raw_data.get('school_page', '')
        
        # Extract team-sanctioned deals
        deals = self._extract_team_deals(text)
        if deals:
            normalized['nil_deals'] = deals
            normalized['team_sanctioned'] = deals  # All Teamworks deals are team-sanctioned
        
        # Check compliance mentions
        if 'compliance approved' in text.lower() or 'ncaa compliant' in text.lower():
            normalized['compliance_status'] = 'approved'
        
        return normalized
    
    def _extract_team_deals(self, text: str) -> List[Dict[str, Any]]:
        """Extract team-sanctioned NIL deals"""
        deals = []
        
        # Look for official partnership announcements
        patterns = [
            r'announces?\s+(?:partnership|deal)\s+with\s+([\w\s&]+?)(?:\.|,|\n)',
            r'([\w\s&]+?)\s+(?:partners?|signs?)\s+with',
            r'official\s+(?:partner|sponsor)\s+of\s+([\w\s&]+?)(?:\.|,|\n)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                brand_name = match.group(1).strip()
                if 3 < len(brand_name) < 50:
                    deals.append({
                        'brand': brand_name,
                        'type': 'Team-Sanctioned',
                        'source': 'teamworks',
                        'is_team_deal': True,
                        'compliance_approved': True
                    })
        
        return deals[:10]
