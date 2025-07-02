"""Social media data extraction for NFL players."""

import re
import logging
import requests
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup

from ..core.exceptions import ExtractionError
from ..core.utils import get_user_agent, polite_delay, extract_social_metrics
from ..llm.adapter import LLMAdapter


class SocialMediaExtractor:
    """Extractor for social media metrics and profiles."""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("nfl_gravity.extractors.social_media")
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': get_user_agent()})
        
        # Initialize LLM adapter if enabled
        if config.enable_llm:
            self.llm_adapter = LLMAdapter(config)
        else:
            self.llm_adapter = None
    
    def discover_social_profiles(self, player_name: str, team: str = None) -> Dict[str, Any]:
        """
        Discover social media profiles for a player.
        
        Args:
            player_name: Name of the player
            team: Optional team name for disambiguation
            
        Returns:
            Dictionary containing discovered social media profiles
        """
        try:
            social_data = {}
            
            # Search for social media mentions using Google search
            search_results = self._search_social_mentions(player_name, team)
            
            # Extract social media handles using regex
            regex_results = self._extract_handles_regex(search_results)
            social_data.update(regex_results)
            
            # Use LLM as fallback for better extraction if enabled
            if self.llm_adapter and search_results:
                llm_results = self._extract_handles_llm(search_results, player_name, team)
                # LLM results override regex results if found
                for key, value in llm_results.items():
                    if value:
                        social_data[key] = value
            
            # Extract metrics for discovered profiles
            if social_data.get('twitter_handle'):
                twitter_metrics = self._extract_twitter_metrics(social_data['twitter_handle'])
                social_data.update(twitter_metrics)
            
            if social_data.get('instagram_handle'):
                instagram_metrics = self._extract_instagram_metrics(social_data['instagram_handle'])
                social_data.update(instagram_metrics)
            
            social_data['data_source'] = 'social_media_extraction'
            self.logger.info(f"Discovered social profiles for {player_name}")
            
            return social_data
            
        except Exception as e:
            self.logger.error(f"Error discovering social profiles for {player_name}: {e}")
            return {'data_source': 'social_media_extraction'}
    
    def _search_social_mentions(self, player_name: str, team: str = None) -> str:
        """
        Search for social media mentions of the player.
        
        Args:
            player_name: Name of the player
            team: Optional team name
            
        Returns:
            Combined text from search results
        """
        search_text = ""
        
        try:
            # Search query for social media profiles
            query = f'"{player_name}" NFL social media Twitter Instagram'
            if team:
                query += f' {team}'
            
            # Use a search engine that doesn't require API keys
            # This is a simplified implementation - in production you might want to use
            # proper search APIs or scrape search results more carefully
            
            search_urls = [
                f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}"
            ]
            
            for url in search_urls:
                try:
                    polite_delay(self.config.request_delay_min, self.config.request_delay_max)
                    
                    response = self.session.get(url, timeout=self.config.request_timeout)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Extract text from search results
                    for result in soup.find_all('a', class_='result__url'):
                        if result.get_text():
                            search_text += result.get_text() + " "
                    
                    # Also check result snippets
                    for snippet in soup.find_all('a', class_='result__snippet'):
                        if snippet.get_text():
                            search_text += snippet.get_text() + " "
                            
                except Exception as e:
                    self.logger.warning(f"Error searching {url}: {e}")
                    continue
            
            return search_text
            
        except Exception as e:
            self.logger.error(f"Error searching for social mentions: {e}")
            return ""
    
    def _extract_handles_regex(self, text: str) -> Dict[str, Any]:
        """
        Extract social media handles using regex patterns.
        
        Args:
            text: Text to search for handles
            
        Returns:
            Dictionary with discovered handles
        """
        handles = {}
        
        # Twitter handle patterns
        twitter_patterns = [
            r'@([a-zA-Z0-9_]{1,15})',
            r'twitter\.com/([a-zA-Z0-9_]{1,15})',
            r'x\.com/([a-zA-Z0-9_]{1,15})'
        ]
        
        for pattern in twitter_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Take the first valid-looking handle
                for match in matches:
                    if len(match) > 2 and not match.isdigit():
                        handles['twitter_handle'] = match
                        break
                if 'twitter_handle' in handles:
                    break
        
        # Instagram handle patterns
        instagram_patterns = [
            r'instagram\.com/([a-zA-Z0-9_.]{1,30})',
            r'@([a-zA-Z0-9_.]{1,30}).*instagram'
        ]
        
        for pattern in instagram_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Take the first valid-looking handle
                for match in matches:
                    if len(match) > 2 and not match.isdigit():
                        handles['instagram_handle'] = match
                        break
                if 'instagram_handle' in handles:
                    break
        
        return handles
    
    def _extract_handles_llm(self, text: str, player_name: str, team: str = None) -> Dict[str, Any]:
        """
        Extract social media handles using LLM.
        
        Args:
            text: Text to analyze
            player_name: Player name for context
            team: Optional team name
            
        Returns:
            Dictionary with discovered handles
        """
        if not self.llm_adapter:
            return {}
        
        try:
            prompt = f"""
            Extract social media handles for NFL player "{player_name}"{f" on team {team}" if team else ""} from the following text.
            
            Text: {text[:2000]}  # Limit text length
            
            Return JSON with:
            - twitter_handle: Twitter/X handle without @ symbol
            - instagram_handle: Instagram handle without @ symbol
            - confidence: confidence score 0-1
            
            Only return handles that clearly belong to the specified player.
            """
            
            result = self.llm_adapter.extract_metrics(text, 'social_discovery', prompt)
            
            if result and isinstance(result, dict):
                handles = {}
                if result.get('twitter_handle'):
                    handles['twitter_handle'] = result['twitter_handle'].lstrip('@')
                if result.get('instagram_handle'):
                    handles['instagram_handle'] = result['instagram_handle'].lstrip('@')
                
                return handles
                
        except Exception as e:
            self.logger.error(f"Error extracting handles with LLM: {e}")
        
        return {}
    
    def _extract_twitter_metrics(self, handle: str) -> Dict[str, Any]:
        """
        Extract Twitter metrics for a given handle.
        
        Args:
            handle: Twitter handle
            
        Returns:
            Dictionary with Twitter metrics
        """
        metrics = {}
        
        try:
            # Note: Direct Twitter scraping is challenging due to their restrictions
            # This is a placeholder implementation - in production you would need:
            # 1. Twitter API access
            # 2. Third-party social media APIs
            # 3. Specialized scraping tools
            
            url = f"https://twitter.com/{handle}"
            
            polite_delay(self.config.request_delay_min, self.config.request_delay_max)
            
            response = self.session.get(url, timeout=self.config.request_timeout)
            
            if response.status_code == 200:
                # Use regex to find follower counts in the HTML
                follower_matches = re.findall(r'(\d+(?:,\d+)*(?:\.\d+)?[KM]?)\s*(?:Followers?|Following)', 
                                            response.text, re.IGNORECASE)
                
                if follower_matches:
                    metrics['twitter_followers'] = self._convert_follower_count(follower_matches[0])
                
                # Mark as verified if we successfully accessed the profile
                metrics['twitter_verified'] = True
                
            self.logger.info(f"Extracted Twitter metrics for @{handle}")
            
        except Exception as e:
            self.logger.warning(f"Could not extract Twitter metrics for @{handle}: {e}")
        
        return metrics
    
    def _extract_instagram_metrics(self, handle: str) -> Dict[str, Any]:
        """
        Extract Instagram metrics for a given handle.
        
        Args:
            handle: Instagram handle
            
        Returns:
            Dictionary with Instagram metrics
        """
        metrics = {}
        
        try:
            # Note: Instagram also has restrictions on scraping
            # This is a placeholder implementation
            
            url = f"https://instagram.com/{handle}"
            
            polite_delay(self.config.request_delay_min, self.config.request_delay_max)
            
            response = self.session.get(url, timeout=self.config.request_timeout)
            
            if response.status_code == 200:
                # Use regex to find follower counts
                follower_matches = re.findall(r'(\d+(?:,\d+)*(?:\.\d+)?[KM]?)\s*(?:followers?)', 
                                            response.text, re.IGNORECASE)
                
                if follower_matches:
                    metrics['instagram_followers'] = self._convert_follower_count(follower_matches[0])
                
                # Mark as verified if we successfully accessed the profile
                metrics['instagram_verified'] = True
                
            self.logger.info(f"Extracted Instagram metrics for @{handle}")
            
        except Exception as e:
            self.logger.warning(f"Could not extract Instagram metrics for @{handle}: {e}")
        
        return metrics
    
    def _convert_follower_count(self, count_str: str) -> int:
        """
        Convert follower count string to integer.
        
        Args:
            count_str: Follower count string (e.g., "1.2K", "5M")
            
        Returns:
            Integer follower count
        """
        count_str = count_str.replace(',', '').strip()
        
        if 'K' in count_str.upper():
            return int(float(count_str.upper().replace('K', '')) * 1000)
        elif 'M' in count_str.upper():
            return int(float(count_str.upper().replace('M', '')) * 1000000)
        else:
            return int(float(count_str))
    
    def extract_team_social_data(self, team_name: str) -> Dict[str, Any]:
        """
        Extract social media data for an NFL team.
        
        Args:
            team_name: Name of the team
            
        Returns:
            Dictionary with team social media data
        """
        try:
            social_data = {'data_source': 'team_social_media'}
            
            # NFL teams have more standardized social media presence
            team_handles = self._get_official_team_handles(team_name)
            social_data.update(team_handles)
            
            # Extract metrics for official handles
            if social_data.get('twitter_handle'):
                twitter_metrics = self._extract_twitter_metrics(social_data['twitter_handle'])
                social_data.update(twitter_metrics)
            
            if social_data.get('instagram_handle'):
                instagram_metrics = self._extract_instagram_metrics(social_data['instagram_handle'])
                social_data.update(instagram_metrics)
            
            return social_data
            
        except Exception as e:
            self.logger.error(f"Error extracting team social data for {team_name}: {e}")
            return {'data_source': 'team_social_media'}
    
    def _get_official_team_handles(self, team_name: str) -> Dict[str, str]:
        """
        Get official social media handles for NFL teams.
        
        Args:
            team_name: Team name
            
        Returns:
            Dictionary with official handles
        """
        # Mapping of team names to their official social media handles
        team_handles = {
            '49ers': {'twitter_handle': '49ers', 'instagram_handle': '49ers'},
            'bears': {'twitter_handle': 'ChicagoBears', 'instagram_handle': 'chicagobears'},
            'bengals': {'twitter_handle': 'Bengals', 'instagram_handle': 'bengals'},
            'bills': {'twitter_handle': 'BuffaloBills', 'instagram_handle': 'buffalobills'},
            'broncos': {'twitter_handle': 'Broncos', 'instagram_handle': 'broncos'},
            'browns': {'twitter_handle': 'Browns', 'instagram_handle': 'clevelandbrowns'},
            'buccaneers': {'twitter_handle': 'Buccaneers', 'instagram_handle': 'buccaneers'},
            'cardinals': {'twitter_handle': 'AZCardinals', 'instagram_handle': 'azcardinals'},
            'chargers': {'twitter_handle': 'Chargers', 'instagram_handle': 'chargers'},
            'chiefs': {'twitter_handle': 'Chiefs', 'instagram_handle': 'kansascitychiefs'},
            'colts': {'twitter_handle': 'Colts', 'instagram_handle': 'colts'},
            'commanders': {'twitter_handle': 'Commanders', 'instagram_handle': 'commanders'},
            'cowboys': {'twitter_handle': 'dallascowboys', 'instagram_handle': 'dallascowboys'},
            'dolphins': {'twitter_handle': 'MiamiDolphins', 'instagram_handle': 'miamidolphins'},
            'eagles': {'twitter_handle': 'Eagles', 'instagram_handle': 'philadelphiaeagles'},
            'falcons': {'twitter_handle': 'AtlantaFalcons', 'instagram_handle': 'atlantafalcons'},
            'giants': {'twitter_handle': 'Giants', 'instagram_handle': 'nygiants'},
            'jaguars': {'twitter_handle': 'Jaguars', 'instagram_handle': 'jaguars'},
            'jets': {'twitter_handle': 'nyjets', 'instagram_handle': 'nyjets'},
            'lions': {'twitter_handle': 'Lions', 'instagram_handle': 'detroitlionsnfl'},
            'packers': {'twitter_handle': 'packers', 'instagram_handle': 'packers'},
            'panthers': {'twitter_handle': 'Panthers', 'instagram_handle': 'panthers'},
            'patriots': {'twitter_handle': 'Patriots', 'instagram_handle': 'newenglandpatriots'},
            'raiders': {'twitter_handle': 'Raiders', 'instagram_handle': 'raiders'},
            'rams': {'twitter_handle': 'RamsNFL', 'instagram_handle': 'larams'},
            'ravens': {'twitter_handle': 'Ravens', 'instagram_handle': 'baltimoreravens'},
            'saints': {'twitter_handle': 'Saints', 'instagram_handle': 'neworleanssaints'},
            'seahawks': {'twitter_handle': 'Seahawks', 'instagram_handle': 'seahawks'},
            'steelers': {'twitter_handle': 'steelers', 'instagram_handle': 'steelers'},
            'texans': {'twitter_handle': 'HoustonTexans', 'instagram_handle': 'houstontexans'},
            'titans': {'twitter_handle': 'Titans', 'instagram_handle': 'titansonline'},
            'vikings': {'twitter_handle': 'Vikings', 'instagram_handle': 'minnesotavikings'}
        }
        
        return team_handles.get(team_name.lower(), {})
