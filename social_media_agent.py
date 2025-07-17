"""
Social Media Intelligence Agent for NFL Players
Automatically searches and extracts social media metrics from Twitter/X, Instagram, TikTok, and YouTube
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import random
from urllib.parse import quote_plus, urljoin

logger = logging.getLogger(__name__)

class SocialMediaAgent:
    """Intelligent agent for discovering and scraping social media profiles."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.delay_range = (1, 3)  # Random delay between requests
        
    def search_google_for_social_profiles(self, player_name: str, team: str = None) -> Dict[str, str]:
        """Search Google for player's social media profiles."""
        profiles = {
            'twitter': None,
            'instagram': None,
            'tiktok': None,
            'youtube': None
        }
        
        search_queries = [
            f'"{player_name}" twitter',
            f'"{player_name}" instagram',
            f'"{player_name}" tiktok',
            f'"{player_name}" youtube'
        ]
        
        if team:
            search_queries.extend([
                f'"{player_name}" {team} twitter',
                f'"{player_name}" {team} instagram',
                f'"{player_name}" {team} tiktok',
                f'"{player_name}" {team} youtube'
            ])
        
        for query in search_queries:
            try:
                platform = self._extract_platform_from_query(query)
                if profiles[platform]:  # Skip if already found
                    continue
                    
                url = self._search_social_profile(query, platform)
                if url:
                    profiles[platform] = url
                    logger.info(f"Found {platform} profile for {player_name}: {url}")
                
                # Random delay to avoid rate limiting
                time.sleep(random.uniform(*self.delay_range))
                
            except Exception as e:
                logger.error(f"Error searching for {query}: {e}")
                continue
        
        return profiles
    
    def _extract_platform_from_query(self, query: str) -> str:
        """Extract platform name from search query."""
        if 'twitter' in query.lower():
            return 'twitter'
        elif 'instagram' in query.lower():
            return 'instagram'
        elif 'tiktok' in query.lower():
            return 'tiktok'
        elif 'youtube' in query.lower():
            return 'youtube'
        return 'unknown'
    
    def _search_social_profile(self, query: str, platform: str) -> Optional[str]:
        """Search for social media profile using Google."""
        try:
            # Construct Google search URL
            search_url = f"https://www.google.com/search?q={quote_plus(query)}"
            
            response = self.session.get(search_url)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for social media links in search results
            platform_domains = {
                'twitter': ['twitter.com', 'x.com'],
                'instagram': ['instagram.com'],
                'tiktok': ['tiktok.com'],
                'youtube': ['youtube.com']
            }
            
            domains = platform_domains.get(platform, [])
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                if any(domain in href for domain in domains):
                    # Extract actual URL from Google redirect
                    url = self._extract_url_from_google_redirect(href)
                    if url and self._is_valid_profile_url(url, platform):
                        return url
            
            return None
            
        except Exception as e:
            logger.error(f"Error searching for {query}: {e}")
            return None
    
    def _extract_url_from_google_redirect(self, href: str) -> Optional[str]:
        """Extract actual URL from Google search result redirect."""
        try:
            if '/url?q=' in href:
                # Extract URL from Google redirect
                import urllib.parse
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                if 'q' in parsed:
                    return parsed['q'][0]
            elif href.startswith('http'):
                return href
            return None
        except:
            return None
    
    def _is_valid_profile_url(self, url: str, platform: str) -> bool:
        """Check if URL is a valid profile URL for the platform."""
        try:
            valid_patterns = {
                'twitter': [r'twitter\.com/[^/]+$', r'x\.com/[^/]+$'],
                'instagram': [r'instagram\.com/[^/]+/?$'],
                'tiktok': [r'tiktok\.com/@[^/]+/?$'],
                'youtube': [r'youtube\.com/c/[^/]+/?$', r'youtube\.com/channel/[^/]+/?$', r'youtube\.com/@[^/]+/?$']
            }
            
            patterns = valid_patterns.get(platform, [])
            return any(re.search(pattern, url) for pattern in patterns)
            
        except:
            return False
    
    def extract_twitter_metrics(self, twitter_url: str) -> Dict[str, int]:
        """Extract follower and following counts from Twitter/X profile."""
        try:
            response = self.session.get(twitter_url)
            if response.status_code != 200:
                return {'followers': 0, 'following': 0}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Twitter/X often loads content dynamically, so we look for meta tags or initial data
            metrics = {'followers': 0, 'following': 0}
            
            # Look for follower count in various formats
            follower_patterns = [
                r'(\d+(?:,\d+)*)\s*followers?',
                r'(\d+(?:\.\d+)?[KMB]?)\s*followers?',
                r'"followers_count":(\d+)',
                r'data-count="(\d+)".*followers'
            ]
            
            following_patterns = [
                r'(\d+(?:,\d+)*)\s*following',
                r'(\d+(?:\.\d+)?[KMB]?)\s*following',
                r'"friends_count":(\d+)',
                r'data-count="(\d+)".*following'
            ]
            
            text_content = soup.get_text().lower()
            
            for pattern in follower_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    metrics['followers'] = self._parse_number(match.group(1))
                    break
            
            for pattern in following_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    metrics['following'] = self._parse_number(match.group(1))
                    break
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error extracting Twitter metrics from {twitter_url}: {e}")
            return {'followers': 0, 'following': 0}
    
    def extract_instagram_metrics(self, instagram_url: str) -> Dict[str, int]:
        """Extract follower and following counts from Instagram profile."""
        try:
            response = self.session.get(instagram_url)
            if response.status_code != 200:
                return {'followers': 0, 'following': 0}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            metrics = {'followers': 0, 'following': 0}
            
            # Look for Instagram metrics in JSON data or meta tags
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if 'interactionStatistic' in data:
                        for stat in data['interactionStatistic']:
                            if 'FollowAction' in stat.get('@type', ''):
                                metrics['followers'] = int(stat.get('userInteractionCount', 0))
                except:
                    continue
            
            # Fallback: look for patterns in text
            if metrics['followers'] == 0:
                text_content = soup.get_text()
                
                follower_patterns = [
                    r'(\d+(?:,\d+)*)\s*followers?',
                    r'(\d+(?:\.\d+)?[KMB]?)\s*followers?'
                ]
                
                following_patterns = [
                    r'(\d+(?:,\d+)*)\s*following',
                    r'(\d+(?:\.\d+)?[KMB]?)\s*following'
                ]
                
                for pattern in follower_patterns:
                    match = re.search(pattern, text_content, re.IGNORECASE)
                    if match:
                        metrics['followers'] = self._parse_number(match.group(1))
                        break
                
                for pattern in following_patterns:
                    match = re.search(pattern, text_content, re.IGNORECASE)
                    if match:
                        metrics['following'] = self._parse_number(match.group(1))
                        break
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error extracting Instagram metrics from {instagram_url}: {e}")
            return {'followers': 0, 'following': 0}
    
    def extract_tiktok_metrics(self, tiktok_url: str) -> Dict[str, int]:
        """Extract follower and following counts from TikTok profile."""
        try:
            response = self.session.get(tiktok_url)
            if response.status_code != 200:
                return {'followers': 0, 'following': 0}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            metrics = {'followers': 0, 'following': 0}
            
            # Look for TikTok metrics in script tags or data attributes
            text_content = soup.get_text()
            
            follower_patterns = [
                r'(\d+(?:\.\d+)?[KMB]?)\s*followers?',
                r'(\d+(?:,\d+)*)\s*followers?'
            ]
            
            following_patterns = [
                r'(\d+(?:\.\d+)?[KMB]?)\s*following',
                r'(\d+(?:,\d+)*)\s*following'
            ]
            
            for pattern in follower_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    metrics['followers'] = self._parse_number(match.group(1))
                    break
            
            for pattern in following_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    metrics['following'] = self._parse_number(match.group(1))
                    break
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error extracting TikTok metrics from {tiktok_url}: {e}")
            return {'followers': 0, 'following': 0}
    
    def extract_youtube_metrics(self, youtube_url: str) -> Dict[str, int]:
        """Extract subscriber count from YouTube channel."""
        try:
            response = self.session.get(youtube_url)
            if response.status_code != 200:
                return {'subscribers': 0}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            metrics = {'subscribers': 0}
            
            # Look for subscriber count in various formats
            text_content = soup.get_text()
            
            subscriber_patterns = [
                r'(\d+(?:\.\d+)?[KMB]?)\s*subscribers?',
                r'(\d+(?:,\d+)*)\s*subscribers?'
            ]
            
            for pattern in subscriber_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    metrics['subscribers'] = self._parse_number(match.group(1))
                    break
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error extracting YouTube metrics from {youtube_url}: {e}")
            return {'subscribers': 0}
    
    def _parse_number(self, number_str: str) -> int:
        """Parse number string with K/M/B suffixes."""
        try:
            number_str = number_str.replace(',', '')
            
            if number_str.endswith('K'):
                return int(float(number_str[:-1]) * 1000)
            elif number_str.endswith('M'):
                return int(float(number_str[:-1]) * 1000000)
            elif number_str.endswith('B'):
                return int(float(number_str[:-1]) * 1000000000)
            else:
                return int(float(number_str))
                
        except:
            return 0
    
    def get_complete_social_media_profile(self, player_name: str, team: str = None) -> Dict:
        """Get complete social media profile for a player."""
        logger.info(f"Searching social media profiles for {player_name}")
        
        # Search for profile URLs
        profiles = self.search_google_for_social_profiles(player_name, team)
        
        # Extract metrics from each platform
        social_data = {
            'twitter_url': profiles.get('twitter'),
            'instagram_url': profiles.get('instagram'),
            'tiktok_url': profiles.get('tiktok'),
            'youtube_url': profiles.get('youtube'),
            'twitter_followers': 0,
            'twitter_following': 0,
            'instagram_followers': 0,
            'instagram_following': 0,
            'tiktok_followers': 0,
            'tiktok_following': 0,
            'youtube_subscribers': 0,
            'data_collection_date': datetime.now().isoformat(),
            'collection_method': 'automated_web_scraping'
        }
        
        # Extract Twitter metrics
        if profiles.get('twitter'):
            twitter_metrics = self.extract_twitter_metrics(profiles['twitter'])
            social_data['twitter_followers'] = twitter_metrics['followers']
            social_data['twitter_following'] = twitter_metrics['following']
            time.sleep(random.uniform(*self.delay_range))
        
        # Extract Instagram metrics
        if profiles.get('instagram'):
            instagram_metrics = self.extract_instagram_metrics(profiles['instagram'])
            social_data['instagram_followers'] = instagram_metrics['followers']
            social_data['instagram_following'] = instagram_metrics['following']
            time.sleep(random.uniform(*self.delay_range))
        
        # Extract TikTok metrics
        if profiles.get('tiktok'):
            tiktok_metrics = self.extract_tiktok_metrics(profiles['tiktok'])
            social_data['tiktok_followers'] = tiktok_metrics['followers']
            social_data['tiktok_following'] = tiktok_metrics['following']
            time.sleep(random.uniform(*self.delay_range))
        
        # Extract YouTube metrics
        if profiles.get('youtube'):
            youtube_metrics = self.extract_youtube_metrics(profiles['youtube'])
            social_data['youtube_subscribers'] = youtube_metrics['subscribers']
            time.sleep(random.uniform(*self.delay_range))
        
        return social_data

def test_social_media_agent():
    """Test the social media agent with a sample player."""
    agent = SocialMediaAgent()
    
    # Test with a well-known player
    test_player = "Brock Purdy"
    test_team = "49ers"
    
    print(f"Testing social media agent with {test_player} ({test_team})")
    
    try:
        social_data = agent.get_complete_social_media_profile(test_player, test_team)
        
        print("\nSocial Media Profile Results:")
        print(f"Twitter: {social_data['twitter_url']} ({social_data['twitter_followers']} followers)")
        print(f"Instagram: {social_data['instagram_url']} ({social_data['instagram_followers']} followers)")
        print(f"TikTok: {social_data['tiktok_url']} ({social_data['tiktok_followers']} followers)")
        print(f"YouTube: {social_data['youtube_url']} ({social_data['youtube_subscribers']} subscribers)")
        
        return social_data
        
    except Exception as e:
        print(f"Error testing social media agent: {e}")
        return None

if __name__ == "__main__":
    test_social_media_agent()