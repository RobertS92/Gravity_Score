"""
News Article Crawler
Discovers sports news (contracts, trades, draft, performance, NIL deals) from any news site
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from urllib.parse import quote
import re

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False

from gravity.crawlers.base_crawler import BaseCrawler
import os

logger = logging.getLogger(__name__)


class NewsArticleCrawler(BaseCrawler):
    """
    Crawl news sites for sports information using Google News RSS and Firecrawl
    """
    
    def __init__(self):
        super().__init__(rate_limit_delay=0.5)  # Faster for news sources
        self.newsapi_key = os.getenv('NEWSAPI_KEY', None)
    
    def get_crawler_name(self) -> str:
        return "news_article"
    
    def get_supported_sports(self) -> List[str]:
        return ['nfl', 'nba', 'cfb', 'ncaab', 'mlb', 'nhl', 'wnba']
    
    async def crawl(
        self,
        athlete_id: Optional[uuid.UUID] = None,
        athlete_name: Optional[str] = None,
        sport: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Crawl news articles for an athlete
        
        Args:
            athlete_id: Optional athlete UUID
            athlete_name: Athlete name (required if athlete_id not provided)
            sport: Optional sport identifier
            **kwargs: Additional parameters
        
        Returns:
            Crawl result dict
        """
        try:
            # Resolve athlete_id if not provided
            if not athlete_id and athlete_name:
                athlete_id = self.find_athlete_by_name(athlete_name, sport)
                if not athlete_id:
                    logger.warning(f"{self.crawler_name}: Athlete not found: {athlete_name}")
                    return self.create_crawl_result(
                        success=False,
                        errors=[f"Athlete not found: {athlete_name}"]
                    )
            
            if not athlete_id:
                return self.create_crawl_result(
                    success=False,
                    errors=["athlete_id or athlete_name required"]
                )
            
            # Get athlete info
            athlete_info = self.get_athlete_info(athlete_id)
            if not athlete_info:
                return self.create_crawl_result(
                    success=False,
                    errors=[f"Athlete not found: {athlete_id}"]
                )
            
            athlete_name = athlete_info['name']
            sport = athlete_info.get('sport', sport)
            
            logger.info(f"{self.crawler_name}: Crawling news for {athlete_name} ({sport})")
            
            # Get news articles from multiple sources
            articles = await self._get_news_articles(athlete_name, sport)
            
            events_created = 0
            errors = []
            
            # Process each article
            for article in articles:
                try:
                    # Scrape full article content with Firecrawl
                    article_content = await self.scrape_with_firecrawl(article['url'])
                    
                    if article_content:
                        text = article_content.get('markdown', '') or article_content.get('content', '')
                        
                        # Extract event types from article
                        events = await self._extract_events_from_article(
                            text,
                            athlete_id,
                            athlete_name,
                            article
                        )
                        
                        # Store events
                        for event_type, event_data in events:
                            event_id = await self.store_event(
                                athlete_id=athlete_id,
                                event_type=event_type,
                                event_data=event_data,
                                event_timestamp=article.get('published_date', datetime.utcnow()),
                                source=article.get('source', 'news')
                            )
                            
                            if event_id:
                                events_created += 1
                                # Trigger score recalculation
                                await self.trigger_score_recalculation(athlete_id, event_type)
                    
                except Exception as e:
                    error_msg = f"Failed to process article {article.get('url', 'unknown')}: {e}"
                    logger.error(f"{self.crawler_name}: {error_msg}")
                    errors.append(error_msg)
            
            return self.create_crawl_result(
                success=True,
                events_created=events_created,
                errors=errors if errors else None,
                metadata={
                    'articles_found': len(articles),
                    'events_created': events_created
                }
            )
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Crawl failed: {e}")
            return self.create_crawl_result(
                success=False,
                errors=[str(e)]
            )
    
    async def _get_news_articles(
        self,
        athlete_name: str,
        sport: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get news articles from multiple sources
        
        Args:
            athlete_name: Athlete name
            sport: Optional sport
        
        Returns:
            List of article dicts
        """
        articles = []
        
        # Build search queries
        queries = [
            f'"{athlete_name}"',
            f'"{athlete_name}" {sport}' if sport else None,
            f'"{athlete_name}" contract',
            f'"{athlete_name}" trade',
            f'"{athlete_name}" draft',
            f'"{athlete_name}" NIL deal',
            f'"{athlete_name}" injury',
        ]
        
        queries = [q for q in queries if q]
        
        # 1. Google News RSS
        for query in queries[:3]:  # Limit to avoid rate limits
            google_articles = await self._get_google_news_rss(query)
            articles.extend(google_articles)
        
        # 2. NewsAPI.org (if available)
        if self.newsapi_key:
            newsapi_articles = await self._get_newsapi_articles(athlete_name, sport)
            articles.extend(newsapi_articles)
        
        # Deduplicate by URL
        seen_urls = set()
        unique_articles = []
        for article in articles:
            url = article.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_articles.append(article)
        
        return unique_articles[:20]  # Limit to 20 articles
    
    async def _get_google_news_rss(self, query: str) -> List[Dict[str, Any]]:
        """Get articles from Google News RSS"""
        if not FEEDPARSER_AVAILABLE:
            logger.warning(f"{self.crawler_name}: feedparser not available, skipping Google News RSS")
            return []
        
        try:
            await self.rate_limit_async()
            
            # Google News RSS URL
            rss_url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
            
            # Parse RSS feed
            loop = asyncio.get_event_loop()
            feed = await loop.run_in_executor(
                None,
                lambda: feedparser.parse(rss_url)
            )
            
            articles = []
            for entry in feed.entries[:10]:  # Limit to 10 per query
                articles.append({
                    'title': entry.get('title', ''),
                    'url': entry.get('link', ''),
                    'published_date': self._parse_rss_date(entry.get('published', '')),
                    'source': 'google_news',
                    'summary': entry.get('summary', '')
                })
            
            return articles
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Google News RSS failed: {e}")
            return []
    
    async def _get_newsapi_articles(
        self,
        athlete_name: str,
        sport: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get articles from NewsAPI.org"""
        if not self.newsapi_key:
            return []
        
        try:
            await self.rate_limit_async()
            
            import aiohttp
            
            query = f'"{athlete_name}"'
            if sport:
                query += f' {sport}'
            
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': query,
                'apiKey': self.newsapi_key,
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': 10
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = []
                        for article in data.get('articles', []):
                            articles.append({
                                'title': article.get('title', ''),
                                'url': article.get('url', ''),
                                'published_date': self._parse_iso_date(article.get('publishedAt', '')),
                                'source': 'newsapi',
                                'summary': article.get('description', '')
                            })
                        return articles
                    else:
                        logger.warning(f"{self.crawler_name}: NewsAPI returned {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"{self.crawler_name}: NewsAPI failed: {e}")
            return []
    
    async def _extract_events_from_article(
        self,
        text: str,
        athlete_id: uuid.UUID,
        athlete_name: str,
        article: Dict[str, Any]
    ) -> List[tuple]:
        """
        Extract event types from article text
        
        Returns:
            List of (event_type, event_data) tuples
        """
        events = []
        text_lower = text.lower()
        
        # Check for contract extension
        if any(keyword in text_lower for keyword in ['contract extension', 'signed extension', 're-signed']):
            contract_data = await self._extract_contract_details(text, athlete_name)
            if contract_data:
                events.append(('news_contract_extension', {
                    'article_url': article.get('url'),
                    'article_title': article.get('title'),
                    'contract_details': contract_data,
                    'published_date': article.get('published_date', datetime.utcnow().isoformat())
                }))
        
        # Check for trade
        if any(keyword in text_lower for keyword in ['traded', 'trade', 'acquired', 'sent to']):
            trade_data = await self._extract_trade_info(text, athlete_name)
            if trade_data:
                events.append(('news_trade', {
                    'article_url': article.get('url'),
                    'article_title': article.get('title'),
                    'trade_details': trade_data,
                    'published_date': article.get('published_date', datetime.utcnow().isoformat())
                }))
        
        # Check for draft
        if any(keyword in text_lower for keyword in ['drafted', 'draft pick', 'selected in draft']):
            draft_data = await self._extract_draft_info(text, athlete_name)
            if draft_data:
                events.append(('news_draft', {
                    'article_url': article.get('url'),
                    'article_title': article.get('title'),
                    'draft_details': draft_data,
                    'published_date': article.get('published_date', datetime.utcnow().isoformat())
                }))
        
        # Check for performance/news mention
        if any(keyword in text_lower for keyword in ['performance', 'record', 'achievement', 'milestone']):
            events.append(('news_performance', {
                'article_url': article.get('url'),
                'article_title': article.get('title'),
                'published_date': article.get('published_date', datetime.utcnow().isoformat())
            }))
        
        # Check for NIL deal
        if any(keyword in text_lower for keyword in ['nil deal', 'nil partnership', 'nil endorsement']):
            nil_deals = await self._extract_nil_deals(text, athlete_name)
            if nil_deals:
                for deal in nil_deals:
                    events.append(('news_nil_deal', {
                        'article_url': article.get('url'),
                        'article_title': article.get('title'),
                        'deal': deal,
                        'published_date': article.get('published_date', datetime.utcnow().isoformat())
                    }))
        
        # Check for roster change
        if any(keyword in text_lower for keyword in ['roster', 'waived', 'released', 'signed', 'cut']):
            events.append(('news_roster_change', {
                'article_url': article.get('url'),
                'article_title': article.get('title'),
                'published_date': article.get('published_date', datetime.utcnow().isoformat())
            }))
        
        return events
    
    async def _extract_contract_details(
        self,
        text: str,
        athlete_name: str
    ) -> Optional[Dict[str, Any]]:
        """Extract contract details using AI"""
        return await self.extract_with_ai(
            text=text[:2000],
            extraction_type='contract_details',
            context={'athlete_name': athlete_name}
        )
    
    async def _extract_trade_info(
        self,
        text: str,
        athlete_name: str
    ) -> Optional[Dict[str, Any]]:
        """Extract trade information using AI"""
        # Try AI extraction first
        ai_result = await self.extract_with_ai(
            text=text[:2000],
            extraction_type='trade_info',
            context={'athlete_name': athlete_name}
        )
        
        if ai_result:
            return ai_result
        
        # Fallback to regex
        trade_patterns = [
            r'traded.*?to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'acquired.*?by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'sent\s+to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
        ]
        
        for pattern in trade_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return {
                    'to_team': match.group(1),
                    'extracted_method': 'regex'
                }
        
        return None
    
    async def _extract_draft_info(
        self,
        text: str,
        athlete_name: str
    ) -> Optional[Dict[str, Any]]:
        """Extract draft information using AI"""
        return await self.extract_with_ai(
            text=text[:2000],
            extraction_type='draft_info',
            context={'athlete_name': athlete_name}
        )
    
    async def _extract_nil_deals(
        self,
        text: str,
        athlete_name: str
    ) -> List[Dict[str, Any]]:
        """Extract NIL deals using AI"""
        deals = await self.extract_with_ai(
            text=text[:2000],
            extraction_type='nil_deals',
            context={'athlete_name': athlete_name}
        )
        
        if deals and isinstance(deals, list):
            return deals
        return []
    
    def _parse_rss_date(self, date_str: str) -> Optional[datetime]:
        """Parse RSS date string"""
        if not date_str:
            return None
        
        try:
            # feedparser handles this, but we'll try manual parsing too
            if FEEDPARSER_AVAILABLE:
                import feedparser
                parsed = feedparser._parse_date(date_str)
                if parsed:
                    return datetime(*parsed[:6])
        except:
            pass
        
        # Fallback to common formats
        for fmt in ['%a, %d %b %Y %H:%M:%S %z', '%a, %d %b %Y %H:%M:%S %Z']:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        
        return None
    
    def _parse_iso_date(self, date_str: str) -> Optional[datetime]:
        """Parse ISO date string"""
        if not date_str:
            return None
        
        try:
            # Remove timezone info for simplicity
            date_str = date_str.split('+')[0].split('Z')[0]
            return datetime.fromisoformat(date_str)
        except:
            return None
