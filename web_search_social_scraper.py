"""
Web Search Social Media Scraper
Uses web search to find social media profiles and scrapes follower counts
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
import random
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

class WebSearchSocialScraper:
    """Web scraper that searches for and extracts social media data."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.delay_range = (2, 5)  # Longer delays for respectful scraping
        
    def search_and_scrape_social_media(self, player_name: str, team: str = None) -> Dict:
        """Search for and scrape social media profiles for a player."""
        
        social_data = {
            'twitter_url': None,
            'instagram_url': None,
            'tiktok_url': None,
            'youtube_url': None,
            'twitter_followers': 0,
            'twitter_following': 0,
            'instagram_followers': 0,
            'instagram_following': 0,
            'tiktok_followers': 0,
            'tiktok_following': 0,
            'youtube_subscribers': 0,
            'search_timestamp': datetime.now().isoformat(),
            'data_sources': []
        }
        
        # Search for each platform
        platforms = ['twitter', 'instagram', 'tiktok', 'youtube']
        
        for platform in platforms:
            try:
                logger.info(f"Searching {platform} for {player_name}")
                
                # Search for profile URL
                profile_url = self.search_for_profile_url(player_name, platform, team)
                
                if profile_url:
                    social_data[f'{platform}_url'] = profile_url
                    logger.info(f"Found {platform} profile: {profile_url}")
                    
                    # Scrape metrics from the profile
                    metrics = self.scrape_profile_metrics(profile_url, platform)
                    
                    # Update social data with metrics
                    if platform == 'twitter':
                        social_data['twitter_followers'] = metrics.get('followers', 0)
                        social_data['twitter_following'] = metrics.get('following', 0)
                    elif platform == 'instagram':
                        social_data['instagram_followers'] = metrics.get('followers', 0)
                        social_data['instagram_following'] = metrics.get('following', 0)
                    elif platform == 'tiktok':
                        social_data['tiktok_followers'] = metrics.get('followers', 0)
                        social_data['tiktok_following'] = metrics.get('following', 0)
                    elif platform == 'youtube':
                        social_data['youtube_subscribers'] = metrics.get('subscribers', 0)
                    
                    social_data['data_sources'].append(f'{platform}_scraped')
                    
                    # Respectful delay between platforms
                    time.sleep(random.uniform(*self.delay_range))
                else:
                    logger.warning(f"No {platform} profile found for {player_name}")
                    
            except Exception as e:
                logger.error(f"Error searching {platform} for {player_name}: {e}")
                continue
        
        return social_data
    
    def search_for_profile_url(self, player_name: str, platform: str, team: str = None) -> Optional[str]:
        """Search for a player's profile URL on a specific platform."""
        try:
            # Construct search queries
            queries = [
                f'"{player_name}" {platform}',
                f'{player_name} {platform}',
            ]
            
            if team:
                queries.extend([
                    f'"{player_name}" {team} {platform}',
                    f'{player_name} {team} {platform}'
                ])
            
            # Try each query
            for query in queries:
                try:
                    # Use Google search manually instead of web_search
                    search_url = f"https://www.google.com/search?q={quote_plus(query)}"
                    
                    response = self.session.get(search_url)
                    if response.status_code == 200:
                        # Look for platform-specific URLs in the results
                        profile_url = self.extract_profile_url_from_search(response.text, platform)
                        
                        if profile_url:
                            return profile_url
                    
                    # Short delay between queries
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error in search query '{query}': {e}")
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error searching for {platform} profile: {e}")
            return None
    
    def extract_profile_url_from_search(self, search_results: str, platform: str) -> Optional[str]:
        """Extract profile URL from search results."""
        try:
            # Platform-specific URL patterns
            url_patterns = {
                'twitter': [
                    r'https?://(?:www\.)?(?:twitter\.com|x\.com)/[^/\s]+',
                    r'twitter\.com/[^/\s]+',
                    r'x\.com/[^/\s]+'
                ],
                'instagram': [
                    r'https?://(?:www\.)?instagram\.com/[^/\s]+',
                    r'instagram\.com/[^/\s]+'
                ],
                'tiktok': [
                    r'https?://(?:www\.)?tiktok\.com/@[^/\s]+',
                    r'tiktok\.com/@[^/\s]+'
                ],
                'youtube': [
                    r'https?://(?:www\.)?youtube\.com/(?:c/|channel/|@)[^/\s]+',
                    r'youtube\.com/(?:c/|channel/|@)[^/\s]+'
                ]
            }
            
            patterns = url_patterns.get(platform, [])
            
            for pattern in patterns:
                matches = re.findall(pattern, search_results, re.IGNORECASE)
                
                if matches:
                    # Return the first valid match
                    for match in matches:
                        # Clean up the URL
                        url = match.strip()
                        
                        # Ensure it starts with https://
                        if not url.startswith('http'):
                            url = 'https://' + url
                        
                        # Validate it's a profile URL (not a post or other page)
                        if self.is_valid_profile_url(url, platform):
                            return url
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting profile URL from search results: {e}")
            return None
    
    def is_valid_profile_url(self, url: str, platform: str) -> bool:
        """Check if URL is a valid profile URL."""
        try:
            # Remove query parameters and fragments
            base_url = url.split('?')[0].split('#')[0]
            
            # Platform-specific validation
            if platform == 'twitter':
                # Should be twitter.com/username or x.com/username
                return bool(re.match(r'https?://(?:www\.)?(?:twitter\.com|x\.com)/[^/]+/?$', base_url))
            
            elif platform == 'instagram':
                # Should be instagram.com/username/
                return bool(re.match(r'https?://(?:www\.)?instagram\.com/[^/]+/?$', base_url))
            
            elif platform == 'tiktok':
                # Should be tiktok.com/@username
                return bool(re.match(r'https?://(?:www\.)?tiktok\.com/@[^/]+/?$', base_url))
            
            elif platform == 'youtube':
                # Should be youtube.com/c/channel or youtube.com/@channel
                return bool(re.match(r'https?://(?:www\.)?youtube\.com/(?:c/|channel/|@)[^/]+/?$', base_url))
            
            return False
            
        except Exception as e:
            logger.error(f"Error validating profile URL: {e}")
            return False
    
    def scrape_profile_metrics(self, profile_url: str, platform: str) -> Dict:
        """Scrape metrics from a social media profile."""
        try:
            response = self.session.get(profile_url, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch {profile_url}: {response.status_code}")
                return {}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Platform-specific metric extraction
            if platform == 'twitter':
                return self.extract_twitter_metrics(soup, response.text)
            elif platform == 'instagram':
                return self.extract_instagram_metrics(soup, response.text)
            elif platform == 'tiktok':
                return self.extract_tiktok_metrics(soup, response.text)
            elif platform == 'youtube':
                return self.extract_youtube_metrics(soup, response.text)
            
            return {}
            
        except Exception as e:
            logger.error(f"Error scraping metrics from {profile_url}: {e}")
            return {}
    
    def extract_twitter_metrics(self, soup: BeautifulSoup, html_text: str) -> Dict:
        """Extract Twitter/X metrics."""
        metrics = {'followers': 0, 'following': 0}
        
        try:
            # Look for follower count in various formats
            text_content = soup.get_text().lower()
            
            # Pattern matching for followers
            follower_patterns = [
                r'(\d+(?:,\d+)*)\s*followers?',
                r'(\d+(?:\.\d+)?[kmb]?)\s*followers?',
                r'"followers_count":(\d+)',
                r'data-count="(\d+)".*followers'
            ]
            
            following_patterns = [
                r'(\d+(?:,\d+)*)\s*following',
                r'(\d+(?:\.\d+)?[kmb]?)\s*following',
                r'"friends_count":(\d+)'
            ]
            
            # Try to find follower count
            for pattern in follower_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    metrics['followers'] = self.parse_social_number(match.group(1))
                    break
            
            # Try to find following count
            for pattern in following_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    metrics['following'] = self.parse_social_number(match.group(1))
                    break
            
            # Also check JSON data in script tags
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    try:
                        if '"followers_count"' in script.string:
                            follower_match = re.search(r'"followers_count":(\d+)', script.string)
                            if follower_match:
                                metrics['followers'] = int(follower_match.group(1))
                        
                        if '"friends_count"' in script.string:
                            following_match = re.search(r'"friends_count":(\d+)', script.string)
                            if following_match:
                                metrics['following'] = int(following_match.group(1))
                    except:
                        continue
            
        except Exception as e:
            logger.error(f"Error extracting Twitter metrics: {e}")
        
        return metrics
    
    def extract_instagram_metrics(self, soup: BeautifulSoup, html_text: str) -> Dict:
        """Extract Instagram metrics."""
        metrics = {'followers': 0, 'following': 0}
        
        try:
            # Look for Instagram-specific patterns
            text_content = soup.get_text()
            
            # Instagram follower patterns
            follower_patterns = [
                r'(\d+(?:,\d+)*)\s*followers?',
                r'(\d+(?:\.\d+)?[kmb]?)\s*followers?'
            ]
            
            following_patterns = [
                r'(\d+(?:,\d+)*)\s*following',
                r'(\d+(?:\.\d+)?[kmb]?)\s*following'
            ]
            
            for pattern in follower_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    metrics['followers'] = self.parse_social_number(match.group(1))
                    break
            
            for pattern in following_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    metrics['following'] = self.parse_social_number(match.group(1))
                    break
            
            # Check for JSON-LD data
            json_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    if 'interactionStatistic' in data:
                        for stat in data['interactionStatistic']:
                            if 'FollowAction' in stat.get('@type', ''):
                                metrics['followers'] = int(stat.get('userInteractionCount', 0))
                except:
                    continue
            
        except Exception as e:
            logger.error(f"Error extracting Instagram metrics: {e}")
        
        return metrics
    
    def extract_tiktok_metrics(self, soup: BeautifulSoup, html_text: str) -> Dict:
        """Extract TikTok metrics."""
        metrics = {'followers': 0, 'following': 0}
        
        try:
            text_content = soup.get_text()
            
            # TikTok follower patterns
            follower_patterns = [
                r'(\d+(?:\.\d+)?[kmb]?)\s*followers?',
                r'(\d+(?:,\d+)*)\s*followers?'
            ]
            
            following_patterns = [
                r'(\d+(?:\.\d+)?[kmb]?)\s*following',
                r'(\d+(?:,\d+)*)\s*following'
            ]
            
            for pattern in follower_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    metrics['followers'] = self.parse_social_number(match.group(1))
                    break
            
            for pattern in following_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    metrics['following'] = self.parse_social_number(match.group(1))
                    break
            
        except Exception as e:
            logger.error(f"Error extracting TikTok metrics: {e}")
        
        return metrics
    
    def extract_youtube_metrics(self, soup: BeautifulSoup, html_text: str) -> Dict:
        """Extract YouTube metrics."""
        metrics = {'subscribers': 0}
        
        try:
            text_content = soup.get_text()
            
            # YouTube subscriber patterns
            subscriber_patterns = [
                r'(\d+(?:\.\d+)?[kmb]?)\s*subscribers?',
                r'(\d+(?:,\d+)*)\s*subscribers?'
            ]
            
            for pattern in subscriber_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    metrics['subscribers'] = self.parse_social_number(match.group(1))
                    break
            
        except Exception as e:
            logger.error(f"Error extracting YouTube metrics: {e}")
        
        return metrics
    
    def parse_social_number(self, number_str: str) -> int:
        """Parse social media number format (e.g., 1.5M, 50K)."""
        try:
            number_str = number_str.replace(',', '').strip().lower()
            
            if number_str.endswith('k'):
                return int(float(number_str[:-1]) * 1000)
            elif number_str.endswith('m'):
                return int(float(number_str[:-1]) * 1000000)
            elif number_str.endswith('b'):
                return int(float(number_str[:-1]) * 1000000000)
            else:
                return int(float(number_str))
                
        except:
            return 0

def test_web_search_social_scraper():
    """Test the web search social scraper."""
    scraper = WebSearchSocialScraper()
    
    # Test with a well-known player
    test_player = "Brock Purdy"
    test_team = "49ers"
    
    print(f"Testing web search social scraper with {test_player} ({test_team})")
    
    try:
        social_data = scraper.search_and_scrape_social_media(test_player, test_team)
        
        print(f"\nSocial Media Data for {test_player}:")
        print(f"Twitter: {social_data['twitter_url']} ({social_data['twitter_followers']} followers)")
        print(f"Instagram: {social_data['instagram_url']} ({social_data['instagram_followers']} followers)")
        print(f"TikTok: {social_data['tiktok_url']} ({social_data['tiktok_followers']} followers)")
        print(f"YouTube: {social_data['youtube_url']} ({social_data['youtube_subscribers']} subscribers)")
        
        print(f"\nData Sources: {social_data['data_sources']}")
        
        return social_data
        
    except Exception as e:
        print(f"Error testing web search social scraper: {e}")
        return None

if __name__ == "__main__":
    test_web_search_social_scraper()