"""
Free APIs Module - Alternative data collection without Firecrawl
Uses free APIs and libraries to reduce costs:
- Google Trends: pytrends (free, rate-limited)
- YouTube Stats: YouTube Data API v3 (free, 10,000 quota/day)
- Wikipedia: Wikipedia API (free)
- Social Media Stats: Direct scraping with requests (free)
"""

import os
import re
import time
import logging
import requests
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from urllib.parse import quote
from bs4 import BeautifulSoup

# Import collection utilities
try:
    from gravity.collection_utils import (
        retry_with_backoff, cached_social_lookup, parse_news_date
    )
except ImportError:
    # Fallback if collection_utils not available
    def retry_with_backoff(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def cached_social_lookup(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def parse_news_date(date_str):
        return None

logger = logging.getLogger(__name__)


# ============================================================================
# GOOGLE TRENDS (Free via pytrends)
# ============================================================================

class FreeTrendsCollector:
    """Collect Google Trends data using pytrends (free, no API key needed)"""
    
    def __init__(self):
        self.pytrends = None
        self._init_pytrends()
        self._last_request = 0
        self._min_delay = 2.0  # Rate limit: 2 seconds between requests
        self._cache = {}  # Simple in-memory cache
        self._cache_ttl = 24 * 3600  # 24 hours in seconds
    
    def _init_pytrends(self):
        """Initialize pytrends with retry logic"""
        try:
            from pytrends.request import TrendReq
            # Note: Removed retries/backoff_factor due to urllib3 compatibility issue
            # (method_whitelist deprecated in favor of allowed_methods)
            # We handle retries with our own @retry_with_backoff decorator
            self.pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 30))
            logger.info("✅ pytrends initialized successfully")
        except ImportError:
            logger.warning("⚠️ pytrends not installed. Run: pip install pytrends")
        except Exception as e:
            logger.warning(f"⚠️ pytrends initialization failed: {e}")
    
    def _rate_limit(self):
        """Respect rate limits"""
        elapsed = time.time() - self._last_request
        if elapsed < self._min_delay:
            time.sleep(self._min_delay - elapsed)
        self._last_request = time.time()
    
    def _get_cache(self, key: str, max_age_hours: int = 24) -> Optional[Dict]:
        """Get cached value if it exists and is not expired"""
        if key in self._cache:
            cached_data, timestamp = self._cache[key]
            age = time.time() - timestamp
            if age < (max_age_hours * 3600):
                logger.info(f"   ✅ Using cached trends data (age: {age/3600:.1f}h)")
                return cached_data
        return None
    
    def _set_cache(self, key: str, value: Dict):
        """Set cache value with timestamp"""
        self._cache[key] = (value, time.time())
    
    def get_trends_score(self, player_name: str, sport: str = "", timeframe: str = 'today 3-m') -> Dict:
        """
        Get Google Trends data for a player with caching and error handling.
        Returns interest over time (0-100 scale) and trend direction.
        
        Args:
            player_name: Player name to search
            sport: Sport context (e.g., "NFL", "NBA")
            timeframe: Google Trends timeframe (default: last 3 months)
        """
        result = {
            "trends_score": 0,
            "trends_momentum": "stable",
            "interest_over_time": [],
            "related_queries": [],
            "source": "pytrends"
        }
        
        if not self.pytrends:
            return result
        
        # Build search query
        search_term = f"{player_name} {sport}".strip()
        cache_key = f"trends_{search_term}_{timeframe}"
        
        # Check cache first (24 hour TTL)
        cached = self._get_cache(cache_key, max_age_hours=24)
        if cached:
            return cached
        
        try:
            # Add delay to avoid rate limits
            self._rate_limit()
            
            # Get interest over time with US-specific targeting for NFL
            self.pytrends.build_payload(
                kw_list=[search_term],
                timeframe=timeframe,
                geo='US'  # US-specific trends for better NFL data
            )
            
            interest_df = self.pytrends.interest_over_time()
            
            if not interest_df.empty and search_term in interest_df.columns:
                values = interest_df[search_term].tolist()
                
                if values:
                    # Current score (latest value)
                    result["trends_score"] = int(values[-1])
                    
                    # Store time series
                    result["interest_over_time"] = values[-30:]  # Last 30 data points
                    
                    # Calculate momentum (compare recent to older)
                    recent_avg = sum(values[-7:]) / 7 if len(values) >= 7 else values[-1]
                    older_avg = sum(values[-30:-7]) / 23 if len(values) >= 30 else sum(values[:-7]) / max(1, len(values) - 7)
                    
                    if recent_avg > older_avg * 1.2:
                        result["trends_momentum"] = "rising"
                    elif recent_avg < older_avg * 0.8:
                        result["trends_momentum"] = "falling"
                    else:
                        result["trends_momentum"] = "stable"
                    
                    logger.info(f"📈 Trends for {player_name}: Score={result['trends_score']}, Momentum={result['trends_momentum']}")
            
            # Get related queries (rate limited separately)
            try:
                self._rate_limit()
                related = self.pytrends.related_queries()
                if search_term in related and related[search_term].get('top') is not None:
                    top_queries = related[search_term]['top']
                    if top_queries is not None and not top_queries.empty:
                        result["related_queries"] = top_queries['query'].head(5).tolist()
            except Exception as e:
                logger.debug(f"Related queries failed: {e}")
            
            # Cache successful result
            self._set_cache(cache_key, result)
                
        except Exception as e:
            error_msg = str(e).lower()
            if 'quota' in error_msg or 'rate' in error_msg or '429' in error_msg:
                logger.warning(f"⚠️ Google Trends quota exceeded for {player_name}. Using cached or returning 0.")
            else:
                logger.warning(f"Google Trends failed for {player_name}: {e}")
        
        return result


