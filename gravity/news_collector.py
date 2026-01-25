"""
News & Media Collector - FREE (No Firecrawl needed)
Collects news, interviews, and media data from free sources
"""

import requests
from bs4 import BeautifulSoup
import re
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from urllib.parse import quote
import time
import os
import traceback

# Optional feedparser for better RSS parsing
try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False

# Import collection utilities
try:
    from gravity.collection_utils import (
        retry_with_backoff, parse_news_date, categorize_article_date
    )
except ImportError:
    # Fallback
    def retry_with_backoff(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def parse_news_date(date_str):
        return None
    def categorize_article_date(article_date, now=None):
        return {'is_7d': False, 'is_30d': False, 'age_days': None}

# Try to import VADER sentiment
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
    sentiment_analyzer = SentimentIntensityAnalyzer()
except ImportError:
    VADER_AVAILABLE = False
    sentiment_analyzer = None

logger = logging.getLogger(__name__)


class NewsCollector:
    """Collect news and media data from free sources"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        # NewsAPI.org key (optional - free tier: 100 requests/day)
        self.newsapi_key = os.getenv('NEWSAPI_KEY', None)
        if self.newsapi_key:
            logger.info("✅ NewsAPI.org key found - will use as additional news source")
        else:
            logger.info("ℹ️ NewsAPI.org key not set (optional - free tier available)")
        
        # Log VADER availability
        if not VADER_AVAILABLE:
            logger.info("ℹ️ VADER sentiment not available - using keyword-based sentiment (install: pip install vaderSentiment)")
    
    def collect_news_data(self, player_name: str, espn_id: Optional[str] = None) -> Dict:
        """
        Collect comprehensive news and media data
        
        Args:
            player_name: Player's name
            espn_id: Optional ESPN athlete ID for ESPN news API
        
        Returns:
            Dict with news and media details
        """
        logger.info(f"📰 Collecting news data for {player_name}...")
        
        news_data = {
            'news_headline_count_7d': 0,
            'news_headline_count_30d': 0,
            'news_headline_count_365d': 0,
            'news_headline_count_1095d': 0,
            'recent_headlines': [],
            'recent_interviews': [],
            'podcast_appearances': [],
            'media_sentiment': 0.0,
            'media_sentiment_7d': 0.0,
            'media_sentiment_30d': 0.0,
            'media_sentiment_365d': 0.0,
            'media_sentiment_1095d': 0.0,
            'mention_velocity': 0.0,
            'trending': False
        }
        
        # 1. Get recent news headlines from multiple sources
        headlines = []
        
        # Source 1: ESPN News (most relevant if available)
        if espn_id:
            espn_headlines = self._get_espn_news(player_name, espn_id)
            headlines.extend(espn_headlines)
        
        # Source 2: Google News RSS (search 3 years back for historical data)
        google_headlines = self._get_google_news_rss(player_name, days=1095)
        headlines.extend(google_headlines)
        
        # Source 3: DuckDuckGo News (fallback if Google fails, also search 3 years)
        if len(google_headlines) == 0:
            ddg_headlines = self._get_duckduckgo_news(player_name, days=1095)
            headlines.extend(ddg_headlines)
        
        # Source 4: NewsAPI.org (if available)
        if self.newsapi_key:
            newsapi_headlines = self._get_newsapi_headlines(player_name)
            headlines.extend(newsapi_headlines)
        
        # Remove duplicates and filter by relevance
        headlines = self._deduplicate_and_filter(headlines, player_name)
        
        if headlines:
            # Sort by date (most recent first)
            headlines.sort(key=lambda x: x.get('date') or datetime.min, reverse=True)
            
            news_data['recent_headlines'] = headlines[:10]
            
            # Count headlines by time period
            headlines_7d = [h for h in headlines if h.get('is_7d')]
            headlines_30d = [h for h in headlines if h.get('is_30d')]
            headlines_365d = [h for h in headlines if h.get('is_365d')]
            headlines_1095d = [h for h in headlines if h.get('is_1095d')]
            
            news_data['news_headline_count_7d'] = len(headlines_7d)
            news_data['news_headline_count_30d'] = len(headlines_30d)
            news_data['news_headline_count_365d'] = len(headlines_365d)
            news_data['news_headline_count_1095d'] = len(headlines_1095d)
            
            # Calculate sentiment for each time period
            news_data['media_sentiment'] = self._calculate_sentiment(headlines)
            news_data['media_sentiment_7d'] = self._calculate_sentiment(headlines_7d) if headlines_7d else 0.0
            news_data['media_sentiment_30d'] = self._calculate_sentiment(headlines_30d) if headlines_30d else 0.0
            news_data['media_sentiment_365d'] = self._calculate_sentiment(headlines_365d) if headlines_365d else 0.0
            news_data['media_sentiment_1095d'] = self._calculate_sentiment(headlines_1095d) if headlines_1095d else 0.0
            
            # Calculate mention velocity (mentions per day)
            if headlines:
                days_span = 30
                news_data['mention_velocity'] = len(headlines_30d) / days_span
                
                # Trending if velocity is high (>1 mention per day in last 7 days)
                if news_data['news_headline_count_7d'] > 7:
                    news_data['trending'] = True
        
        # 2. Search for interviews
        interviews = self._search_interviews(player_name)
        if interviews:
            news_data['recent_interviews'] = interviews
        
        # 3. Search for podcast appearances
        podcasts = self._search_podcasts(player_name)
        if podcasts:
            news_data['podcast_appearances'] = podcasts
        
        logger.info(f"✅ News: {news_data['news_headline_count_30d']} articles (30d), "
                   f"{news_data['news_headline_count_7d']} (7d), "
                   f"{news_data['news_headline_count_365d']} (1yr), "
                   f"{news_data['news_headline_count_1095d']} (3yr), "
                   f"sentiment: {news_data['media_sentiment']:.2f}")
        
        return news_data
    
    def _get_recent_headlines(self, player_name: str, days: int = 30) -> List[Dict]:
        """
        Get recent headlines from DuckDuckGo News
        """
        try:
            headlines = []
            
            # DuckDuckGo News search
            search_url = f"https://duckduckgo.com/?q={player_name.replace(' ', '+')}&ia=news&iax=news"
            
            response = self.session.get(search_url, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find news results
                news_items = soup.find_all('div', class_='result')
                
                for item in news_items[:50]:  # Check up to 50 results
                    try:
                        # Extract headline
                        title_elem = item.find('a', class_='result__a')
                        if not title_elem:
                            continue
                        
                        headline = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '')
                        
                        # Extract date/time if available
                        time_elem = item.find('span', class_='result__timestamp')
                        date_str = time_elem.get_text(strip=True) if time_elem else ''
                        
                        # Parse date using improved parser
                        date = parse_news_date(date_str)
                        
                        # Extract source
                        source_elem = item.find('span', class_='result__source')
                        source = source_elem.get_text(strip=True) if source_elem else 'Unknown'
                        
                        headlines.append({
                            'headline': headline,
                            'url': url,
                            'date': date,
                            'source': source,
                            'age_days': (datetime.now() - date).days if date else None
                        })
                    
                    except Exception as e:
                        logger.debug(f"Error parsing news item: {e}")
                        continue
            
            # Alternative: Try Google News RSS (simpler, more reliable)
            if len(headlines) < 10:
                rss_headlines = self._get_google_news_rss(player_name)
                headlines.extend(rss_headlines)
            
            # Filter to last N days and add date categorization
            cutoff_date = datetime.now() - timedelta(days=days)
            filtered_headlines = []
            for h in headlines:
                if h.get('date') and h['date'] > cutoff_date:
                    # Add date categorization if not already present
                    if 'is_7d' not in h:
                        date_info = categorize_article_date(h['date'])
                        h.update(date_info)
                    filtered_headlines.append(h)
            
            headlines = filtered_headlines
            
            # Sort by date (most recent first)
            headlines.sort(key=lambda x: x.get('date') or datetime.min, reverse=True)
            
            return headlines
            
        except Exception as e:
            logger.debug(f"Headline collection failed: {e}")
            return []
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, exceptions=(requests.RequestException,))
    def _get_google_news_rss(self, player_name: str, days: int = 30) -> List[Dict]:
        """
        Get news from Google News RSS feed with enhanced parsing.
        Uses feedparser if available for better reliability, falls back to BeautifulSoup.
        
        Args:
            player_name: Player name to search
            days: Number of days to look back (default 30)
        """
        try:
            headlines = []
            
            # Google News RSS feed URL - add sport context for better results
            query = f"{player_name} NFL OR NBA"
            rss_url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Try feedparser first (more robust)
            if FEEDPARSER_AVAILABLE:
                logger.info(f"   📰 Using feedparser for Google News RSS...")
                feed = feedparser.parse(rss_url)
                
                for entry in feed.entries[:50]:  # Process up to 50 recent entries
                    try:
                        title_text = entry.title if hasattr(entry, 'title') else ''
                        link_text = entry.link if hasattr(entry, 'link') else ''
                        
                        if not title_text or not link_text:
                            continue
                        
                        # Parse publication date
                        pub_date = None
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            pub_date = datetime(*entry.published_parsed[:6])
                        elif hasattr(entry, 'published'):
                            pub_date = parse_news_date(entry.published)
                        
                        # Skip if no date or too old
                        if not pub_date or pub_date < cutoff_date:
                            continue
                        
                        # Extract source from title (Google News format: "Title - Source")
                        source = 'Unknown'
                        if ' - ' in title_text:
                            parts = title_text.rsplit(' - ', 1)
                            if len(parts) == 2:
                                title_text, source = parts
                        
                        # Get description if available
                        description = entry.get('summary', '') if hasattr(entry, 'get') else ''
                        
                        # Calculate relevance
                        relevance = self._calculate_relevance(title_text, player_name, source)
                        
                        # Categorize by date
                        date_info = categorize_article_date(pub_date)
                        
                        headlines.append({
                            'headline': title_text,
                            'url': link_text,
                            'date': pub_date,
                            'source': source,
                            'description': description,
                            'relevance': relevance,
                            'is_7d': date_info['is_7d'],
                            'is_30d': date_info['is_30d'],
                            'age_days': date_info['age_days']
                        })
                    except Exception as e:
                        logger.debug(f"Error parsing feedparser entry: {e}")
                        continue
                
                if headlines:
                    logger.info(f"   ✅ Feedparser found {len(headlines)} articles")
                else:
                    logger.warning(f"   ⚠️  Feedparser found 0 articles for {player_name}")
                    logger.debug(f"   RSS URL: {rss_url}")
                return headlines
            
            # Fallback: BeautifulSoup parsing
            logger.info(f"   📰 Using BeautifulSoup for Google News RSS...")
            response = self.session.get(rss_url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'xml')
                
                items = soup.find_all('item')
                
                for item in items[:30]:
                    try:
                        title = item.find('title')
                        link = item.find('link')
                        pub_date_elem = item.find('pubDate')
                        
                        if not title or not link:
                            continue
                        
                        title_text = title.get_text(strip=True)
                        link_text = link.get_text(strip=True)
                        pub_date_str = pub_date_elem.get_text(strip=True) if pub_date_elem else ''
                        
                        # Use improved date parsing
                        pub_date = parse_news_date(pub_date_str)
                        if not pub_date or pub_date < cutoff_date:
                            continue
                        
                        # Extract source from title (Google News format: "Title - Source")
                        source = 'Unknown'
                        if ' - ' in title_text:
                            parts = title_text.rsplit(' - ', 1)
                            if len(parts) == 2:
                                title_text, source = parts
                        
                        # Calculate relevance score
                        relevance = self._calculate_relevance(title_text, player_name, source)
                        
                        # Categorize by date
                        date_info = categorize_article_date(pub_date)
                        
                        headlines.append({
                            'headline': title_text,
                            'url': link_text,
                            'date': pub_date,
                            'source': source,
                            'relevance': relevance,
                            'is_7d': date_info['is_7d'],
                            'is_30d': date_info['is_30d'],
                            'age_days': date_info['age_days']
                        })
                    
                    except Exception as e:
                        logger.debug(f"Error parsing RSS item: {e}")
                        continue
            
            return headlines
            
        except Exception as e:
            logger.warning(f"Google News RSS failed for {player_name}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def _get_duckduckgo_news(self, player_name: str, days: int = 30) -> List[Dict]:
        """Get news from DuckDuckGo news search (FREE, no API key needed)"""
        try:
            from duckduckgo_search import DDGS
            
            ddgs = DDGS()
            query = f'"{player_name}" NFL news'
            
            logger.info(f"   🦆 Searching DuckDuckGo News for {player_name}...")
            results = list(ddgs.news(query, max_results=20))
            
            headlines = []
            cutoff_date = datetime.now() - timedelta(days=days)
            
            for result in results:
                try:
                    # Parse date
                    pub_date = parse_news_date(result.get('date', ''))
                    if not pub_date or pub_date < cutoff_date:
                        continue
                    
                    # Get title and URL
                    title = result.get('title', '')
                    url = result.get('url', '')
                    
                    if not title or not url:
                        continue
                    
                    # Calculate relevance
                    source = result.get('source', 'Unknown')
                    relevance = self._calculate_relevance(title, player_name, source)
                    
                    # Categorize by date
                    date_info = categorize_article_date(pub_date)
                    
                    headlines.append({
                        'headline': title,
                        'url': url,
                        'date': pub_date,
                        'source': source,
                        'description': result.get('body', ''),
                        'relevance': relevance,
                        'is_7d': date_info['is_7d'],
                        'is_30d': date_info['is_30d'],
                        'age_days': date_info['age_days']
                    })
                    
                except Exception as e:
                    logger.debug(f"Error parsing DDG news result: {e}")
                    continue
            
            if headlines:
                logger.info(f"   ✅ DuckDuckGo News found {len(headlines)} articles")
            else:
                logger.warning(f"   ⚠️  DuckDuckGo News found 0 articles for {player_name}")
            
            return headlines
            
        except ImportError:
            logger.debug("DuckDuckGo search not available (install: pip install duckduckgo-search)")
            return []
        except Exception as e:
            logger.warning(f"DuckDuckGo news search failed for {player_name}: {e}")
            logger.debug(traceback.format_exc())
            return []
    
    def _get_espn_news(self, player_name: str, espn_id: Optional[str] = None) -> List[Dict]:
        """Get news from ESPN athlete news API"""
        if not espn_id:
            return []
        
        try:
            logger.info(f"   📰 Fetching ESPN news for {player_name} (ID: {espn_id})...")
            url = f"https://site.api.espn.com/apis/common/v3/news?athlete={espn_id}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                
                headlines = []
                for article in articles[:10]:
                    try:
                        pub_date_str = article.get('published')
                        pub_date = parse_news_date(pub_date_str) if pub_date_str else None
                        
                        if not pub_date:
                            continue
                        
                        # Get article link
                        url_link = ''
                        links = article.get('links', {})
                        if isinstance(links, dict):
                            web_link = links.get('web', {})
                            if isinstance(web_link, dict):
                                url_link = web_link.get('href', '')
                        
                        # Categorize by date
                        date_info = categorize_article_date(pub_date)
                        
                        headlines.append({
                            'headline': article.get('headline', ''),
                            'url': url_link,
                            'date': pub_date,
                            'source': 'ESPN',
                            'description': article.get('description', ''),
                            'relevance': 1.0,  # ESPN articles are highly relevant
                            'is_7d': date_info['is_7d'],
                            'is_30d': date_info['is_30d'],
                            'age_days': date_info['age_days']
                        })
                    except Exception as e:
                        logger.debug(f"Error parsing ESPN article: {e}")
                        continue
                
                if headlines:
                    logger.info(f"   ✅ ESPN News found {len(headlines)} articles")
                else:
                    logger.debug(f"   ESPN returned 0 articles for {player_name}")
                
                return headlines
            else:
                logger.debug(f"ESPN news API returned status {response.status_code}")
                return []
                
        except Exception as e:
            logger.warning(f"ESPN news collection failed for {player_name}: {e}")
            return []
    
    @retry_with_backoff(max_retries=2, initial_delay=1.0, exceptions=(requests.RequestException,))
    def _get_newsapi_headlines(self, player_name: str, days: int = 30) -> List[Dict]:
        """
        Get news from NewsAPI.org
        
        NOTE: Free tier only provides last 30 days of data.
        For historical data beyond 30 days, a paid plan is required.
        """
        if not self.newsapi_key:
            return []
        
        try:
            headlines = []
            
            logger.info(f"   📰 Fetching from NewsAPI.org (last {min(days, 30)} days)...")
            
            # NewsAPI.org endpoint
            url = "https://newsapi.org/v2/everything"
            
            # Free tier limitation: can only search last 30 days
            search_days = min(days, 30)
            
            params = {
                'q': f'"{player_name}" AND (NFL OR NBA OR football OR basketball)',
                'apiKey': self.newsapi_key,
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': 100,  # Max allowed per request
                'from': (datetime.now() - timedelta(days=search_days)).strftime('%Y-%m-%d')
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                
                logger.info(f"   📰 NewsAPI returned {len(articles)} articles")
                
                for article in articles:
                    try:
                        title = article.get('title', '')
                        url_link = article.get('url', '')
                        pub_date_str = article.get('publishedAt', '')
                        source_name = article.get('source', {}).get('name', 'Unknown')
                        description = article.get('description', '')
                        
                        if not title or not url_link:
                            continue
                        
                        # Parse date
                        pub_date = parse_news_date(pub_date_str)
                        if not pub_date:
                            continue
                        
                        # Calculate relevance
                        relevance = self._calculate_relevance(title, player_name, source_name)
                        
                        # Categorize by date (now includes 365d and 1095d)
                        date_info = categorize_article_date(pub_date)
                        
                        headlines.append({
                            'headline': title,
                            'url': url_link,
                            'date': pub_date,
                            'source': source_name,
                            'description': description,
                            'relevance': relevance,
                            'is_7d': date_info['is_7d'],
                            'is_30d': date_info['is_30d'],
                            'is_365d': date_info['is_365d'],
                            'is_1095d': date_info['is_1095d'],
                            'age_days': date_info['age_days']
                        })
                    
                    except Exception as e:
                        logger.debug(f"Error parsing NewsAPI article: {e}")
                        continue
                
                if headlines:
                    logger.info(f"   ✅ NewsAPI: Processed {len(headlines)} relevant articles")
            elif response.status_code == 429:
                logger.warning("NewsAPI rate limit reached (100 requests/day)")
            else:
                logger.debug(f"NewsAPI request failed: {response.status_code}")
            
            return headlines
            
        except Exception as e:
            logger.warning(f"NewsAPI collection failed: {e}")
            return []
    
    def _calculate_relevance(self, headline: str, player_name: str, source: str) -> float:
        """
        Calculate relevance score for an article (0.0 to 1.0)
        Higher score = more relevant to the player
        """
        score = 0.0
        headline_lower = headline.lower()
        player_lower = player_name.lower()
        source_lower = source.lower()
        
        # Exact name match (highest score)
        if player_lower in headline_lower:
            score += 0.5
        
        # First and last name both present
        name_parts = player_name.split()
        if len(name_parts) >= 2:
            if name_parts[0].lower() in headline_lower and name_parts[-1].lower() in headline_lower:
                score += 0.3
        
        # Source credibility (ESPN, official sources = higher)
        credible_sources = ['espn', 'nfl.com', 'nba.com', 'the athletic', 'sports illustrated', 
                          'bleacher report', 'cbs sports', 'fox sports']
        if any(cred in source_lower for cred in credible_sources):
            score += 0.2
        
        # Penalize irrelevant sources
        irrelevant_sources = ['fantasy', 'betting', 'odds', 'gambling']
        if any(irr in source_lower for irr in irrelevant_sources):
            score -= 0.2
        
        return min(1.0, max(0.0, score))
    
    def _deduplicate_and_filter(self, headlines: List[Dict], player_name: str) -> List[Dict]:
        """Remove duplicates and filter by relevance"""
        seen_urls = set()
        filtered = []
        
        for headline in headlines:
            url = headline.get('url', '')
            relevance = headline.get('relevance', 0.0)
            
            # Skip duplicates
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            # Filter by relevance (keep articles with relevance > 0.3)
            if relevance >= 0.3:
                filtered.append(headline)
        
        # Sort by relevance (highest first), then by date
        filtered.sort(key=lambda x: (x.get('relevance', 0), x.get('date') or datetime.min), reverse=True)
        
        return filtered
    
    def _search_interviews(self, player_name: str) -> List[str]:
        """Search for recent interviews"""
        try:
            interviews = []
            
            search_query = f'"{player_name}" interview'
            url = f"https://duckduckgo.com/html/?q={search_query.replace(' ', '+')}"
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = soup.find_all('a', class_='result__a')
                
                for result in results[:10]:
                    title = result.get_text(strip=True)
                    url = result.get('href', '')
                    
                    # Filter for actual interviews
                    if any(word in title.lower() for word in ['interview', 'talks', 'sits down', 'exclusive']):
                        interviews.append({
                            'title': title,
                            'url': url
                        })
            
            return interviews[:5]  # Return top 5
            
        except Exception as e:
            logger.debug(f"Interview search failed: {e}")
            return []
    
    def _search_podcasts(self, player_name: str) -> List[str]:
        """Search for podcast appearances"""
        try:
            podcasts = []
            
            search_query = f'"{player_name}" podcast'
            url = f"https://duckduckgo.com/html/?q={search_query.replace(' ', '+')}"
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = soup.find_all('a', class_='result__a')
                
                for result in results[:10]:
                    title = result.get_text(strip=True)
                    url = result.get('href', '')
                    
                    # Filter for podcast-related content
                    if any(word in title.lower() for word in ['podcast', 'episode', 'show', 'the ringer', 'barstool']):
                        podcasts.append({
                            'title': title,
                            'url': url
                        })
            
            return podcasts[:5]  # Return top 5
            
        except Exception as e:
            logger.debug(f"Podcast search failed: {e}")
            return []
    
    def _calculate_sentiment(self, headlines: List[Dict]) -> float:
        """
        Calculate sentiment using VADER if available, otherwise keyword-based
        Returns: -1.0 (very negative) to 1.0 (very positive)
        """
        if not headlines:
            return 0.0
        
        # Use VADER if available (more accurate)
        if VADER_AVAILABLE and sentiment_analyzer:
            sentiment_scores = []
            for headline in headlines[:20]:  # Limit to first 20 for performance
                text = headline.get('headline', '')
                if text:
                    scores = sentiment_analyzer.polarity_scores(text)
                    # Use compound score (-1 to 1)
                    sentiment_scores.append(scores['compound'])
            
            if sentiment_scores:
                return sum(sentiment_scores) / len(sentiment_scores)
        
        # Fallback: keyword-based sentiment
        positive_keywords = [
            'win', 'score', 'touchdown', 'victory', 'champion', 'mvp',
            'record', 'career-high', 'dominant', 'amazing', 'incredible',
            'breakout', 'star', 'elite', 'best', 'great', 'clutch', 'signed',
            'extension', 'deal', 'award', 'honor', 'selected', 'pro bowl'
        ]
        
        negative_keywords = [
            'injury', 'injured', 'suspend', 'fine', 'arrest', 'charge',
            'controversy', 'loss', 'lose', 'decline', 'struggle', 'benched',
            'trade', 'cut', 'released', 'criticism', 'criticized', 'failed',
            'missed', 'out', 'doubtful', 'questionable'
        ]
        
        sentiment_scores = []
        
        for headline in headlines:
            text = headline.get('headline', '').lower()
            
            positive_count = sum(1 for word in positive_keywords if word in text)
            negative_count = sum(1 for word in negative_keywords if word in text)
            
            if positive_count > 0 or negative_count > 0:
                score = (positive_count - negative_count) / max(1, positive_count + negative_count)
                sentiment_scores.append(score)
        
        if sentiment_scores:
            return sum(sentiment_scores) / len(sentiment_scores)
        else:
            return 0.0  # Neutral
    
    def _parse_relative_date(self, date_str: str) -> Optional[datetime]:
        """Parse relative date strings - now uses improved parse_news_date"""
        return parse_news_date(date_str)


# Standalone usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    collector = NewsCollector()
    
    # Test with Patrick Mahomes
    news = collector.collect_news_data("Patrick Mahomes")
    print(f"\nNews Data: {news}")

