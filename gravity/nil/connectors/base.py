"""
Base NIL Connector Framework
Abstract base class for all NIL data connectors
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import requests
from bs4 import BeautifulSoup
import time
import asyncio
import httpx

logger = logging.getLogger(__name__)


class BaseNILConnector(ABC):
    """
    Abstract base class for NIL data connectors
    All source connectors should inherit from this class
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize connector
        
        Args:
            api_key: Optional API key for the source
        """
        self.api_key = api_key
        # Keep existing sync session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        # Add async client (lazy init)
        self._async_client: Optional[httpx.AsyncClient] = None
        self.last_request_time = None
        self.rate_limit_delay = 1.0  # seconds between requests
    
    @abstractmethod
    def fetch_raw(
        self,
        athlete_name: str,
        school: Optional[str] = None,
        sport: Optional[str] = None,
        **filters
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch raw data from the source
        
        Args:
            athlete_name: Name of athlete
            school: School/college name
            sport: Sport type (football, basketball, etc.)
            **filters: Additional source-specific filters
        
        Returns:
            Raw response data as dict or None if not found
        """
        pass
    
    @abstractmethod
    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize raw data into canonical schema
        
        Args:
            raw_data: Raw response from fetch_raw()
        
        Returns:
            Normalized data dict with standard fields
        """
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """Return the source name (e.g., 'on3', 'opendorse')"""
        pass
    
    @abstractmethod
    def get_source_reliability_weight(self) -> float:
        """
        Return reliability weight for this source
        Should be value between 0 and 1
        """
        pass
    
    # ========================================================================
    # ASYNC INFRASTRUCTURE
    # ========================================================================
    
    async def get_async_client(self) -> httpx.AsyncClient:
        """
        Get or create async HTTP client
        
        Returns:
            Async httpx client
        """
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=15.0,
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'},
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5
                )
            )
        return self._async_client
    
    async def close_async_client(self):
        """Close async client if it exists"""
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None
    
    async def fetch_urls_parallel(
        self,
        urls: List[str],
        rate_limit_delay: Optional[float] = None
    ) -> List[Optional[httpx.Response]]:
        """
        Fetch multiple URLs in parallel with rate limiting
        
        Args:
            urls: List of URLs to fetch
            rate_limit_delay: Optional custom rate limit delay
        
        Returns:
            List of Response objects (None for failed requests)
        """
        delay = rate_limit_delay or self.rate_limit_delay
        
        async def fetch_with_delay(url: str, idx: int):
            await asyncio.sleep(idx * delay)  # Stagger requests
            try:
                client = await self.get_async_client()
                response = await client.get(url, timeout=15.0)
                if response.status_code == 200:
                    return response
                else:
                    logger.warning(f"{self.get_source_name()} returned {response.status_code} for {url}")
                    return None
            except Exception as e:
                logger.error(f"Failed to fetch {url}: {e}")
                return None
        
        tasks = [fetch_with_delay(url, i) for i, url in enumerate(urls)]
        return await asyncio.gather(*tasks)
    
    def extract_with_ai_fallback(
        self,
        text: str,
        extraction_type: str,
        athlete_name: str,
        use_ai: bool = True
    ) -> Optional[Any]:
        """
        Extract structured data with AI fallback for high-value fields
        
        Args:
            text: Text to extract from
            extraction_type: One of 'nil_deals', 'brand_partnerships', 
                           'contract_details', 'draft_info', 'dates'
            athlete_name: Athlete name for context
            use_ai: Whether to use AI fallback
        
        Returns:
            Extracted data or None
        """
        # Try regex first (fast, free)
        regex_result = self._extract_by_type(text, extraction_type)
        
        if regex_result or not use_ai:
            return regex_result
        
        # AI fallback for high-value data only
        high_value_types = ['nil_deals', 'brand_partnerships', 'contract_details', 'draft_info', 'dates']
        if extraction_type in high_value_types:
            return self._ai_extract(text, extraction_type, athlete_name)
        
        return None
    
    def _extract_by_type(self, text: str, extraction_type: str) -> Optional[Any]:
        """
        Dispatch to appropriate regex extraction method
        Subclasses should override this to add custom extraction
        
        Args:
            text: Text to extract from
            extraction_type: Type of extraction
        
        Returns:
            Extracted data or None
        """
        # Default implementation - subclasses override
        return None
    
    def _ai_extract(self, text: str, extraction_type: str, athlete_name: str) -> Optional[Any]:
        """
        Use AI to extract structured data
        
        Args:
            text: Text to extract from
            extraction_type: Type of extraction
            athlete_name: Athlete name for context
        
        Returns:
            AI-extracted data or None
        """
        try:
            from gravity.ai.extractor import AIExtractor
            
            extractor = AIExtractor()
            return extractor.extract(
                text=text[:2000],  # Limit to reduce tokens
                extraction_type=extraction_type,
                context={'athlete_name': athlete_name}
            )
        except Exception as e:
            logger.error(f"AI extraction failed for {extraction_type}: {e}")
            return None
    
    # ========================================================================
    # COMMON UTILITY METHODS
    # ========================================================================
    
    def rate_limit(self):
        """Apply rate limiting between requests"""
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit_delay:
                time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()
    
    def fetch_url(
        self,
        url: str,
        method: str = 'GET',
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        timeout: int = 15,
        retries: int = 3
    ) -> Optional[requests.Response]:
        """
        Fetch URL with retry logic and rate limiting
        
        Args:
            url: URL to fetch
            method: HTTP method (GET, POST, etc.)
            params: Query parameters
            data: POST data
            timeout: Request timeout in seconds
            retries: Number of retry attempts
        
        Returns:
            Response object or None if failed
        """
        self.rate_limit()
        
        for attempt in range(retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:  # Rate limited
                    wait_time = min(2 ** attempt, 30)
                    logger.warning(f"{self.get_source_name()} rate limited, waiting {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"{self.get_source_name()} returned {response.status_code}")
                    
            except requests.RequestException as e:
                logger.debug(f"{self.get_source_name()} request failed (attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    time.sleep(1)
        
        return None
    
    def parse_html(self, html_content: str) -> BeautifulSoup:
        """
        Parse HTML content
        
        Args:
            html_content: HTML string
        
        Returns:
            BeautifulSoup object
        """
        return BeautifulSoup(html_content, 'html.parser')
    
    def extract_json_from_response(self, response: requests.Response) -> Optional[Dict]:
        """
        Safely extract JSON from response
        
        Args:
            response: Response object
        
        Returns:
            Parsed JSON dict or None
        """
        try:
            return response.json()
        except Exception as e:
            logger.debug(f"Failed to parse JSON from {self.get_source_name()}: {e}")
            return None
    
    def collect(
        self,
        athlete_name: str,
        school: Optional[str] = None,
        sport: Optional[str] = None,
        **filters
    ) -> Optional[Dict[str, Any]]:
        """
        High-level method to fetch and normalize data
        
        Args:
            athlete_name: Name of athlete
            school: School/college name
            sport: Sport type
            **filters: Additional filters
        
        Returns:
            Normalized data with metadata
        """
        try:
            logger.info(f"Collecting from {self.get_source_name()}: {athlete_name}")
            
            # Fetch raw data
            raw_data = self.fetch_raw(athlete_name, school, sport, **filters)
            
            if not raw_data:
                logger.debug(f"{self.get_source_name()}: No data found for {athlete_name}")
                return None
            
            # Normalize data
            normalized_data = self.normalize(raw_data)
            
            # Add metadata
            normalized_data['_metadata'] = {
                'source': self.get_source_name(),
                'source_reliability': self.get_source_reliability_weight(),
                'fetched_at': datetime.utcnow().isoformat(),
                'athlete_name': athlete_name,
                'school': school,
                'sport': sport
            }
            
            logger.info(f"{self.get_source_name()}: Successfully collected data for {athlete_name}")
            return normalized_data
            
        except Exception as e:
            logger.error(f"{self.get_source_name()} collection failed for {athlete_name}: {e}")
            return None
    
    # ========================================================================
    # DATA EXTRACTION HELPERS
    # ========================================================================
    
    def parse_currency_value(self, value_str: str) -> Optional[float]:
        """
        Parse currency string to float
        
        Examples:
            "$1.2M" -> 1200000
            "$850K" -> 850000
            "$1,200,000" -> 1200000
        
        Args:
            value_str: Currency string
        
        Returns:
            Numeric value or None
        """
        if not value_str:
            return None
        
        import re
        
        # Remove $ and commas
        cleaned = value_str.replace('$', '').replace(',', '').strip()
        
        # Check for K/M/B multipliers
        match = re.search(r'([\d.]+)\s*([KMB])?', cleaned, re.IGNORECASE)
        if not match:
            return None
        
        value = float(match.group(1))
        multiplier = match.group(2)
        
        if multiplier:
            mult_upper = multiplier.upper()
            if mult_upper == 'K':
                value *= 1_000
            elif mult_upper == 'M':
                value *= 1_000_000
            elif mult_upper == 'B':
                value *= 1_000_000_000
        
        return value
    
    def extract_ranking(self, text: str) -> Optional[int]:
        """
        Extract ranking number from text
        
        Examples:
            "#42" -> 42
            "Ranked 15th" -> 15
        
        Args:
            text: Text containing ranking
        
        Returns:
            Ranking number or None
        """
        if not text:
            return None
        
        import re
        
        # Try to find "#42" or "Ranked 15"
        match = re.search(r'#?(\d+)(?:st|nd|rd|th)?', text)
        if match:
            return int(match.group(1))
        
        return None
    
    def clean_athlete_name(self, name: str) -> str:
        """
        Clean and normalize athlete name
        
        Args:
            name: Raw name string
        
        Returns:
            Cleaned name
        """
        if not name:
            return ""
        
        # Remove extra whitespace
        name = ' '.join(name.split())
        
        # Remove common prefixes/suffixes
        name = name.replace('Jr.', '').replace('Sr.', '').replace('III', '').replace('II', '')
        
        # Trim
        return name.strip()


class ConnectorError(Exception):
    """Custom exception for connector errors"""
    pass


class RateLimitError(ConnectorError):
    """Raised when rate limit is exceeded"""
    pass


class DataNotFoundError(ConnectorError):
    """Raised when athlete data is not found"""
    pass


class NormalizationError(ConnectorError):
    """Raised when data normalization fails"""
    pass