# ============================================================================
# YOUTUBE DATA API (Free - 10,000 quota units/day)
# ============================================================================

class FreeYouTubeCollector:
    """Collect YouTube stats using the free YouTube Data API v3"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        self.youtube = None
        self._init_youtube()
    
    def _init_youtube(self):
        """Initialize YouTube API client"""
        if not self.api_key:
            logger.info("ℹ️ YouTube API key not set. YouTube stats will be limited.")
            return
        
        try:
            from googleapiclient.discovery import build
            self.youtube = build('youtube', 'v3', developerKey=self.api_key)
            logger.info("✅ YouTube API initialized successfully")
        except ImportError:
            logger.warning("⚠️ google-api-python-client not installed")
        except Exception as e:
            logger.warning(f"⚠️ YouTube API initialization failed: {e}")
    
    def search_channel(self, player_name: str, sport: str = "") -> Optional[str]:
        """Search for player's YouTube channel"""
        if not self.youtube:
            return None
        
        try:
            search_query = f"{player_name} {sport} official".strip()
            
            request = self.youtube.search().list(
                part="snippet",
                q=search_query,
                type="channel",
                maxResults=5
            )
            response = request.execute()
            
            # Filter for likely official channels
            for item in response.get("items", []):
                channel_title = item["snippet"]["title"].lower()
                player_parts = player_name.lower().split()
                
                # Check if channel name contains player's name
                if any(part in channel_title for part in player_parts):
                    return item["snippet"]["channelId"]
            
            return None
        except Exception as e:
            logger.debug(f"YouTube channel search failed: {e}")
            return None
    
    def get_channel_stats(self, channel_id: str) -> Dict:
        """Get statistics for a YouTube channel"""
        result = {
            "subscribers": 0,
            "total_views": 0,
            "video_count": 0,
            "channel_name": "",
            "source": "youtube_api"
        }
        
        if not self.youtube or not channel_id:
            return result
        
        try:
            request = self.youtube.channels().list(
                part="snippet,statistics",
                id=channel_id
            )
            response = request.execute()
            
            if response.get("items"):
                item = response["items"][0]
                stats = item.get("statistics", {})
                snippet = item.get("snippet", {})
                
                result["subscribers"] = int(stats.get("subscriberCount", 0))
                result["total_views"] = int(stats.get("viewCount", 0))
                result["video_count"] = int(stats.get("videoCount", 0))
                result["channel_name"] = snippet.get("title", "")
                
                logger.info(f"📺 YouTube: {result['channel_name']} - {result['subscribers']:,} subscribers")
        except Exception as e:
            logger.debug(f"YouTube stats failed: {e}")
        
        return result
    
    def get_player_youtube_stats(self, player_name: str, sport: str = "") -> Dict:
        """Full flow: search channel and get stats"""
        channel_id = self.search_channel(player_name, sport)
        if channel_id:
            return self.get_channel_stats(channel_id)
        return {"subscribers": 0, "total_views": 0, "video_count": 0, "source": "youtube_api"}


