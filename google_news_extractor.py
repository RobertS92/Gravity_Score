
"""
Google News Extractor for NFL Players
Extracts headline counts and biographical information from Google News
"""

import requests
from bs4 import BeautifulSoup
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote_plus
import time
import random

logger = logging.getLogger(__name__)

class GoogleNewsExtractor:
    """Extractor for Google News headlines and biographical snippets."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.delay_range = (2, 4)  # Respectful delays
        
    def extract_player_news_data(self, player_name: str, team: str = None) -> Dict:
        """
        Extract Google News headlines and biographical snippets for a player.
        
        Args:
            player_name: Name of the player
            team: Optional team name for more targeted search
            
        Returns:
            Dictionary containing news data
        """
        try:
            news_data = {
                'news_headline_count': 0,
                'recent_headlines': [],
                'news_bio_snippets': [],
                'google_news_url': None,
                'news_extraction_timestamp': datetime.now().isoformat(),
                'data_sources': ['Google News']
            }
            
            # Search Google News for the player
            search_queries = [
                f'"{player_name}" NFL',
                f'{player_name} NFL football',
            ]
            
            if team:
                search_queries.extend([
                    f'"{player_name}" {team} NFL',
                    f'{player_name} {team} football'
                ])
            
            all_headlines = []
            all_bio_snippets = []
            
            for query in search_queries:
                try:
                    logger.info(f"📰 Searching Google News for: {query}")
                    
                    # Search Google News
                    headlines, bio_snippets = self._search_google_news(query)
                    
                    all_headlines.extend(headlines)
                    all_bio_snippets.extend(bio_snippets)
                    
                    # Respectful delay between queries
                    time.sleep(random.uniform(*self.delay_range))
                    
                except Exception as e:
                    logger.warning(f"Error searching Google News for '{query}': {e}")
                    continue
            
            # Remove duplicates and clean data
            unique_headlines = list(set(all_headlines))
            unique_bio_snippets = list(set(all_bio_snippets))
            
            # Filter for relevant headlines (contain player name)
            relevant_headlines = [
                headline for headline in unique_headlines
                if self._is_relevant_headline(headline, player_name)
            ]
            
            # Update news data
            news_data['news_headline_count'] = len(relevant_headlines)
            news_data['recent_headlines'] = relevant_headlines[:10]  # Top 10
            news_data['news_bio_snippets'] = unique_bio_snippets[:5]  # Top 5
            
            # Create Google News search URL
            main_query = f'"{player_name}" NFL'
            if team:
                main_query += f' {team}'
            news_data['google_news_url'] = f"https://news.google.com/search?q={quote_plus(main_query)}"
            
            logger.info(f"📰 Found {len(relevant_headlines)} headlines for {player_name}")
            
            return news_data
            
        except Exception as e:
            logger.error(f"Error extracting Google News data for {player_name}: {e}")
            return {
                'news_headline_count': 0,
                'recent_headlines': [],
                'news_bio_snippets': [],
                'google_news_url': None,
                'news_extraction_timestamp': datetime.now().isoformat(),
                'data_sources': ['Google News (error)']
            }
    
    def _search_google_news(self, query: str) -> tuple[List[str], List[str]]:
        """
        Search Google News for headlines and bio snippets.
        
        Args:
            query: Search query
            
        Returns:
            Tuple of (headlines, bio_snippets)
        """
        headlines = []
        bio_snippets = []
        
        try:
            # Use Google News search
            search_url = "https://news.google.com/search"
            params = {
                'q': query,
                'hl': 'en-US',
                'gl': 'US',
                'ceid': 'US:en'
            }
            
            response = self.session.get(search_url, params=params, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract headlines from Google News
                # Google News uses various article selectors
                article_selectors = [
                    'article',
                    '[role="article"]',
                    '.xrnccd',
                    '.JtKRv'
                ]
                
                for selector in article_selectors:
                    articles = soup.select(selector)
                    
                    for article in articles[:20]:  # Limit to first 20
                        # Extract headline
                        headline_elem = article.find(['h3', 'h4', 'a'])
                        if headline_elem:
                            headline = self._clean_text(headline_elem.get_text())
                            if headline and len(headline) > 10:
                                headlines.append(headline)
                        
                        # Extract bio snippet
                        snippet_elem = article.find(['p', 'span', 'div'])
                        if snippet_elem:
                            snippet = self._clean_text(snippet_elem.get_text())
                            if snippet and len(snippet) > 20 and self._is_biographical(snippet):
                                bio_snippets.append(snippet)
            
            # Fallback: Use regular Google search for news
            if not headlines:
                headlines, additional_snippets = self._fallback_google_search(query)
                bio_snippets.extend(additional_snippets)
                
        except Exception as e:
            logger.warning(f"Error searching Google News: {e}")
            
        return headlines, bio_snippets
    
    def _fallback_google_search(self, query: str) -> tuple[List[str], List[str]]:
        """
        Fallback to regular Google search for news results.
        
        Args:
            query: Search query
            
        Returns:
            Tuple of (headlines, bio_snippets)
        """
        headlines = []
        bio_snippets = []
        
        try:
            # Search regular Google with news filter
            search_url = "https://www.google.com/search"
            params = {
                'q': f'{query} news',
                'tbm': 'nws',  # News search
                'num': 20
            }
            
            response = self.session.get(search_url, params=params, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract news results
                news_results = soup.find_all(['h3', 'div'], class_=re.compile(r'.*title.*|.*headline.*'))
                
                for result in news_results:
                    headline = self._clean_text(result.get_text())
                    if headline and len(headline) > 10:
                        headlines.append(headline)
                
                # Extract snippets
                snippet_results = soup.find_all(['span', 'div'], class_=re.compile(r'.*snippet.*|.*description.*'))
                
                for result in snippet_results:
                    snippet = self._clean_text(result.get_text())
                    if snippet and len(snippet) > 20 and self._is_biographical(snippet):
                        bio_snippets.append(snippet)
                        
        except Exception as e:
            logger.warning(f"Error in fallback Google search: {e}")
            
        return headlines, bio_snippets
    
    def _is_relevant_headline(self, headline: str, player_name: str) -> bool:
        """
        Check if headline is relevant to the player.
        
        Args:
            headline: News headline
            player_name: Player name to match
            
        Returns:
            True if headline is relevant
        """
        if not headline or not player_name:
            return False
        
        headline_lower = headline.lower()
        name_parts = player_name.lower().split()
        
        # Check if player name or parts appear in headline
        for name_part in name_parts:
            if len(name_part) > 2 and name_part in headline_lower:
                return True
        
        # Check for NFL-related keywords
        nfl_keywords = ['nfl', 'football', 'touchdown', 'quarterback', 'yards', 'draft']
        has_nfl_keyword = any(keyword in headline_lower for keyword in nfl_keywords)
        
        # Must have player name component AND NFL context
        return has_nfl_keyword and any(name_part in headline_lower for name_part in name_parts if len(name_part) > 2)
    
    def _is_biographical(self, text: str) -> bool:
        """
        Check if text contains biographical information.
        
        Args:
            text: Text to check
            
        Returns:
            True if text appears biographical
        """
        if not text:
            return False
        
        text_lower = text.lower()
        
        # Biographical indicators
        bio_keywords = [
            'born', 'age', 'college', 'university', 'drafted', 'career',
            'played', 'started', 'yards', 'touchdowns', 'seasons',
            'graduated', 'attended', 'rookie', 'veteran', 'experience'
        ]
        
        return any(keyword in text_lower for keyword in bio_keywords)
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text.
        
        Args:
            text: Raw text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove extra whitespace and newlines
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common unwanted patterns
        cleaned = re.sub(r'\b\d+\s*(hours?|days?|weeks?)\s+ago\b', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b(source|via|by)\s*:\s*\w+', '', cleaned, flags=re.IGNORECASE)
        
        return cleaned.strip()

def test_google_news_extractor():
    """Test the Google News extractor with sample players."""
    extractor = GoogleNewsExtractor()
    
    # Test with famous players
    test_players = [
        ("Patrick Mahomes", "Chiefs"),
        ("Tom Brady", None),
        ("Aaron Rodgers", "Jets")
    ]
    
    for player_name, team in test_players:
        print(f"\n📰 Testing Google News extraction for {player_name}")
        
        try:
            news_data = extractor.extract_player_news_data(player_name, team)
            
            print(f"Headlines found: {news_data['news_headline_count']}")
            print(f"Bio snippets: {len(news_data['news_bio_snippets'])}")
            
            if news_data['recent_headlines']:
                print("Recent headlines:")
                for i, headline in enumerate(news_data['recent_headlines'][:3], 1):
                    print(f"  {i}. {headline[:80]}...")
            
            if news_data['news_bio_snippets']:
                print("Bio snippets:")
                for i, snippet in enumerate(news_data['news_bio_snippets'][:2], 1):
                    print(f"  {i}. {snippet[:100]}...")
            
            print(f"Google News URL: {news_data['google_news_url']}")
            
        except Exception as e:
            print(f"Error testing {player_name}: {e}")

if __name__ == "__main__":
    test_google_news_extractor()
