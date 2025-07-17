"""
Firecrawl Agent for Enhanced Social Media and Web Data Scraping
Uses official Firecrawl SDK with advanced features like structured extraction and mapping
"""

import os
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Import the official Firecrawl SDK
try:
    from firecrawl import FirecrawlApp
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False
    logger.warning("Firecrawl SDK not available. Install with: pip install firecrawl-py")

class SocialMediaProfile(BaseModel):
    """Schema for social media profile extraction."""
    handle: Optional[str] = Field(description="Social media handle (e.g., @username)")
    followers: Optional[int] = Field(description="Number of followers")
    following: Optional[int] = Field(description="Number of following")
    verified: Optional[bool] = Field(description="Whether the account is verified")
    bio: Optional[str] = Field(description="Account bio or description")
    posts_count: Optional[int] = Field(description="Number of posts")

class WikipediaData(BaseModel):
    """Schema for Wikipedia biographical data extraction."""
    birth_date: Optional[str] = Field(description="Birth date of the person")
    birth_place: Optional[str] = Field(description="Birth place of the person")
    college: Optional[str] = Field(description="College or university attended")
    draft_info: Optional[str] = Field(description="NFL draft information")
    career_highlights: Optional[List[str]] = Field(description="Career highlights and achievements")
    awards: Optional[List[str]] = Field(description="Awards and honors received")
    pro_bowls: Optional[str] = Field(description="Pro Bowl selections")
    all_pro: Optional[str] = Field(description="All-Pro selections")
    hall_of_fame: Optional[bool] = Field(description="Hall of Fame status")

class ContractData(BaseModel):
    """Schema for contract and salary data extraction."""
    current_salary: Optional[str] = Field(description="Current year salary")
    contract_value: Optional[str] = Field(description="Total contract value")
    contract_years: Optional[str] = Field(description="Contract duration in years")
    guaranteed_money: Optional[str] = Field(description="Guaranteed money amount")
    signing_bonus: Optional[str] = Field(description="Signing bonus amount")
    career_earnings: Optional[str] = Field(description="Total career earnings")

