"""
Advanced Firecrawl Agent with Manual Implementation
Implements Firecrawl's advanced features using direct API calls
"""

import os
import json
import requests
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

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

class AdvancedFirecrawlAgent:
    """Advanced Firecrawl agent with manual API implementation."""
    
    def __init__(self):
        self.api_key = os.getenv("FIRECRAWL_API_KEY", "your-api-key-here")
        self.base_url = "https://api.firecrawl.dev"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.request_delay = 2
        self.max_retries = 3
        
        logger.info("Advanced Firecrawl agent initialized")
    
    def scrape_url(self, url: str, formats: List[str] = None, actions: List[Dict] = None) -> Dict:
        """
        Scrape a URL using Firecrawl's /scrape endpoint.
        
        Args:
            url: URL to scrape
            formats: Output formats (markdown, html, json, etc.)
            actions: Actions to perform on the page
            
        Returns:
            Dictionary with scraped data
        """
        try:
            payload = {
                "url": url,
                "formats": formats or ["markdown", "html"],
                "onlyMainContent": True,
                "timeout": 30000
            }
            
            if actions:
                payload["actions"] = actions
            
            response = requests.post(
                f"{self.base_url}/v1/scrape",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Firecrawl scraping failed for {url}: {response.status_code}")
                return {"error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {"error": str(e)}
    
    def extract_structured_data(self, urls: List[str], prompt: str, schema: Dict = None) -> Dict:
        """
        Extract structured data using Firecrawl's /extract endpoint.
        
        Args:
            urls: List of URLs to extract from
            prompt: Natural language prompt for extraction
            schema: Optional JSON schema for structured output
            
        Returns:
            Dictionary with extracted data
        """
        try:
            payload = {
                "urls": urls,
                "prompt": prompt,
                "enableWebSearch": True
            }
            
            if schema:
                payload["schema"] = schema
            
            response = requests.post(
                f"{self.base_url}/v1/extract",
                headers=self.headers,
                json=payload,
                timeout=120
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Firecrawl extraction failed: {response.status_code}")
                return {"error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error extracting data: {e}")
            return {"error": str(e)}
    
    def map_website(self, url: str, search: str = None) -> Dict:
        """
        Map a website using Firecrawl's /map endpoint.
        
        Args:
            url: URL to map
            search: Optional search term to filter results
            
        Returns:
            Dictionary with mapped URLs
        """
        try:
            payload = {"url": url}
            
            if search:
                payload["search"] = search
            
            response = requests.post(
                f"{self.base_url}/v1/map",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Firecrawl mapping failed for {url}: {response.status_code}")
                return {"error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error mapping {url}: {e}")
            return {"error": str(e)}
    
    def crawl_website(self, url: str, limit: int = 10, include_subdomains: bool = False) -> Dict:
        """
        Crawl a website using Firecrawl's /crawl endpoint.
        
        Args:
            url: URL to crawl
            limit: Maximum number of pages to crawl
            include_subdomains: Whether to include subdomains
            
        Returns:
            Dictionary with crawl job ID
        """
        try:
            payload = {
                "url": url,
                "limit": limit,
                "allowSubdomains": include_subdomains,
                "formats": ["markdown", "html"]
            }
            
            response = requests.post(
                f"{self.base_url}/v1/crawl",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Firecrawl crawling failed for {url}: {response.status_code}")
                return {"error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            return {"error": str(e)}
    
    def search_social_media_profiles(self, player_name: str, team: str) -> Dict:
        """
        Search for social media profiles using Firecrawl's extract endpoint.
        
        Args:
            player_name: Name of the player
            team: Team name
            
        Returns:
            Dictionary with discovered social media profiles
        """
        try:
            # Use extract endpoint for intelligent social media discovery
            search_urls = [
                f"https://www.google.com/search?q=\"{player_name}\"+NFL+{team}+social+media+twitter+instagram"
            ]
            
            social_prompt = f"""
            Extract comprehensive social media profile information for NFL player {player_name} from team {team}.
            
            Find and extract:
            1. Twitter/X handle, followers, following, verification status
            2. Instagram handle, followers, following, verification status  
            3. TikTok handle, followers, following, verification status
            4. YouTube channel, subscribers, verification status
            5. Bio/description from each platform
            6. Profile URLs for each platform
            
            Return structured data for each platform found.
            """
            
            result = self.extract_structured_data(
                urls=search_urls,
                prompt=social_prompt,
                schema=SocialMediaProfile.model_json_schema()
            )
            
            if result.get("success") and result.get("data"):
                return {
                    'social_profiles': result["data"],
                    'discovery_timestamp': datetime.now().isoformat(),
                    'extraction_method': 'firecrawl_extract'
                }
            
        except Exception as e:
            logger.error(f"Error searching social media for {player_name}: {e}")
        
        return {
            'social_profiles': {},
            'discovery_timestamp': datetime.now().isoformat(),
            'extraction_method': 'failed'
        }
    
    def scrape_player_wikipedia(self, player_name: str, team: str) -> Dict:
        """
        Scrape Wikipedia page using Firecrawl's extract endpoint.
        
        Args:
            player_name: Name of the player
            team: Team name
            
        Returns:
            Dictionary with Wikipedia data
        """
        try:
            # Use extract endpoint for Wikipedia data
            search_urls = [
                f"https://www.google.com/search?q=\"{player_name}\"+NFL+{team}+wikipedia+biography"
            ]
            
            wikipedia_prompt = f"""
            Extract comprehensive biographical information for NFL player {player_name} from team {team}.
            
            Find and extract:
            1. Birth date and birth place
            2. College or university attended
            3. NFL draft information (year, round, pick)
            4. Career highlights and achievements
            5. Awards and honors received
            6. Pro Bowl selections (years and count)
            7. All-Pro selections (years and count)
            8. Hall of Fame status
            9. Career statistics and records
            
            Return structured biographical data.
            """
            
            result = self.extract_structured_data(
                urls=search_urls,
                prompt=wikipedia_prompt,
                schema=WikipediaData.model_json_schema()
            )
            
            if result.get("success") and result.get("data"):
                return {
                    'biographical_data': result["data"],
                    'wikipedia_url': self._find_wikipedia_url(player_name),
                    'scraped_at': datetime.now().isoformat(),
                    'extraction_method': 'firecrawl_extract'
                }
            
        except Exception as e:
            logger.error(f"Error scraping Wikipedia for {player_name}: {e}")
        
        return {
            'biographical_data': {},
            'wikipedia_url': None,
            'scraped_at': datetime.now().isoformat(),
            'extraction_method': 'failed'
        }
    
    def scrape_contract_data(self, player_name: str, team: str) -> Dict:
        """
        Scrape contract and financial data using Firecrawl's extract endpoint.
        
        Args:
            player_name: Name of the player
            team: Team name
            
        Returns:
            Dictionary with contract data
        """
        try:
            # Use extract endpoint for contract data
            search_urls = [
                f"https://www.google.com/search?q=\"{player_name}\"+NFL+{team}+contract+salary+spotrac"
            ]
            
            contract_prompt = f"""
            Extract comprehensive contract and salary information for NFL player {player_name} from team {team}.
            
            Find and extract:
            1. Current year salary
            2. Total contract value
            3. Contract duration in years
            4. Guaranteed money amount
            5. Signing bonus amount
            6. Career earnings total
            7. Cap hit information
            8. Dead money information
            
            Return structured financial data.
            """
            
            result = self.extract_structured_data(
                urls=search_urls,
                prompt=contract_prompt,
                schema=ContractData.model_json_schema()
            )
            
            if result.get("success") and result.get("data"):
                return {
                    'contract_data': result["data"],
                    'spotrac_url': self._find_spotrac_url(player_name),
                    'scraped_at': datetime.now().isoformat(),
                    'extraction_method': 'firecrawl_extract'
                }
            
        except Exception as e:
            logger.error(f"Error scraping contract data for {player_name}: {e}")
        
        return {
            'contract_data': {},
            'spotrac_url': None,
            'scraped_at': datetime.now().isoformat(),
            'extraction_method': 'failed'
        }
    
    def _find_wikipedia_url(self, player_name: str) -> str:
        """Find the most likely Wikipedia URL for the player."""
        return f"https://en.wikipedia.org/wiki/{player_name.replace(' ', '_')}"
    
    def _find_spotrac_url(self, player_name: str) -> str:
        """Find the most likely Spotrac URL for the player."""
        return f"https://www.spotrac.com/nfl/search/?search={player_name.replace(' ', '+')}"