# ============================================================================
# WIKIPEDIA API (Free)
# ============================================================================

class FreeWikipediaCollector:
    """Collect Wikipedia page views using the free Wikimedia API"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'GravityScore/1.0 (Sports Analytics; contact@example.com)'
        })
    
    def get_page_views(self, player_name: str, days: int = 30) -> Dict:
        """
        Get Wikipedia page view statistics.
        Uses the Wikimedia REST API (free, no key needed).
        """
        result = {
            "page_views_30d": 0,
            "page_views_7d": 0,
            "daily_average": 0,
            "page_exists": False,
            "source": "wikipedia_api"
        }
        
        try:
            # Format page title (Wikipedia uses underscores)
            page_title = player_name.replace(" ", "_")
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Wikimedia REST API for pageviews
            url = (
                f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
                f"en.wikipedia/all-access/all-agents/{quote(page_title)}/daily/"
                f"{start_date.strftime('%Y%m%d')}/{end_date.strftime('%Y%m%d')}"
            )
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                
                if items:
                    result["page_exists"] = True
                    
                    # Calculate totals
                    all_views = [item.get("views", 0) for item in items]
                    result["page_views_30d"] = sum(all_views)
                    result["page_views_7d"] = sum(all_views[-7:]) if len(all_views) >= 7 else sum(all_views)
                    result["daily_average"] = round(result["page_views_30d"] / max(1, len(all_views)), 1)
                    
                    logger.info(f"📖 Wikipedia: {player_name} - {result['page_views_30d']:,} views (30d)")
            elif response.status_code == 404:
                logger.debug(f"Wikipedia page not found for {player_name}")
            else:
                logger.debug(f"Wikipedia API error: {response.status_code}")
                
        except Exception as e:
            logger.debug(f"Wikipedia collection failed for {player_name}: {e}")
        
        return result


# ============================================================================
# SOCIAL MEDIA STATS (Free via direct scraping)
# ============================================================================

class FreeSocialMediaCollector:
    """
    Collect social media statistics using direct requests.
    No API key required, but may be rate-limited.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, exceptions=(requests.RequestException,))
    @cached_social_lookup(ttl=86400)  # Cache for 24 hours
    def get_instagram_stats(self, username: str) -> Dict:
        """
        Get Instagram follower count.
        Note: Instagram heavily restricts scraping. This may not work consistently.
        """
        result = {"followers": 0, "posts": 0, "verified": False, "source": "instagram_scrape"}
        
        if not username:
            logger.debug("Instagram: No username provided")
            return result
        
        # Clean username
        username = username.lstrip("@").split("/")[-1].split("?")[0].strip()
        if not username:
            logger.debug("Instagram: Invalid username after cleaning")
            return result
        
        try:
            # Method 1: Try Instagram's public API endpoint
            url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15',
                'X-IG-App-ID': '936619743392459',  # Public web app ID
                'Accept': 'application/json',
            }
            
            response = self.session.get(url, headers=headers, timeout=15, allow_redirects=True)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    user_data = data.get("data", {}).get("user", {})
                    
                    result["followers"] = user_data.get("edge_followed_by", {}).get("count", 0)
                    result["posts"] = user_data.get("edge_owner_to_timeline_media", {}).get("count", 0)
                    result["verified"] = user_data.get("is_verified", False)
                    
                    if result["followers"]:
                        logger.info(f"📸 Instagram @{username}: {result['followers']:,} followers")
                        return result
                except:
                    pass
            
            # Method 2: Try scraping the public page HTML
            profile_url = f"https://www.instagram.com/{username}/"
            response = self.session.get(profile_url, timeout=15)
            
            if response.status_code == 200:
                # Look for JSON data in script tags
                html = response.text
                
                # Try to find window._sharedData or similar
                json_match = re.search(r'window\._sharedData\s*=\s*({.+?});', html)
                if json_match:
                    try:
                        import json
                        data = json.loads(json_match.group(1))
                        user_data = data.get("entry_data", {}).get("ProfilePage", [{}])[0].get("graphql", {}).get("user", {})
                        result["followers"] = user_data.get("edge_followed_by", {}).get("count", 0)
                        result["verified"] = user_data.get("is_verified", False)
                        if result["followers"]:
                            logger.info(f"📸 Instagram @{username}: {result['followers']:,} followers (HTML)")
                            return result
                    except:
                        pass
                
                # Fallback: regex search for follower count
                follower_patterns = [
                    r'"edge_followed_by":\s*{\s*"count":\s*(\d+)',
                    r'"follower_count":\s*(\d+)',
                    r'(\d+(?:,\d+)*)\s*followers',
                ]
                for pattern in follower_patterns:
                    match = re.search(pattern, html, re.I)
                    if match:
                        try:
                            count_str = match.group(1).replace(',', '')
                            result["followers"] = int(count_str)
                            if result["followers"] > 0:
                                logger.info(f"📸 Instagram @{username}: {result['followers']:,} followers (regex)")
                                return result
                        except:
                            continue
                            
        except Exception as e:
            logger.warning(f"Instagram scrape failed for {username}: {e}")
        
        return result
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, exceptions=(requests.RequestException,))
    @cached_social_lookup(ttl=86400)  # Cache for 24 hours
    def get_twitter_stats(self, username: str) -> Dict:
        """
        Get Twitter/X follower count.
        Note: Twitter/X has restricted API access. This uses public page scraping.
        """
        result = {"followers": 0, "verified": False, "source": "twitter_scrape"}
        
        if not username:
            logger.debug("Twitter: No username provided")
            return result
        
        # Clean username
        username = username.lstrip("@").split("/")[-1].split("?")[0].strip()
        if not username:
            logger.debug("Twitter: Invalid username after cleaning")
            return result
        
        try:
            # Try multiple methods
            # Method 1: Try nitter (Twitter frontend that's easier to scrape)
            nitter_urls = [
                f"https://nitter.net/{username}",
                f"https://nitter.it/{username}",
                f"https://nitter.pussthecat.org/{username}",
            ]
            
            for url in nitter_urls:
                try:
                    response = self.session.get(url, timeout=10, allow_redirects=True)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        # Look for follower count
                        follower_elem = soup.find('span', class_='profile-stat-num') or soup.find('span', string=re.compile(r'\d+.*followers', re.I))
                        if follower_elem:
                            text = follower_elem.get_text(strip=True)
                            # Extract number
                            match = re.search(r'([\d,]+)', text.replace(',', ''))
                            if match:
                                result["followers"] = int(match.group(1).replace(',', ''))
                                if result["followers"] > 0:
                                    logger.info(f"🐦 Twitter @{username}: {result['followers']:,} followers (nitter)")
                                    return result
                except:
                    continue
            
            # Method 2: Try Twitter's public page (may be blocked)
            twitter_url = f"https://twitter.com/{username}"
            try:
                response = self.session.get(twitter_url, timeout=10, allow_redirects=True)
                if response.status_code == 200:
                    html = response.text
                    # Look for follower count in JSON data
                    patterns = [
                        r'"followers_count":\s*(\d+)',
                        r'"follower_count":\s*(\d+)',
                        r'(\d+(?:,\d+)*)\s*Followers',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, html, re.I)
                        if match:
                            try:
                                count_str = match.group(1).replace(',', '')
                                result["followers"] = int(count_str)
                                if result["followers"] > 0:
                                    logger.info(f"🐦 Twitter @{username}: {result['followers']:,} followers")
                                    return result
                            except:
                                continue
            except:
                pass
                
            # Method 3: Try Twitter's syndication API (public, for widgets)
            try:
                url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    text = response.text
                    patterns = [
                        r'"followers_count":(\d+)',
                        r'(\d+(?:,\d+)*)\s*(?:Followers|followers)',
                        r'(\d+(?:\.\d+)?[KMB]?)\s*(?:Followers|followers)',
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, text)
                        if match:
                            count_str = match.group(1).replace(",", "")
                            
                            # Handle K/M/B suffixes
                            if count_str.endswith('K'):
                                result["followers"] = int(float(count_str[:-1]) * 1000)
                            elif count_str.endswith('M'):
                                result["followers"] = int(float(count_str[:-1]) * 1000000)
                            elif count_str.endswith('B'):
                                result["followers"] = int(float(count_str[:-1]) * 1000000000)
                            else:
                                result["followers"] = int(count_str)
                            
                            if result["followers"]:
                                logger.info(f"🐦 Twitter @{username}: {result['followers']:,} followers (syndication)")
                                return result
            except:
                pass
                
        except Exception as e:
            logger.warning(f"Twitter scrape failed for {username}: {e}")
        
        return result
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, exceptions=(requests.RequestException,))
    @cached_social_lookup(ttl=86400)  # Cache for 24 hours
    def get_tiktok_stats(self, username: str) -> Dict:
        """Get TikTok stats (limited due to restrictions)"""
        result = {"followers": 0, "likes": 0, "source": "tiktok_scrape"}
        
        if not username:
            logger.debug("TikTok: No username provided")
            return result
        
        username = username.lstrip("@").split("/")[-1].split("?")[0]
        
        try:
            # TikTok's public page - heavily restricted
            url = f"https://www.tiktok.com/@{username}"
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                text = response.text
                
                # Look for follower count in page data
                patterns = [
                    r'"followerCount":(\d+)',
                    r'"fans":(\d+)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, text)
                    if match:
                        result["followers"] = int(match.group(1))
                        if result["followers"]:
                            logger.info(f"🎵 TikTok @{username}: {result['followers']:,} followers")
                        break
        except Exception as e:
            logger.warning(f"TikTok scrape failed for {username}: {e}")
        
        return result


# ============================================================================
# DUCKDUCKGO SOCIAL HANDLE FINDER (Free - No API Key!)
# ============================================================================

class DuckDuckGoSocialFinder:
    """
    Find social media handles using multiple sources:
    1. Wikipedia (most reliable)
    2. DuckDuckGo search (fallback)
    Completely FREE - no API key required!
    Replaces Firecrawl for social handle discovery.
    """
    
    def __init__(self):
        self.ddgs = None
        self._init_ddgs()
        self._last_request = 0
        self._min_delay = 1.0  # Rate limit: 1 second between searches
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def _init_ddgs(self):
        """Initialize DuckDuckGo search"""
        try:
            # Try newer ddgs library first
            from ddgs import DDGS
            self.ddgs = DDGS()
            logger.info("✅ DuckDuckGo search initialized (FREE social handle finder)")
        except ImportError:
            try:
                # Fallback to older duckduckgo_search
                from duckduckgo_search import DDGS
                self.ddgs = DDGS()
                logger.info("✅ DuckDuckGo search initialized (FREE social handle finder)")
            except ImportError:
                logger.warning("⚠️ ddgs not installed. Run: pip install ddgs")
        except Exception as e:
            logger.warning(f"⚠️ DuckDuckGo initialization failed: {e}")
    
    def _rate_limit(self):
        """Respect rate limits"""
        elapsed = time.time() - self._last_request
        if elapsed < self._min_delay:
            time.sleep(self._min_delay - elapsed)
        self._last_request = time.time()
    
    def find_social_handle(self, player_name: str, platform: str) -> Optional[str]:
        """
        Find a player's social media handle using multiple sources.
        Priority: Wikipedia > DuckDuckGo
        
        Args:
            player_name: Full name of the player
            platform: 'instagram', 'twitter', 'tiktok', or 'youtube'
        
        Returns:
            Social media handle/username or None
        """
        platform = platform.lower()
        
        # Method 1: Try Wikipedia first (most reliable)
        wiki_handle = self._find_handle_from_wikipedia(player_name, platform)
        if wiki_handle:
            logger.info(f"📖 Wikipedia found {platform}: @{wiki_handle}")
            return wiki_handle
        
        # Method 2: Fallback to DuckDuckGo search
        if not self.ddgs:
            return None
        
        platform_domains = {
            'instagram': 'instagram.com',
            'twitter': 'twitter.com',
            'tiktok': 'tiktok.com',
            'youtube': 'youtube.com'
        }
        
        domain = platform_domains.get(platform)
        if not domain:
            return None
        
        # Try multiple search strategies
        queries = [
            f'{player_name} {domain}',  # Direct search with domain
            f'{player_name} official {platform}',  # Official account
        ]
        
        for query in queries:
            try:
                self._rate_limit()
                
                # Search DuckDuckGo
                results = list(self.ddgs.text(query, max_results=10))
                
                if not results:
                    continue
                
                # Extract handle from results
                for result in results:
                    url = result.get('href', '') or result.get('link', '')
                    title = result.get('title', '').lower()
                    
                    # Skip if URL doesn't contain the platform domain
                    if domain not in url.lower():
                        continue
                    
                    # Extract handle based on platform
                    handle = self._extract_handle_from_url(url, platform)
                    
                    if handle:
                        # Verify it's a personal account (not team/news)
                        if self._is_personal_account(handle, player_name, platform):
                            logger.info(f"🦆 DuckDuckGo found {platform}: @{handle}")
                            return handle
                
            except Exception as e:
                logger.debug(f"DuckDuckGo search failed for {player_name} {platform}: {e}")
                continue
        
        return None
    
    def _find_handle_from_wikipedia(self, player_name: str, platform: str) -> Optional[str]:
        """Extract social media handle from Wikipedia infobox"""
        try:
            # Format Wikipedia page title
            page_title = player_name.replace(" ", "_")
            wiki_url = f"https://en.wikipedia.org/wiki/{quote(page_title)}"
            
            response = self.session.get(wiki_url, timeout=10)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find infobox (usually has class 'infobox')
            infobox = soup.find('table', class_='infobox')
            if not infobox:
                return None
            
            # Look for social media links in infobox
            platform_keywords = {
                'instagram': ['instagram', 'ig'],
                'twitter': ['twitter', 'x.com'],
                'tiktok': ['tiktok'],
                'youtube': ['youtube', 'yt']
            }
            
            keywords = platform_keywords.get(platform.lower(), [])
            if not keywords:
                return None
            
            # Find all links in infobox
            links = infobox.find_all('a', href=True)
            for link in links:
                href = link.get('href', '').lower()
                text = link.get_text(strip=True).lower()
                
                # Check if link matches platform
                for keyword in keywords:
                    if keyword in href:
                        # Extract handle from URL
                        handle = self._extract_handle_from_url(href, platform)
                        if handle and self._is_personal_account(handle, player_name, platform):
                            return handle
            
            return None
            
        except Exception as e:
            logger.debug(f"Wikipedia handle extraction failed for {player_name} {platform}: {e}")
            return None
    
    def _find_handle_from_wikipedia(self, player_name: str, platform: str) -> Optional[str]:
        """Extract social media handle from Wikipedia infobox"""
        try:
            # Format Wikipedia page title
            page_title = player_name.replace(" ", "_")
            wiki_url = f"https://en.wikipedia.org/wiki/{quote(page_title)}"
            
            response = self.session.get(wiki_url, timeout=10)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find infobox (usually has class 'infobox')
            infobox = soup.find('table', class_='infobox')
            if not infobox:
                return None
            
            # Look for social media links in infobox
            platform_keywords = {
                'instagram': ['instagram', 'ig'],
                'twitter': ['twitter', 'x.com'],
                'tiktok': ['tiktok'],
                'youtube': ['youtube', 'yt']
            }
            
            keywords = platform_keywords.get(platform.lower(), [])
            if not keywords:
                return None
            
            # Find all links in infobox
            links = infobox.find_all('a', href=True)
            for link in links:
                href = link.get('href', '').lower()
                text = link.get_text(strip=True).lower()
                
                # Check if link matches platform
                for keyword in keywords:
                    if keyword in href:
                        # Extract handle from URL
                        handle = self._extract_handle_from_url(href, platform)
                        if handle and self._is_personal_account(handle, player_name, platform):
                            return handle
            
            return None
            
        except Exception as e:
            logger.debug(f"Wikipedia handle extraction failed for {player_name} {platform}: {e}")
            return None
    
    def _extract_handle_from_url(self, url: str, platform: str) -> Optional[str]:
        """Extract username/handle from social media URL"""
        if not url:
            return None
        
        url_lower = url.lower()
        
        patterns = {
            'instagram': [
                r'instagram\.com/([a-zA-Z0-9_\.]+)',
            ],
            'twitter': [
                r'twitter\.com/([a-zA-Z0-9_]+)',
                r'x\.com/([a-zA-Z0-9_]+)',
            ],
            'tiktok': [
                r'tiktok\.com/@([a-zA-Z0-9_\.]+)',
            ],
            'youtube': [
                r'youtube\.com/@([a-zA-Z0-9_\-]+)',
                r'youtube\.com/c/([a-zA-Z0-9_\-]+)',
                r'youtube\.com/user/([a-zA-Z0-9_\-]+)',
            ]
        }
        
        # Common non-profile pages to exclude
        excluded_handles = [
            'explore', 'p', 'reel', 'stories', 'hashtag', 'search', 'watch',
            'results', 'trending', 'home', 'settings', 'about', 'help',
            'privacy', 'terms', 'tag', 'discover', 'reels', 'tv', 'live',
            'playlist', 'channel', 'feed', 'shorts', 'video', 'embed',
            'share', 'login', 'signup', 'register', 'account', 'notifications'
        ]
        
        for pattern in patterns.get(platform, []):
            match = re.search(pattern, url_lower, re.IGNORECASE)
            if match:
                handle = match.group(1)
                # Filter out non-profile pages
                if handle.lower() not in excluded_handles and len(handle) > 2:
                    return handle
        
        return None
    
    def _is_personal_account(self, handle: str, player_name: str, platform: str) -> bool:
        """Check if handle is likely a personal account (not team/official)"""
        handle_lower = handle.lower()
        
        # Exclude obvious non-personal accounts
        excluded_patterns = [
            'nfl', 'nba', 'wnba', 'mlb', 'nhl', 'espn', 'foxsports', 'cbssports',
            'bleacher', 'sportscenter', 'theathleticnfl', 'pff', 'fantasy',
            'official', 'news', 'update', 'fan', 'fanpage', 'stats', 'highlights',
            'team', 'network', 'media', 'daily', 'nation', 'podcast'
        ]
        
        for pattern in excluded_patterns:
            if pattern in handle_lower:
                return False
        
        # Check if handle contains part of player name
        player_parts = player_name.lower().split()
        name_match = any(part in handle_lower for part in player_parts if len(part) > 2)
        
        # More lenient for short handles
        if len(handle) < 20 or name_match:
            return True
        
        return False
    
    def find_all_social_handles(self, player_name: str) -> Dict[str, Optional[str]]:
        """Find all social media handles for a player"""
        handles = {}
        
        for platform in ['instagram', 'twitter', 'tiktok', 'youtube']:
            handles[platform] = self.find_social_handle(player_name, platform)
        
        return handles


# ============================================================================
# UNIFIED FREE DATA COLLECTOR
# ============================================================================

class FreeDataCollector:
    """
    Unified collector that uses all free APIs.
    No Firecrawl needed for trends, YouTube, Wikipedia, social stats, or news.
    """
    
    def __init__(self, youtube_api_key: str = None):
        self.trends = FreeTrendsCollector()
        self.youtube = FreeYouTubeCollector(youtube_api_key)
        self.wikipedia = FreeWikipediaCollector()
        self.social = FreeSocialMediaCollector()
        self.ddg_finder = DuckDuckGoSocialFinder()  # FREE social handle finder!
        
        # Import NewsCollector here to avoid circular imports
        try:
            from gravity.news_collector import NewsCollector
            self.news = NewsCollector()
            logger.info("✅ NewsCollector initialized (Google News, DuckDuckGo, ESPN)")
        except Exception as e:
            logger.warning(f"⚠️  NewsCollector failed to initialize: {e}")
            self.news = None
    
    def collect_all_free_data(self, player_name: str, sport: str = "", 
                               social_handles: Dict = None) -> Dict:
        """
        Collect all available free data for a player.
        
        Args:
            player_name: Player's full name
            sport: Sport name (e.g., "NFL", "NBA")
            social_handles: Dict of social media handles {platform: handle}
        
        Returns:
            Dict with all collected data
        """
        result = {
            "trends": {},
            "youtube": {},
            "wikipedia": {},
            "instagram": {},
            "twitter": {},
            "tiktok": {},
            "collection_timestamp": datetime.now().isoformat()
        }
        
        # Google Trends (free)
        try:
            result["trends"] = self.trends.get_trends_score(player_name, sport)
        except Exception as e:
            logger.debug(f"Trends collection failed: {e}")
        
        # YouTube stats (free)
        try:
            result["youtube"] = self.youtube.get_player_youtube_stats(player_name, sport)
        except Exception as e:
            logger.debug(f"YouTube collection failed: {e}")
        
        # Wikipedia page views (free)
        try:
            result["wikipedia"] = self.wikipedia.get_page_views(player_name)
        except Exception as e:
            logger.debug(f"Wikipedia collection failed: {e}")
        
        # Social media stats (free, if handles provided)
        if social_handles:
            if social_handles.get("instagram"):
                try:
                    result["instagram"] = self.social.get_instagram_stats(social_handles["instagram"])
                except Exception as e:
                    logger.debug(f"Instagram collection failed: {e}")
            
            if social_handles.get("twitter"):
                try:
                    result["twitter"] = self.social.get_twitter_stats(social_handles["twitter"])
                except Exception as e:
                    logger.debug(f"Twitter collection failed: {e}")
            
            if social_handles.get("tiktok"):
                try:
                    result["tiktok"] = self.social.get_tiktok_stats(social_handles["tiktok"])
                except Exception as e:
                    logger.debug(f"TikTok collection failed: {e}")
        
        return result


# ============================================================================
# HELPER FUNCTION
# ============================================================================

def get_free_data_collector(youtube_api_key: str = None) -> FreeDataCollector:
    """Factory function to create a FreeDataCollector instance"""
    return FreeDataCollector(youtube_api_key)


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Test the collectors
    collector = FreeDataCollector()
    
    print("\n" + "="*60)
    print("Testing Free APIs")
    print("="*60)
    
    # Test with a well-known player
    test_player = "Patrick Mahomes"
    test_sport = "NFL"
    test_handles = {
        "instagram": "patrickmahomes",
        "twitter": "PatrickMahomes"
    }
    
    print(f"\nCollecting data for {test_player}...")
    
    data = collector.collect_all_free_data(test_player, test_sport, test_handles)
    
    print("\n📊 Results:")
    print(f"  Trends Score: {data['trends'].get('trends_score', 'N/A')}")
    print(f"  Trends Momentum: {data['trends'].get('trends_momentum', 'N/A')}")
    print(f"  Wikipedia Views (30d): {data['wikipedia'].get('page_views_30d', 'N/A')}")
    print(f"  YouTube Subscribers: {data['youtube'].get('subscribers', 'N/A')}")
    print(f"  Instagram Followers: {data['instagram'].get('followers', 'N/A')}")
    print(f"  Twitter Followers: {data['twitter'].get('followers', 'N/A')}")
    
    print("\n" + "="*60)

