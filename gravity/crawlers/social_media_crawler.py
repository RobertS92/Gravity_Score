"""
Social Media Crawler
Tracks athlete social engagement and brand mentions across Instagram, Twitter/X, TikTok
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import os

from gravity.crawlers.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class SocialMediaCrawler(BaseCrawler):
    """
    Crawl athlete social media posts for brand mentions and engagement tracking
    """
    
    def __init__(self):
        super().__init__(rate_limit_delay=1.0)  # Social APIs can be rate-limited
        self.apify_api_key = os.getenv('APIFY_API_KEY', None)
        self.rapidapi_key = os.getenv('RAPIDAPI_KEY', None)
    
    def get_crawler_name(self) -> str:
        return "social_media"
    
    def get_supported_sports(self) -> List[str]:
        return ['nfl', 'nba', 'cfb', 'ncaab', 'mlb', 'nhl', 'wnba']
    
    async def crawl(
        self,
        athlete_id: Optional[uuid.UUID] = None,
        athlete_name: Optional[str] = None,
        sport: Optional[str] = None,
        instagram_handle: Optional[str] = None,
        twitter_handle: Optional[str] = None,
        tiktok_handle: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Crawl social media for an athlete
        
        Args:
            athlete_id: Optional athlete UUID
            athlete_name: Athlete name (required if athlete_id not provided)
            sport: Optional sport identifier
            instagram_handle: Optional Instagram handle
            twitter_handle: Optional Twitter/X handle
            tiktok_handle: Optional TikTok handle
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
            
            logger.info(f"{self.crawler_name}: Crawling social media for {athlete_name}")
            
            events_created = 0
            errors = []
            
            # Crawl Instagram if handle provided
            if instagram_handle:
                instagram_events = await self._crawl_instagram(athlete_id, instagram_handle)
                events_created += len(instagram_events)
            
            # Crawl Twitter/X if handle provided
            if twitter_handle:
                twitter_events = await self._crawl_twitter(athlete_id, twitter_handle)
                events_created += len(twitter_events)
            
            # Crawl TikTok if handle provided
            if tiktok_handle:
                tiktok_events = await self._crawl_tiktok(athlete_id, tiktok_handle)
                events_created += len(tiktok_events)
            
            # If no handles provided, try to find them from athlete metadata
            if not (instagram_handle or twitter_handle or tiktok_handle):
                # Try to get handles from database metadata
                handles = self._get_social_handles_from_db(athlete_id)
                
                if handles.get('instagram'):
                    instagram_events = await self._crawl_instagram(athlete_id, handles['instagram'])
                    events_created += len(instagram_events)
                
                if handles.get('twitter'):
                    twitter_events = await self._crawl_twitter(athlete_id, handles['twitter'])
                    events_created += len(twitter_events)
            
            return self.create_crawl_result(
                success=True,
                events_created=events_created,
                errors=errors if errors else None,
                metadata={
                    'platforms_crawled': [
                        p for p in ['instagram', 'twitter', 'tiktok']
                        if locals().get(f'{p}_handle') or handles.get(p)
                    ]
                }
            )
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Crawl failed: {e}")
            return self.create_crawl_result(
                success=False,
                errors=[str(e)]
            )
    
    async def _crawl_instagram(
        self,
        athlete_id: uuid.UUID,
        instagram_handle: str
    ) -> List[uuid.UUID]:
        """
        Crawl Instagram posts for brand mentions
        
        Args:
            athlete_id: Athlete UUID
            instagram_handle: Instagram handle (without @)
        
        Returns:
            List of event IDs created
        """
        event_ids = []
        
        try:
            # Try Apify first (free tier available)
            if self.apify_api_key:
                posts = await self._get_instagram_posts_apify(instagram_handle)
            else:
                # Fallback to public scraper or nitter-like service
                posts = await self._get_instagram_posts_public(instagram_handle)
            
            for post in posts[:20]:  # Limit to 20 recent posts
                # Detect brand mentions
                brands = self._detect_brands(post.get('caption', ''))
                
                if brands:
                    # Determine if it's a partnership vs casual mention
                    is_partnership = await self._is_brand_partnership(
                        post.get('caption', ''),
                        brands
                    )
                    
                    event_type = 'social_nil_partnership' if is_partnership else 'social_brand_mention'
                    
                    event_id = await self.store_event(
                        athlete_id=athlete_id,
                        event_type=event_type,
                        event_data={
                            'platform': 'instagram',
                            'post_url': post.get('url', ''),
                            'post_id': post.get('id', ''),
                            'caption': post.get('caption', ''),
                            'brands': brands,
                            'engagement': {
                                'likes': post.get('likes', 0),
                                'comments': post.get('comments', 0),
                                'total': post.get('likes', 0) + post.get('comments', 0)
                            },
                            'posted_at': post.get('timestamp', datetime.utcnow().isoformat()),
                            'is_partnership': is_partnership
                        },
                        event_timestamp=self._parse_timestamp(post.get('timestamp')),
                        source='instagram'
                    )
                    
                    if event_id:
                        event_ids.append(event_id)
                        await self.trigger_score_recalculation(athlete_id, event_type)
                
                # Check for engagement spike
                engagement = post.get('likes', 0) + post.get('comments', 0)
                if engagement > 10000:  # Threshold for "spike"
                    event_id = await self.store_event(
                        athlete_id=athlete_id,
                        event_type='social_engagement_spike',
                        event_data={
                            'platform': 'instagram',
                            'post_url': post.get('url', ''),
                            'engagement': engagement,
                            'posted_at': post.get('timestamp', datetime.utcnow().isoformat())
                        },
                        event_timestamp=self._parse_timestamp(post.get('timestamp')),
                        source='instagram'
                    )
                    
                    if event_id:
                        event_ids.append(event_id)
                        await self.trigger_score_recalculation(athlete_id, 'social_engagement_spike')
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Instagram crawl failed: {e}")
        
        return event_ids
    
    async def _crawl_twitter(
        self,
        athlete_id: uuid.UUID,
        twitter_handle: str
    ) -> List[uuid.UUID]:
        """
        Crawl Twitter/X posts for brand mentions
        
        Args:
            athlete_id: Athlete UUID
            twitter_handle: Twitter handle (without @)
        
        Returns:
            List of event IDs created
        """
        event_ids = []
        
        try:
            # Use nitter.net public scraper (no API key needed)
            posts = await self._get_twitter_posts_public(twitter_handle)
            
            for post in posts[:20]:  # Limit to 20 recent posts
                # Detect brand mentions
                brands = self._detect_brands(post.get('text', ''))
                
                if brands:
                    is_partnership = await self._is_brand_partnership(
                        post.get('text', ''),
                        brands
                    )
                    
                    event_type = 'social_nil_partnership' if is_partnership else 'social_brand_mention'
                    
                    event_id = await self.store_event(
                        athlete_id=athlete_id,
                        event_type=event_type,
                        event_data={
                            'platform': 'twitter',
                            'post_url': post.get('url', ''),
                            'post_id': post.get('id', ''),
                            'text': post.get('text', ''),
                            'brands': brands,
                            'engagement': {
                                'likes': post.get('likes', 0),
                                'retweets': post.get('retweets', 0),
                                'replies': post.get('replies', 0),
                                'total': post.get('likes', 0) + post.get('retweets', 0) + post.get('replies', 0)
                            },
                            'posted_at': post.get('timestamp', datetime.utcnow().isoformat()),
                            'is_partnership': is_partnership
                        },
                        event_timestamp=self._parse_timestamp(post.get('timestamp')),
                        source='twitter'
                    )
                    
                    if event_id:
                        event_ids.append(event_id)
                        await self.trigger_score_recalculation(athlete_id, event_type)
                
                # Check for engagement spike
                engagement = post.get('likes', 0) + post.get('retweets', 0) + post.get('replies', 0)
                if engagement > 5000:  # Threshold for Twitter
                    event_id = await self.store_event(
                        athlete_id=athlete_id,
                        event_type='social_engagement_spike',
                        event_data={
                            'platform': 'twitter',
                            'post_url': post.get('url', ''),
                            'engagement': engagement,
                            'posted_at': post.get('timestamp', datetime.utcnow().isoformat())
                        },
                        event_timestamp=self._parse_timestamp(post.get('timestamp')),
                        source='twitter'
                    )
                    
                    if event_id:
                        event_ids.append(event_id)
                        await self.trigger_score_recalculation(athlete_id, 'social_engagement_spike')
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Twitter crawl failed: {e}")
        
        return event_ids
    
    async def _crawl_tiktok(
        self,
        athlete_id: uuid.UUID,
        tiktok_handle: str
    ) -> List[uuid.UUID]:
        """
        Crawl TikTok posts for brand mentions
        
        Args:
            athlete_id: Athlete UUID
            tiktok_handle: TikTok handle (without @)
        
        Returns:
            List of event IDs created
        """
        event_ids = []
        
        try:
            # TikTok scraping is more limited, use public profile pages
            posts = await self._get_tiktok_posts_public(tiktok_handle)
            
            for post in posts[:10]:  # Limit to 10 recent posts
                brands = self._detect_brands(post.get('description', ''))
                
                if brands:
                    event_id = await self.store_event(
                        athlete_id=athlete_id,
                        event_type='social_brand_mention',
                        event_data={
                            'platform': 'tiktok',
                            'post_url': post.get('url', ''),
                            'description': post.get('description', ''),
                            'brands': brands,
                            'engagement': {
                                'likes': post.get('likes', 0),
                                'comments': post.get('comments', 0),
                                'shares': post.get('shares', 0),
                                'total': post.get('likes', 0) + post.get('comments', 0) + post.get('shares', 0)
                            },
                            'posted_at': post.get('timestamp', datetime.utcnow().isoformat())
                        },
                        event_timestamp=self._parse_timestamp(post.get('timestamp')),
                        source='tiktok'
                    )
                    
                    if event_id:
                        event_ids.append(event_id)
                        await self.trigger_score_recalculation(athlete_id, 'social_brand_mention')
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: TikTok crawl failed: {e}")
        
        return event_ids
    
    async def _get_instagram_posts_apify(self, handle: str) -> List[Dict[str, Any]]:
        """Get Instagram posts using Apify actor"""
        if not self.apify_api_key:
            return []
        
        try:
            import aiohttp
            
            url = "https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items"
            headers = {
                'Authorization': f'Bearer {self.apify_api_key}',
                'Content-Type': 'application/json'
            }
            data = {
                'usernames': [handle],
                'resultsLimit': 20
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('data', [])
                    else:
                        logger.warning(f"{self.crawler_name}: Apify returned {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"{self.crawler_name}: Apify Instagram failed: {e}")
            return []
    
    async def _get_instagram_posts_public(self, handle: str) -> List[Dict[str, Any]]:
        """Get Instagram posts using public scraper (fallback)"""
        # This would use a public Instagram scraper or Firecrawl
        # For now, return empty list - can be implemented later
        logger.debug(f"{self.crawler_name}: Public Instagram scraper not implemented")
        return []
    
    async def _get_twitter_posts_public(self, handle: str) -> List[Dict[str, Any]]:
        """Get Twitter posts using nitter.net or similar public scraper"""
        try:
            # Use nitter.net public instance
            nitter_url = f"https://nitter.net/{handle}"
            
            # Scrape with Firecrawl
            content = await self.scrape_with_firecrawl(nitter_url)
            
            if content:
                # Parse tweets from HTML (simplified - would need proper parsing)
                # For now, return empty - can be enhanced with proper HTML parsing
                logger.debug(f"{self.crawler_name}: Twitter public scraper needs HTML parsing")
                return []
            
            return []
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Twitter public scraper failed: {e}")
            return []
    
    async def _get_tiktok_posts_public(self, handle: str) -> List[Dict[str, Any]]:
        """Get TikTok posts using public scraper"""
        # TikTok scraping is more complex, return empty for now
        logger.debug(f"{self.crawler_name}: TikTok public scraper not implemented")
        return []
    
    def _detect_brands(self, text: str) -> List[str]:
        """
        Detect brand mentions in text
        
        Args:
            text: Text to analyze
        
        Returns:
            List of brand names found
        """
        # Common sports brand list
        brands = [
            'nike', 'adidas', 'jordan', 'under armour', 'puma', 'new balance',
            'gatorade', 'powerade', 'body armor', 'red bull', 'monster',
            'ea sports', '2k sports', 'madden', 'fifa',
            'state farm', 'geico', 'progressive', 'allstate',
            'apple', 'samsung', 'beats', 'sony',
            'mcdonalds', 'subway', 'chipotle', 'papa johns',
            'nfl', 'nba', 'espn', 'fox sports'
        ]
        
        text_lower = text.lower()
        found_brands = []
        
        for brand in brands:
            if brand in text_lower:
                found_brands.append(brand.title())
        
        return found_brands
    
    async def _is_brand_partnership(
        self,
        text: str,
        brands: List[str]
    ) -> bool:
        """
        Determine if brand mention is a partnership vs casual reference
        
        Uses AI to analyze context
        
        Args:
            text: Post text
            brands: List of brands mentioned
        
        Returns:
            True if appears to be partnership, False otherwise
        """
        # Keywords that suggest partnership
        partnership_keywords = [
            'partner', 'sponsor', 'endorsement', 'ambassador',
            'proud to', 'excited to', 'team', 'official',
            'ad', 'advertisement', 'sponsored', 'paid partnership'
        ]
        
        text_lower = text.lower()
        
        # Check for partnership keywords
        if any(keyword in text_lower for keyword in partnership_keywords):
            return True
        
        # Check for hashtags that suggest partnership
        if '#ad' in text_lower or '#sponsored' in text_lower or '#partner' in text_lower:
            return True
        
        # Use AI for ambiguous cases
        if len(brands) > 0:
            ai_result = await self.extract_with_ai(
                text=text[:500],
                extraction_type='brand_partnerships',
                context={'brands': brands}
            )
            
            if ai_result and isinstance(ai_result, list):
                for item in ai_result:
                    if item.get('status') in ['active', 'announced']:
                        return True
        
        return False
    
    def _get_social_handles_from_db(self, athlete_id: uuid.UUID) -> Dict[str, str]:
        """Get social handles from athlete metadata"""
        try:
            athlete_info = self.get_athlete_info(athlete_id)
            if athlete_info:
                metadata = athlete_info.get('metadata', {})
                return {
                    'instagram': metadata.get('instagram_handle'),
                    'twitter': metadata.get('twitter_handle'),
                    'tiktok': metadata.get('tiktok_handle')
                }
        except:
            pass
        return {}
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> datetime:
        """Parse timestamp string to datetime"""
        if not timestamp_str:
            return datetime.utcnow()
        
        if isinstance(timestamp_str, datetime):
            return timestamp_str
        
        try:
            # Try ISO format
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            return datetime.utcnow()
