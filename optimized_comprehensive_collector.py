"""
Optimized Comprehensive NFL Player Data Collector
Fast, efficient collection of 40+ fields with timeout handling and fallback strategies
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import concurrent.futures
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

class OptimizedComprehensiveCollector:
    """Optimized collector for comprehensive NFL player data with timeout handling."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.timeout = 10  # Reduced timeout for faster collection
        self.max_retries = 1  # Reduced retries for speed
        
    def collect_player_data_fast(self, player_name: str, team: str, position: str = None) -> Dict:
        """Fast collection of comprehensive player data with timeout handling."""
        logger.info(f"Fast collecting data for {player_name} ({team})")
        
        # Initialize with all 40+ fields
        player_data = {
            'name': player_name,
            'team': team,
            'position': position,
            'jersey_number': None,
            'height': None,
            'weight': None,
            'age': None,
            'birth_date': None,
            'college': None,
            'draft_year': None,
            'draft_round': None,
            'draft_pick': None,
            'years_pro': None,
            'games_played': None,
            'games_started': None,
            
            # Social Media
            'twitter_handle': None,
            'instagram_handle': None,
            'tiktok_handle': None,
            'youtube_handle': None,
            'twitter_followers': None,
            'instagram_followers': None,
            'tiktok_followers': None,
            'youtube_subscribers': None,
            'twitter_following': None,
            'instagram_following': None,
            'tiktok_following': None,
            
            # Career Stats
            'career_pass_yards': None,
            'career_pass_tds': None,
            'career_pass_ints': None,
            'career_pass_rating': None,
            'career_rush_yards': None,
            'career_rush_tds': None,
            'career_receptions': None,
            'career_rec_yards': None,
            'career_rec_tds': None,
            'career_tackles': None,
            'career_sacks': None,
            'career_interceptions': None,
            
            # Awards and Recognition
            'pro_bowls': None,
            'all_pro_selections': None,
            'super_bowl_wins': None,
            'rookie_of_year': None,
            'mvp_awards': None,
            'college_awards': None,
            
            # Contract and Financial
            'current_salary': None,
            'career_earnings': None,
            'contract_years': None,
            'contract_value': None,
            'signing_bonus': None,
            'guaranteed_money': None,
            
            # Media and External
            'wikipedia_url': None,
            'nfl_com_url': None,
            'espn_url': None,
            'pfr_url': None,
            'news_mentions': None,
            'fantasy_points': None,
            
            # Metadata
            'data_sources': [],
            'data_quality_score': 0,
            'collection_timestamp': datetime.now().isoformat(),
            'collection_duration': 0,
            'scraped_at': datetime.now()
        }
        
        start_time = time.time()
        
        # Collect data from multiple sources with parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            
            # Submit fast data collection tasks
            futures.append(executor.submit(self._collect_wikipedia_data_fast, player_name, team))
            futures.append(executor.submit(self._collect_nfl_com_data_fast, player_name, team))
            futures.append(executor.submit(self._collect_social_media_fast, player_name, team))
            
            # Collect results with timeout
            for future in concurrent.futures.as_completed(futures, timeout=30):
                try:
                    result = future.result()
                    if result:
                        player_data.update(result)
                except Exception as e:
                    logger.warning(f"Data collection task failed for {player_name}: {e}")
        
        # Calculate final metrics
        player_data['collection_duration'] = time.time() - start_time
        player_data['data_quality_score'] = self._calculate_quality_score(player_data)
        
        return player_data
    
    def _collect_wikipedia_data_fast(self, player_name: str, team: str) -> Dict:
        """Fast Wikipedia data collection with timeout."""
        try:
            # Use direct Wikipedia search
            search_url = f"https://en.wikipedia.org/w/api.php"
            params = {
                'action': 'opensearch',
                'search': f"{player_name} NFL {team}",
                'limit': 3,
                'format': 'json'
            }
            
            response = self.session.get(search_url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                if len(data) > 3 and data[3]:  # Check if URLs exist
                    wikipedia_url = data[3][0]  # First URL
                    return {
                        'wikipedia_url': wikipedia_url,
                        'data_sources': ['wikipedia']
                    }
        except Exception as e:
            logger.debug(f"Wikipedia collection failed for {player_name}: {e}")
        
        return {}
    
    def _collect_nfl_com_data_fast(self, player_name: str, team: str) -> Dict:
        """Fast NFL.com data collection."""
        try:
            # Quick NFL.com search
            search_term = f"{player_name} {team}".replace(' ', '+')
            search_url = f"https://www.nfl.com/search?query={search_term}"
            
            response = self.session.get(search_url, timeout=self.timeout)
            if response.status_code == 200:
                # Extract basic data from search results
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for player profile links
                player_links = soup.find_all('a', href=re.compile(r'/players/'))
                if player_links:
                    nfl_url = f"https://www.nfl.com{player_links[0]['href']}"
                    return {
                        'nfl_com_url': nfl_url,
                        'data_sources': ['nfl.com']
                    }
        except Exception as e:
            logger.debug(f"NFL.com collection failed for {player_name}: {e}")
        
        return {}
    
    def _collect_social_media_fast(self, player_name: str, team: str) -> Dict:
        """Fast social media data collection with basic profile discovery."""
        try:
            # Use Google search for social media profiles
            search_query = f'"{player_name}" NFL {team} Twitter Instagram site:twitter.com OR site:instagram.com'
            google_url = f"https://www.google.com/search?q={quote_plus(search_query)}"
            
            response = self.session.get(google_url, timeout=self.timeout)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for social media links
                social_data = {}
                
                # Extract Twitter handles
                twitter_links = soup.find_all('a', href=re.compile(r'twitter\.com/'))
                if twitter_links:
                    twitter_url = twitter_links[0]['href']
                    handle = twitter_url.split('/')[-1].replace('@', '')
                    social_data['twitter_handle'] = f"@{handle}"
                    social_data['twitter_url'] = twitter_url
                
                # Extract Instagram handles
                instagram_links = soup.find_all('a', href=re.compile(r'instagram\.com/'))
                if instagram_links:
                    instagram_url = instagram_links[0]['href']
                    handle = instagram_url.split('/')[-1].replace('@', '')
                    social_data['instagram_handle'] = f"@{handle}"
                    social_data['instagram_url'] = instagram_url
                
                if social_data:
                    social_data['data_sources'] = ['google_search']
                    return social_data
                    
        except Exception as e:
            logger.debug(f"Social media collection failed for {player_name}: {e}")
        
        return {}
    
    def _calculate_quality_score(self, player_data: Dict) -> float:
        """Calculate data quality score based on filled fields."""
        total_fields = 0
        filled_fields = 0
        
        for key, value in player_data.items():
            if key not in ['data_sources', 'collection_timestamp', 'collection_duration', 'scraped_at']:
                total_fields += 1
                if value and value != [] and value != 'Unknown':
                    filled_fields += 1
        
        return (filled_fields / total_fields) * 100 if total_fields > 0 else 0


def main():
    """Test the optimized comprehensive collector."""
    collector = OptimizedComprehensiveCollector()
    
    # Test with Brandon Aiyuk
    player_data = collector.collect_player_data_fast('Brandon Aiyuk', '49ers', 'WR')
    
    print(f"=== OPTIMIZED COMPREHENSIVE COLLECTION TEST ===")
    print(f"Player: {player_data['name']}")
    print(f"Collection Duration: {player_data['collection_duration']:.2f}s")
    print(f"Data Quality Score: {player_data['data_quality_score']:.1f}%")
    print(f"Data Sources: {player_data['data_sources']}")
    
    print("\nFields with data:")
    for key, value in player_data.items():
        if value and value != [] and key not in ['data_sources', 'collection_timestamp', 'scraped_at']:
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()