"""
Sentiment Crawler
Gauges public sentiment around athletes from Reddit and forums
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from gravity.crawlers.base_crawler import BaseCrawler
import os

logger = logging.getLogger(__name__)


class SentimentCrawler(BaseCrawler):
    """
    Crawl Reddit/forums for athlete mentions and sentiment analysis
    """
    
    def __init__(self):
        super().__init__(rate_limit_delay=1.0)  # Reddit API rate limits
        self.reddit_client_id = os.getenv('REDDIT_CLIENT_ID', None)
        self.reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET', None)
        self.reddit_user_agent = os.getenv('REDDIT_USER_AGENT', 'GravityScoreBot/1.0')
        self._reddit_client = None
    
    def get_crawler_name(self) -> str:
        return "sentiment"
    
    def get_supported_sports(self) -> List[str]:
        return ['nfl', 'nba', 'cfb', 'ncaab', 'mlb', 'nhl']
    
    @property
    def reddit_client(self):
        """Lazy initialization of Reddit client"""
        if self._reddit_client is None and self.reddit_client_id:
            try:
                import praw
                self._reddit_client = praw.Reddit(
                    client_id=self.reddit_client_id,
                    client_secret=self.reddit_client_secret,
                    user_agent=self.reddit_user_agent
                )
            except ImportError:
                logger.warning(f"{self.crawler_name}: praw not installed, Reddit crawling disabled")
                self._reddit_client = None
            except Exception as e:
                logger.error(f"{self.crawler_name}: Failed to initialize Reddit client: {e}")
                self._reddit_client = None
        return self._reddit_client
    
    async def crawl(
        self,
        athlete_id: Optional[uuid.UUID] = None,
        athlete_name: Optional[str] = None,
        sport: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Crawl Reddit for athlete mentions and sentiment
        
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
            
            logger.info(f"{self.crawler_name}: Crawling sentiment for {athlete_name} ({sport})")
            
            # Get relevant subreddits for sport
            subreddits = self._get_subreddits_for_sport(sport)
            
            events_created = 0
            errors = []
            sentiment_scores = []
            
            # Search each subreddit
            for subreddit_name in subreddits:
                try:
                    mentions = await self._search_reddit(subreddit_name, athlete_name)
                    
                    for mention in mentions:
                        # Analyze sentiment
                        sentiment = await self._analyze_sentiment(
                            mention.get('title', '') + ' ' + mention.get('body', '')
                        )
                        
                        sentiment_scores.append({
                            'sentiment': sentiment,
                            'upvotes': mention.get('score', 0),
                            'subreddit': subreddit_name
                        })
                        
                        # Store sentiment mention event
                        event_id = await self.store_event(
                            athlete_id=athlete_id,
                            event_type='sentiment_mention',
                            event_data={
                                'platform': 'reddit',
                                'subreddit': subreddit_name,
                                'sentiment': sentiment,
                                'upvotes': mention.get('score', 0),
                                'url': mention.get('url', ''),
                                'title': mention.get('title', ''),
                                'body_preview': mention.get('body', '')[:500]
                            },
                            event_timestamp=self._parse_reddit_timestamp(mention.get('created_utc')),
                            source='reddit'
                        )
                        
                        if event_id:
                            events_created += 1
                            await self.trigger_score_recalculation(athlete_id, 'sentiment_mention')
                
                except Exception as e:
                    error_msg = f"Subreddit {subreddit_name} search failed: {e}"
                    logger.error(f"{self.crawler_name}: {error_msg}")
                    errors.append(error_msg)
            
            # Calculate aggregate sentiment score
            if sentiment_scores:
                aggregate_sentiment = self._calculate_aggregate_sentiment(sentiment_scores)
                
                # Store aggregate sentiment update
                await self._update_sentiment_score(athlete_id, aggregate_sentiment)
            
            return self.create_crawl_result(
                success=True,
                events_created=events_created,
                errors=errors if errors else None,
                metadata={
                    'subreddits_searched': len(subreddits),
                    'mentions_found': len(sentiment_scores),
                    'aggregate_sentiment': aggregate_sentiment if sentiment_scores else None
                }
            )
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Crawl failed: {e}")
            return self.create_crawl_result(
                success=False,
                errors=[str(e)]
            )
    
    def _get_subreddits_for_sport(self, sport: Optional[str]) -> List[str]:
        """Get relevant subreddits for a sport"""
        sport_subreddits = {
            'nfl': ['nfl', 'fantasyfootball'],
            'nba': ['nba', 'fantasybball'],
            'cfb': ['CFB', 'collegefootball'],
            'ncaab': ['CollegeBasketball'],
            'mlb': ['baseball', 'fantasybaseball'],
            'nhl': ['hockey', 'fantasyhockey']
        }
        
        if sport and sport.lower() in sport_subreddits:
            return sport_subreddits[sport.lower()]
        
        # Default to general sports subreddits
        return ['sports', 'nfl', 'nba', 'CFB']
    
    async def _search_reddit(
        self,
        subreddit_name: str,
        athlete_name: str
    ) -> List[Dict[str, Any]]:
        """
        Search Reddit for athlete mentions
        
        Args:
            subreddit_name: Subreddit to search
            athlete_name: Athlete name to search for
        
        Returns:
            List of mention dicts
        """
        if not self.reddit_client:
            logger.debug(f"{self.crawler_name}: Reddit client not available")
            return []
        
        try:
            # Run Reddit search in executor (praw is sync)
            loop = asyncio.get_event_loop()
            mentions = await loop.run_in_executor(
                None,
                self._search_reddit_sync,
                subreddit_name,
                athlete_name
            )
            
            return mentions
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Reddit search failed: {e}")
            return []
    
    def _search_reddit_sync(
        self,
        subreddit_name: str,
        athlete_name: str
    ) -> List[Dict[str, Any]]:
        """Sync Reddit search"""
        mentions = []
        
        try:
            subreddit = self.reddit_client.subreddit(subreddit_name)
            
            # Search for athlete name in subreddit (past week)
            for submission in subreddit.search(
                athlete_name,
                sort='new',
                time_filter='week',
                limit=20
            ):
                mentions.append({
                    'title': submission.title,
                    'body': submission.selftext[:1000] if submission.selftext else '',
                    'score': submission.score,
                    'url': submission.url,
                    'created_utc': submission.created_utc,
                    'subreddit': subreddit_name
                })
        
        except Exception as e:
            logger.error(f"{self.crawler_name}: Reddit sync search failed: {e}")
        
        return mentions
    
    async def _analyze_sentiment(self, text: str) -> str:
        """
        Analyze sentiment of text
        
        Returns:
            'positive', 'negative', or 'neutral'
        """
        # Try VADER sentiment first (if available)
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            analyzer = SentimentIntensityAnalyzer()
            scores = analyzer.polarity_scores(text)
            
            compound = scores['compound']
            if compound >= 0.05:
                return 'positive'
            elif compound <= -0.05:
                return 'negative'
            else:
                return 'neutral'
        except ImportError:
            pass
        
        # Fallback to keyword-based sentiment
        positive_words = ['great', 'amazing', 'excellent', 'best', 'love', 'awesome', 'incredible']
        negative_words = ['terrible', 'awful', 'bad', 'worst', 'hate', 'disappointing', 'poor']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'
    
    def _calculate_aggregate_sentiment(
        self,
        sentiment_scores: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate weighted aggregate sentiment score
        
        Args:
            sentiment_scores: List of sentiment dicts with 'sentiment' and 'upvotes'
        
        Returns:
            Aggregate sentiment score (-1 to 1)
        """
        if not sentiment_scores:
            return 0.0
        
        total_weight = 0
        weighted_sum = 0
        
        for item in sentiment_scores:
            sentiment = item['sentiment']
            upvotes = item.get('upvotes', 0)
            
            # Weight by upvotes (log scale to avoid outliers)
            weight = 1 + (upvotes ** 0.5)
            
            # Convert sentiment to numeric
            if sentiment == 'positive':
                value = 1.0
            elif sentiment == 'negative':
                value = -1.0
            else:
                value = 0.0
            
            weighted_sum += value * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return weighted_sum / total_weight
    
    async def _update_sentiment_score(
        self,
        athlete_id: uuid.UUID,
        sentiment_score: float
    ) -> None:
        """
        Update sentiment score in feature snapshot
        
        Args:
            athlete_id: Athlete UUID
            sentiment_score: Aggregate sentiment score (-1 to 1)
        """
        try:
            # This would update the feature_snapshots table
            # For now, we'll rely on the event processor to handle this
            logger.debug(f"{self.crawler_name}: Sentiment score update queued for {athlete_id}: {sentiment_score:.2f}")
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Failed to update sentiment score: {e}")
    
    def _parse_reddit_timestamp(self, created_utc: Optional[float]) -> datetime:
        """Parse Reddit timestamp (Unix UTC) to datetime"""
        if not created_utc:
            return datetime.utcnow()
        
        try:
            return datetime.utcfromtimestamp(created_utc)
        except:
            return datetime.utcnow()
