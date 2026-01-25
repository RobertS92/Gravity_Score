#!/usr/bin/env python3
"""
Enhanced Social Media Collector
================================
Multi-source social media handle collection with validation.

Sources (in priority order):
1. Wikidata (structured, verified)
2. DuckDuckGo (enhanced with validation)
3. Cross-reference (Twitter bio -> Instagram, etc.)
4. Direct platform searches

Author: Gravity Score Team
"""

import requests
import re
import logging
from typing import Dict, Optional, List
from bs4 import BeautifulSoup
import time

logger = logging.getLogger(__name__)


class EnhancedSocialCollector:
    """Enhanced social media handle collector with multi-source validation"""
    
    def __init__(self, session: requests.Session = None):
        self.session = session or requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Minimum follower thresholds by position (NFL)
        self.min_followers = {
            'QB': 50000,
            'WR': 20000,
            'TE': 10000,
            'RB': 20000,
            'DE': 5000,
            'LB': 5000,
            'DB': 5000,
            'CB': 5000,
            'S': 5000,
            'default': 5000
        }
    
    def collect_all_handles(self, player_name: str, position: str = None, team: str = None) -> Dict:
        """
        Collect all social media handles using multi-source strategy
        
        Returns:
            {
                'instagram': {'handle': '@username', 'followers': 123456, 'verified': True, 'source': 'wikidata'},
                'twitter': {...},
                'tiktok': {...},
                'youtube': {...}
            }
        """
        logger.info(f"🔍 Enhanced social collection for {player_name}")
        
        results = {}
        
        # Source 1: Wikidata (most reliable)
        wikidata_handles = self.get_wikidata_handles(player_name)
        if wikidata_handles:
            results = self._merge_handles(results, wikidata_handles, 'wikidata')
            logger.info(f"✅ Wikidata: Found {len(wikidata_handles)} handles")
        
        # Source 2: Enhanced DuckDuckGo searches
        if not self._all_found(results):
            ddg_handles = self.get_duckduckgo_handles_enhanced(player_name, position, team)
            if ddg_handles:
                results = self._merge_handles(results, ddg_handles, 'duckduckgo')
                logger.info(f"✅ DuckDuckGo: Found {len(ddg_handles)} handles")
        
        # Source 3: Cross-reference from found accounts
        if results.get('twitter') and not results.get('instagram'):
            twitter_handle = results['twitter'].get('handle', '').replace('@', '')
            if twitter_handle:
                cross_ref = self.get_handles_from_twitter_bio(twitter_handle)
                if cross_ref:
                    results = self._merge_handles(results, cross_ref, 'twitter_bio')
                    logger.info(f"✅ Cross-reference: Found from Twitter bio")
        
        # Validate all results
        validated_results = self.validate_all_handles(results, player_name, position)
        
        return validated_results
    
    def get_wikidata_handles(self, player_name: str) -> Dict:
        """
        Query Wikidata for verified social media handles
        Free SPARQL endpoint, no API key needed
        """
        try:
            endpoint = "https://query.wikidata.org/sparql"
            
            # SPARQL query for social media properties
            query = f"""
            SELECT ?instagram ?twitter ?youtube ?tiktok WHERE {{
              ?person rdfs:label "{player_name}"@en .
              ?person wdt:P106 wd:Q3665646 .
              OPTIONAL {{ ?person wdt:P2003 ?instagram }}
              OPTIONAL {{ ?person wdt:P2002 ?twitter }}
              OPTIONAL {{ ?person wdt:P2397 ?youtube }}
              OPTIONAL {{ ?person wdt:P7085 ?tiktok }}
            }}
            LIMIT 1
            """
            
            response = self.session.get(
                endpoint,
                params={'query': query, 'format': 'json'},
                headers={'User-Agent': 'GravityScoreBot/1.0'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                bindings = data.get('results', {}).get('bindings', [])
                
                if bindings:
                    result = bindings[0]
                    handles = {}
                    
                    if 'instagram' in result:
                        handles['instagram'] = {'handle': result['instagram']['value']}
                    if 'twitter' in result:
                        handles['twitter'] = {'handle': result['twitter']['value']}
                    if 'youtube' in result:
                        handles['youtube'] = {'handle': result['youtube']['value']}
                    if 'tiktok' in result:
                        handles['tiktok'] = {'handle': result['tiktok']['value']}
                    
                    return handles
        
        except Exception as e:
            logger.debug(f"Wikidata query failed for {player_name}: {e}")
        
        return {}
    
    def get_duckduckgo_handles_enhanced(self, player_name: str, position: str = None, team: str = None) -> Dict:
        """
        Enhanced DuckDuckGo search with platform-specific queries and validation
        """
        # Try importing DDGS - support both old and new package names
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                logger.warning("⚠️ Neither 'ddgs' nor 'duckduckgo_search' module found. Install with: pip install duckduckgo-search")
                return {}
        
        handles = {}
        
        # Platform-specific search strategies
        search_strategies = {
            'instagram': [
                f'{player_name} official instagram verified',
                f'{player_name} instagram NFL {team or ""}',
                f'site:instagram.com "{player_name}"'
            ],
            'twitter': [
                f'{player_name} official twitter verified',
                f'{player_name} twitter NFL {team or ""}',
                f'site:twitter.com "{player_name}" verified'
            ],
            'tiktok': [
                f'{player_name} official tiktok NFL',
                f'{player_name} tiktok verified',
                f'site:tiktok.com "@{player_name.replace(" ", "")}"'
            ],
            'youtube': [
                f'{player_name} official youtube channel NFL',
                f'{player_name} youtube verified',
                f'site:youtube.com "{player_name}"'
            ]
        }
        
        for platform, queries in search_strategies.items():
            for query in queries:
                try:
                    ddgs = DDGS()
                    results = list(ddgs.text(query, max_results=5))
                    
                    for result in results:
                        url = result.get('href', '')
                        handle = self._extract_handle_from_url(url, platform)
                        
                        if handle:
                            handles[platform] = {'handle': handle}
                            logger.debug(f"DDG found {platform}: @{handle}")
                            break  # Found one, move to next platform
                    
                    if platform in handles:
                        break  # Found valid handle, stop trying queries
                    
                    time.sleep(0.5)  # Rate limiting
                
                except Exception as e:
                    logger.debug(f"DDG search failed for {platform} ({query}): {e}")
                    continue
        
        return handles
    
    def get_handles_from_twitter_bio(self, twitter_handle: str) -> Dict:
        """
        Scrape Twitter bio for Instagram/TikTok/YouTube links
        """
        try:
            # Try to get Twitter profile page
            url = f"https://twitter.com/{twitter_handle}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                bio_text = soup.get_text()
                
                handles = {}
                
                # Look for Instagram mentions
                ig_patterns = [
                    r'instagram\.com/([a-zA-Z0-9_.]+)',
                    r'@([a-zA-Z0-9_.]+).*instagram',
                    r'IG:?\s*@?([a-zA-Z0-9_.]+)'
                ]
                for pattern in ig_patterns:
                    match = re.search(pattern, bio_text, re.IGNORECASE)
                    if match:
                        handles['instagram'] = {'handle': match.group(1)}
                        break
                
                # Look for TikTok mentions
                tiktok_patterns = [
                    r'tiktok\.com/@([a-zA-Z0-9_.]+)',
                    r'TikTok:?\s*@?([a-zA-Z0-9_.]+)'
                ]
                for pattern in tiktok_patterns:
                    match = re.search(pattern, bio_text, re.IGNORECASE)
                    if match:
                        handles['tiktok'] = {'handle': match.group(1)}
                        break
                
                # Look for YouTube mentions
                youtube_patterns = [
                    r'youtube\.com/c/([a-zA-Z0-9_-]+)',
                    r'youtube\.com/@([a-zA-Z0-9_-]+)',
                    r'YouTube:?\s*([a-zA-Z0-9_-]+)'
                ]
                for pattern in youtube_patterns:
                    match = re.search(pattern, bio_text, re.IGNORECASE)
                    if match:
                        handles['youtube'] = {'handle': match.group(1)}
                        break
                
                return handles
        
        except Exception as e:
            logger.debug(f"Failed to scrape Twitter bio for {twitter_handle}: {e}")
        
        return {}
    
    def validate_all_handles(self, handles: Dict, player_name: str, position: str = None) -> Dict:
        """
        Validate all collected handles with follower count checks
        """
        validated = {}
        threshold = self.min_followers.get(position, self.min_followers['default'])
        
        for platform, data in handles.items():
            handle = data.get('handle', '').replace('@', '')
            if not handle:
                continue
            
            # Get follower count if not already present
            if 'followers' not in data:
                followers = self._get_follower_count(handle, platform)
                data['followers'] = followers
            else:
                followers = data['followers']
            
            # Validate
            if followers and followers >= threshold:
                validated[platform] = data
                validated[platform]['validated'] = True
                logger.info(f"✅ Validated {platform} @{handle}: {followers:,} followers")
            elif followers and followers < threshold:
                logger.warning(f"⚠️  {platform} @{handle} has only {followers:,} followers (threshold: {threshold:,})")
                # Still include it but mark as unvalidated
                validated[platform] = data
                validated[platform]['validated'] = False
            else:
                # No follower count, include but mark as unvalidated
                validated[platform] = data
                validated[platform]['validated'] = False
        
        return validated
    
    def _get_follower_count(self, handle: str, platform: str) -> Optional[int]:
        """Get follower count for validation"""
        try:
            if platform == 'instagram':
                return self._get_instagram_followers(handle)
            elif platform == 'twitter':
                return self._get_twitter_followers(handle)
            elif platform == 'tiktok':
                return self._get_tiktok_followers(handle)
            elif platform == 'youtube':
                return self._get_youtube_subscribers(handle)
        except Exception as e:
            logger.debug(f"Failed to get {platform} followers for @{handle}: {e}")
        return None
    
    def _get_instagram_followers(self, username: str) -> Optional[int]:
        """Get Instagram follower count"""
        try:
            url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'X-IG-App-ID': '936619743392459'
            }
            response = self.session.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                followers = data.get('data', {}).get('user', {}).get('edge_followed_by', {}).get('count', 0)
                return int(followers) if followers else None
        except:
            pass
        return None
    
    def _get_twitter_followers(self, username: str) -> Optional[int]:
        """Get Twitter follower count"""
        try:
            # Try syndication API
            url = f"https://cdn.syndication.twimg.com/tweet-result?id={username}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                text = response.text
                # Look for follower count patterns
                patterns = [
                    r'"followers_count":(\d+)',
                    r'(\d+(?:\.\d+)?[KMB]?)\s*[Ff]ollowers'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, text)
                    if match:
                        count_str = match.group(1)
                        return self._parse_follower_count(count_str)
        except:
            pass
        return None
    
    def _get_tiktok_followers(self, username: str) -> Optional[int]:
        """Get TikTok follower count"""
        try:
            url = f"https://www.tiktok.com/@{username}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                text = response.text
                # Look for follower patterns
                patterns = [
                    r'"followerCount":(\d+)',
                    r'"fans":(\d+)',
                    r'(\d+(?:\.\d+)?[KMB]?)\s*[Ff]ollowers'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, text)
                    if match:
                        count_str = match.group(1)
                        return self._parse_follower_count(count_str)
        except:
            pass
        return None
    
    def _get_youtube_subscribers(self, channel_id: str) -> Optional[int]:
        """Get YouTube subscriber count"""
        try:
            url = f"https://www.youtube.com/@{channel_id}/about"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                text = response.text
                # Look for subscriber patterns
                patterns = [
                    r'"subscriberCountText".*?"simpleText":"([\d.]+[KMB]?)\s*subscribers"',
                    r'(\d+(?:\.\d+)?[KMB]?)\s*subscribers'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        count_str = match.group(1)
                        return self._parse_follower_count(count_str)
        except:
            pass
        return None
    
    def _parse_follower_count(self, count_str: str) -> int:
        """Parse follower count string (handles K, M, B suffixes)"""
        try:
            count_str = str(count_str).replace(',', '').strip()
            
            multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000}
            
            for suffix, multiplier in multipliers.items():
                if suffix in count_str.upper():
                    number = float(count_str.upper().replace(suffix, ''))
                    return int(number * multiplier)
            
            return int(float(count_str))
        except:
            return 0
    
    def _extract_handle_from_url(self, url: str, platform: str) -> Optional[str]:
        """Extract username/handle from social media URL"""
        if not url:
            return None
        
        patterns = {
            'instagram': r'instagram\.com/([a-zA-Z0-9_.]+)',
            'twitter': r'twitter\.com/([a-zA-Z0-9_]+)',
            'tiktok': r'tiktok\.com/@([a-zA-Z0-9_.]+)',
            'youtube': r'youtube\.com/(?:c/|@|channel/)([a-zA-Z0-9_-]+)'
        }
        
        pattern = patterns.get(platform)
        if pattern:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _merge_handles(self, existing: Dict, new: Dict, source: str) -> Dict:
        """Merge new handles into existing, prioritizing if not already found"""
        for platform, data in new.items():
            if platform not in existing:
                if isinstance(data, dict):
                    data['source'] = source
                    existing[platform] = data
                else:
                    existing[platform] = {'handle': data, 'source': source}
        return existing
    
    def _all_found(self, handles: Dict) -> bool:
        """Check if all major platforms found"""
        required = ['instagram', 'twitter', 'tiktok', 'youtube']
        return all(platform in handles for platform in required)