class FirecrawlAgent:
    """Advanced agent for intelligent web scraping using official Firecrawl SDK."""
    
    def __init__(self):
        self.api_key = os.getenv("FIRECRAWL_API_KEY", "your-api-key-here")
        self.request_delay = 2
        self.max_retries = 3
        
        if not FIRECRAWL_AVAILABLE:
            logger.error("Firecrawl SDK not available")
            self.app = None
            return
            
        try:
            self.app = FirecrawlApp(api_key=self.api_key)
            logger.info("Firecrawl agent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firecrawl app: {e}")
            self.app = None
        
    def scrape_url(self, url: str, extract_schema: Dict = None, formats: List[str] = None) -> Dict:
        """
        Scrape a single URL using official Firecrawl SDK.
        
        Args:
            url: URL to scrape
            extract_schema: Optional schema for structured data extraction
            formats: List of output formats (markdown, html, json, etc.)
            
        Returns:
            Dictionary with scraped data
        """
        if not self.app:
            return {"error": "Firecrawl SDK not initialized"}
            
        try:
            formats = formats or ["markdown", "html"]
            
            scrape_params = {
                "formats": formats,
                "onlyMainContent": True,
                "timeout": 30000
            }
            
            if extract_schema:
                scrape_params["formats"] = ["json"]
                scrape_params["jsonOptions"] = {"schema": extract_schema}
            
            result = self.app.scrape_url(url, **scrape_params)
            
            if result.get("success"):
                return {"success": True, "data": result.get("data", {})}
            else:
                return {"error": result.get("error", "Unknown error")}
                
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {"error": str(e)}
    
    def search_social_media_profiles(self, player_name: str, team: str) -> Dict:
        """
        Search for social media profiles using direct URL construction and web search.
        
        Args:
            player_name: Name of the player
            team: Team name
            
        Returns:
            Dictionary with discovered social media profiles
        """
        social_data = {
            'twitter': None,
            'instagram': None,
            'tiktok': None,
            'youtube': None,
            'discovery_timestamp': datetime.now().isoformat()
        }
        
        # Try direct profile URLs first (more reliable than Google search)
        direct_urls = self._construct_direct_profile_urls(player_name, team)
        
        for platform, potential_urls in direct_urls.items():
            try:
                for url in potential_urls:
                    result = self.scrape_url(url)
                    if result and 'data' in result and 'error' not in result:
                        profile_data = self._extract_social_profile_from_page(result['data'], platform, player_name, url)
                        if profile_data:
                            social_data[platform] = profile_data
                            break
                
                # Rate limiting
                time.sleep(self.request_delay)
                
            except Exception as e:
                logger.debug(f"Error searching {platform} for {player_name}: {e}")
                continue
        
        return social_data
    
    def scrape_player_wikipedia(self, player_name: str, team: str) -> Dict:
        """
        Scrape Wikipedia page using Firecrawl's extract endpoint with structured data.
        
        Args:
            player_name: Name of the player
            team: Team name
            
        Returns:
            Dictionary with Wikipedia data
        """
        if not self.app:
            return self._fallback_wikipedia_search(player_name, team)
            
        try:
            # Use Firecrawl's extract endpoint for intelligent Wikipedia discovery
            search_urls = [
                f"https://www.google.com/search?q=\"{player_name}\"+NFL+{team}+wikipedia",
                f"https://en.wikipedia.org/wiki/{player_name.replace(' ', '_')}",
                f"https://en.wikipedia.org/wiki/{player_name.replace(' ', '_')}_(American_football)"
            ]
            
            # Use extract with structured schema for Wikipedia data
            extract_result = self.app.extract(
                urls=search_urls,
                prompt=f"Extract comprehensive biographical information for NFL player {player_name}, including birth date, birth place, college, draft information, career highlights, awards, Pro Bowl selections, and All-Pro selections.",
                schema=WikipediaData.model_json_schema(),
                enable_web_search=True
            )
            
            if extract_result.get("success") and extract_result.get("data"):
                bio_data = extract_result["data"]
                
                # Filter out None values and construct response
                filtered_data = {k: v for k, v in bio_data.items() if v is not None}
                
                if filtered_data:
                    return {
                        'wikipedia_url': self._find_wikipedia_url(search_urls, player_name),
                        'biographical_data': filtered_data,
                        'scraped_at': datetime.now().isoformat(),
                        'extraction_method': 'firecrawl_extract'
                    }
            
        except Exception as e:
            logger.error(f"Error scraping Wikipedia for {player_name}: {e}")
        
        return {}
    
    def scrape_contract_data(self, player_name: str, team: str) -> Dict:
        """
        Scrape contract and salary information from Spotrac.
        
        Args:
            player_name: Name of the player
            team: Team name
            
        Returns:
            Dictionary with contract data
        """
        try:
            # Search for Spotrac page
            search_query = f'"{player_name}" NFL {team} contract salary site:spotrac.com'
            search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
            
            search_result = self.scrape_url(search_url)
            if not search_result or 'data' not in search_result:
                return {}
            
            # Extract Spotrac URL
            spotrac_url = self._extract_spotrac_url(search_result['data'])
            if not spotrac_url:
                return {}
            
            # Scrape Spotrac page with structured extraction
            extract_schema = {
                "type": "object",
                "properties": {
                    "current_salary": {"type": "string", "description": "Current year salary"},
                    "contract_value": {"type": "string", "description": "Total contract value"},
                    "contract_years": {"type": "string", "description": "Contract duration"},
                    "guaranteed_money": {"type": "string", "description": "Guaranteed money"},
                    "signing_bonus": {"type": "string", "description": "Signing bonus"},
                    "career_earnings": {"type": "string", "description": "Career earnings"}
                }
            }
            
            spotrac_result = self.scrape_url(spotrac_url, extract_schema)
            if spotrac_result and 'data' in spotrac_result:
                return {
                    'spotrac_url': spotrac_url,
                    'contract_data': spotrac_result['data'].get('extract', {}),
                    'scraped_at': datetime.now().isoformat()
                }
            
        except Exception as e:
            logger.error(f"Error scraping contract data for {player_name}: {e}")
        
        return {}
    
    def _construct_direct_profile_urls(self, player_name: str, team: str) -> Dict[str, List[str]]:
        """Construct potential social media profile URLs directly."""
        # Clean the player name for URL construction
        clean_name = player_name.replace(' ', '').replace('.', '').replace("'", '').lower()
        name_parts = player_name.lower().split()
        
        # Common username patterns
        patterns = [
            clean_name,
            f"{name_parts[0]}{name_parts[-1]}",
            f"{name_parts[0][0]}{name_parts[-1]}",
            f"{name_parts[0]}_{name_parts[-1]}",
            f"{clean_name}{team.lower()}",
            f"{clean_name}nfl"
        ]
        
        return {
            'twitter': [f"https://twitter.com/{pattern}" for pattern in patterns],
            'instagram': [f"https://instagram.com/{pattern}" for pattern in patterns],
            'tiktok': [f"https://tiktok.com/@{pattern}" for pattern in patterns],
            'youtube': [f"https://youtube.com/@{pattern}" for pattern in patterns]
        }
    
    def _construct_wikipedia_urls(self, player_name: str) -> List[str]:
        """Construct potential Wikipedia URLs for the player."""
        # Clean the player name for Wikipedia URL construction
        wiki_name = player_name.replace(' ', '_').replace('.', '')
        
        return [
            f"https://en.wikipedia.org/wiki/{wiki_name}",
            f"https://en.wikipedia.org/wiki/{wiki_name}_(American_football)",
            f"https://en.wikipedia.org/wiki/{wiki_name}_(football_player)"
        ]
    
    def _extract_social_profile_from_page(self, page_data: Dict, platform: str, player_name: str, url: str) -> Optional[Dict]:
        """Extract social media profile information from the actual page."""
        try:
            # Check if the page contains the player's name or relevant content
            content = page_data.get('markdown', '').lower()
            if not content or player_name.lower() not in content:
                return None
            
            # Basic profile structure
            profile = {
                'handle': self._extract_handle_from_url(url),
                'url': url,
                'followers': None,
                'verified': None,
                'found_via': 'firecrawl_direct'
            }
            
            # Try to extract follower count from content
            if platform == 'twitter':
                profile['followers'] = self._extract_twitter_followers(content)
            elif platform == 'instagram':
                profile['followers'] = self._extract_instagram_followers(content)
            elif platform == 'tiktok':
                profile['followers'] = self._extract_tiktok_followers(content)
            elif platform == 'youtube':
                profile['followers'] = self._extract_youtube_subscribers(content)
            
            return profile
            
        except Exception as e:
            logger.debug(f"Error extracting {platform} profile from page: {e}")
            return None
    
    def _extract_handle_from_url(self, url: str) -> str:
        """Extract handle from social media URL."""
        try:
            if 'twitter.com' in url or 'x.com' in url:
                return f"@{url.split('/')[-1]}"
            elif 'instagram.com' in url:
                return f"@{url.split('/')[-1]}"
            elif 'tiktok.com' in url:
                return f"@{url.split('/')[-1].replace('@', '')}"
            elif 'youtube.com' in url:
                return f"@{url.split('/')[-1].replace('@', '')}"
            return url.split('/')[-1]
        except:
            return None
    
    def _extract_twitter_followers(self, content: str) -> Optional[int]:
        """Extract Twitter follower count from page content."""
        try:
            import re
            # Look for follower patterns
            patterns = [
                r'(\d{1,3}(?:,\d{3})*)\s*followers',
                r'followers[^\d]*(\d{1,3}(?:,\d{3})*)',
                r'(\d+\.?\d*[kmb]?)\s*followers'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return self._parse_follower_count(match.group(1))
            return None
        except:
            return None
    
    def _extract_instagram_followers(self, content: str) -> Optional[int]:
        """Extract Instagram follower count from page content."""
        try:
            import re
            patterns = [
                r'(\d{1,3}(?:,\d{3})*)\s*followers',
                r'followers[^\d]*(\d{1,3}(?:,\d{3})*)',
                r'(\d+\.?\d*[kmb]?)\s*followers'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return self._parse_follower_count(match.group(1))
            return None
        except:
            return None
    
    def _extract_tiktok_followers(self, content: str) -> Optional[int]:
        """Extract TikTok follower count from page content."""
        try:
            import re
            patterns = [
                r'(\d{1,3}(?:,\d{3})*)\s*followers',
                r'followers[^\d]*(\d{1,3}(?:,\d{3})*)',
                r'(\d+\.?\d*[kmb]?)\s*followers'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return self._parse_follower_count(match.group(1))
            return None
        except:
            return None
    
    def _extract_youtube_subscribers(self, content: str) -> Optional[int]:
        """Extract YouTube subscriber count from page content."""
        try:
            import re
            patterns = [
                r'(\d{1,3}(?:,\d{3})*)\s*subscribers',
                r'subscribers[^\d]*(\d{1,3}(?:,\d{3})*)',
                r'(\d+\.?\d*[kmb]?)\s*subscribers'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return self._parse_follower_count(match.group(1))
            return None
        except:
            return None
    
    def _parse_follower_count(self, count_str: str) -> Optional[int]:
        """Parse follower count string to integer."""
        try:
            count_str = count_str.replace(',', '').lower()
            if 'k' in count_str:
                return int(float(count_str.replace('k', '')) * 1000)
            elif 'm' in count_str:
                return int(float(count_str.replace('m', '')) * 1000000)
            elif 'b' in count_str:
                return int(float(count_str.replace('b', '')) * 1000000000)
            else:
                return int(count_str)
        except:
            return None
    
    def _extract_wikipedia_url(self, search_data: Dict) -> Optional[str]:
        """Extract Wikipedia URL from search results."""
        try:
            # Parse search results to find Wikipedia links
            # This is a simplified implementation
            if 'markdown' in search_data:
                content = search_data['markdown']
                if 'wikipedia.org' in content:
                    # Extract the first Wikipedia URL found
                    import re
                    wiki_match = re.search(r'https://en\.wikipedia\.org/wiki/[^\s\)]+', content)
                    if wiki_match:
                        return wiki_match.group(0)
            return None
        except Exception as e:
            logger.debug(f"Error extracting Wikipedia URL: {e}")
            return None
    
    def _extract_spotrac_url(self, search_data: Dict) -> Optional[str]:
        """Extract Spotrac URL from search results."""
        try:
            # Parse search results to find Spotrac links
            if 'markdown' in search_data:
                content = search_data['markdown']
                if 'spotrac.com' in content:
                    import re
                    spotrac_match = re.search(r'https://www\.spotrac\.com/[^\s\)]+', content)
                    if spotrac_match:
                        return spotrac_match.group(0)
            return None
        except Exception as e:
            logger.debug(f"Error extracting Spotrac URL: {e}")
            return None


def main():
    """Test the Firecrawl agent."""
    agent = FirecrawlAgent()
    
    # Test with a well-known player
    player_name = "Brock Purdy"
    team = "49ers"
    
    print(f"=== TESTING FIRECRAWL AGENT ===")
    print(f"Player: {player_name} ({team})")
    
    # Test social media search
    print("\n--- Social Media Search ---")
    social_data = agent.search_social_media_profiles(player_name, team)
    for platform, data in social_data.items():
        if data and platform != 'discovery_timestamp':
            print(f"{platform}: {data}")
    
    # Test Wikipedia scraping
    print("\n--- Wikipedia Scraping ---")
    wiki_data = agent.scrape_player_wikipedia(player_name, team)
    if wiki_data:
        print(f"Wikipedia URL: {wiki_data.get('wikipedia_url')}")
        print(f"Biographical Data: {wiki_data.get('biographical_data', {})}")
    
    # Test contract data scraping
    print("\n--- Contract Data Scraping ---")
    contract_data = agent.scrape_contract_data(player_name, team)
    if contract_data:
        print(f"Spotrac URL: {contract_data.get('spotrac_url')}")
        print(f"Contract Data: {contract_data.get('contract_data', {})}")


if __name__ == "__main__":
    main()