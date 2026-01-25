"""
Base Crawler Framework
Abstract base class for all sports information crawlers
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime, date
import logging
import uuid
import asyncio
import time

from gravity.storage import get_storage_manager
from gravity.db.models import AthleteEvent
from gravity.ai.extractor import AIExtractor

logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """
    Abstract base class for all crawlers
    
    Provides common functionality:
    - Async execution support
    - Storage integration
    - AI extraction
    - Firecrawl integration
    - Event emission for score recalculation
    - Rate limiting and error handling
    - Provenance tracking
    """
    
    def __init__(self, rate_limit_delay: float = 1.0):
        """
        Initialize base crawler
        
        Args:
            rate_limit_delay: Seconds between requests (default: 1.0)
        """
        self.storage = get_storage_manager()
        self.ai_extractor = AIExtractor()
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = None
        self.crawler_name = self.get_crawler_name()
        
        # Initialize Firecrawl client (lazy)
        self._firecrawl_client = None
        
        logger.info(f"Initialized {self.crawler_name} crawler")
    
    @abstractmethod
    def get_crawler_name(self) -> str:
        """
        Return the crawler name (e.g., 'news_article', 'trade')
        
        Returns:
            Crawler name string
        """
        pass
    
    @abstractmethod
    def get_supported_sports(self) -> List[str]:
        """
        Return list of sports this crawler supports
        
        Returns:
            List of sport identifiers (e.g., ['nfl', 'nba', 'cfb'])
        """
        pass
    
    @abstractmethod
    async def crawl(
        self,
        athlete_id: Optional[uuid.UUID] = None,
        athlete_name: Optional[str] = None,
        sport: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Main crawl method - must be implemented by subclasses
        
        Args:
            athlete_id: Optional athlete UUID
            athlete_name: Optional athlete name
            sport: Optional sport identifier
            **kwargs: Additional crawler-specific parameters
        
        Returns:
            Dict with crawl results including events created
        """
        pass
    
    # ========================================================================
    # FIRECRAWL INTEGRATION
    # ========================================================================
    
    @property
    def firecrawl_client(self):
        """Lazy initialization of Firecrawl client"""
        if self._firecrawl_client is None:
            try:
                from gravity.firecrawl_sdk import fc
                self._firecrawl_client = fc
            except Exception as e:
                logger.warning(f"Firecrawl not available: {e}")
                self._firecrawl_client = None
        return self._firecrawl_client
    
    async def scrape_with_firecrawl(
        self,
        url: str,
        max_age_ms: int = 600000,
        timeout: int = 120000
    ) -> Optional[Dict[str, Any]]:
        """
        Scrape URL using Firecrawl
        
        Args:
            url: URL to scrape
            max_age_ms: Maximum age of cached content in milliseconds
            timeout: Request timeout in milliseconds
        
        Returns:
            Scraped content dict or None if failed
        """
        if not self.firecrawl_client:
            logger.warning(f"{self.crawler_name}: Firecrawl not available")
            return None
        
        try:
            self.rate_limit()
            
            # Firecrawl scrape is sync, run in executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.firecrawl_client.scrape(
                    url=url,
                    only_main_content=True,
                    timeout=timeout,
                    maxAge=max_age_ms
                )
            )
            
            return result
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Firecrawl scrape failed for {url}: {e}")
            return None
    
    # ========================================================================
    # AI EXTRACTION
    # ========================================================================
    
    async def extract_with_ai(
        self,
        text: str,
        extraction_type: str,
        context: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Extract structured data using AI
        
        Args:
            text: Text to extract from
            extraction_type: Type of extraction (nil_deals, contract_details, etc.)
            context: Additional context (athlete_name, etc.)
        
        Returns:
            Extracted structured data or None
        """
        try:
            # Run AI extraction in executor (it's sync)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.ai_extractor.extract(text, extraction_type, context)
            )
            return result
        except Exception as e:
            logger.error(f"{self.crawler_name}: AI extraction failed: {e}")
            return None
    
    # ========================================================================
    # EVENT STORAGE
    # ========================================================================
    
    async def store_event(
        self,
        athlete_id: uuid.UUID,
        event_type: str,
        event_data: Dict[str, Any],
        event_timestamp: Optional[datetime] = None,
        source: Optional[str] = None
    ) -> Optional[uuid.UUID]:
        """
        Store event in athlete_events table
        
        Args:
            athlete_id: Athlete UUID
            event_type: Event type (e.g., 'trade_completed', 'injury')
            event_data: Event data dict (stored as JSONB)
            event_timestamp: Optional timestamp (defaults to now)
            source: Optional source identifier
        
        Returns:
            Event UUID if successful, None otherwise
        """
        try:
            if not event_timestamp:
                event_timestamp = datetime.utcnow()
            
            if not source:
                source = self.crawler_name
            
            # Store event in database
            loop = asyncio.get_event_loop()
            event_id = await loop.run_in_executor(
                None,
                self._store_event_sync,
                athlete_id,
                event_type,
                event_data,
                event_timestamp,
                source
            )
            
            logger.debug(f"{self.crawler_name}: Stored event {event_type} for athlete {athlete_id}")
            return event_id
            
        except Exception as e:
            logger.error(f"{self.crawler_name}: Failed to store event: {e}")
            return None
    
    def _store_event_sync(
        self,
        athlete_id: uuid.UUID,
        event_type: str,
        event_data: Dict[str, Any],
        event_timestamp: datetime,
        source: str
    ) -> uuid.UUID:
        """Sync version of store_event for executor"""
        with self.storage.get_session() as session:
            event = AthleteEvent(
                athlete_id=athlete_id,
                event_type=event_type,
                event_timestamp=event_timestamp,
                source=source,
                raw_data=event_data,
                processed=False
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            return event.event_id
    
    async def trigger_score_recalculation(
        self,
        athlete_id: uuid.UUID,
        event_type: str
    ) -> None:
        """
        Trigger score recalculation for affected components
        
        This emits a signal that will be picked up by the event processor
        
        Args:
            athlete_id: Athlete UUID
            event_type: Event type that triggered recalculation
        """
        try:
            # Import here to avoid circular dependencies
            from gravity.crawlers.event_processor import EventProcessor
            
            processor = EventProcessor()
            await processor.process_new_event_by_type(athlete_id, event_type)
            
            logger.debug(f"{self.crawler_name}: Triggered score recalculation for {athlete_id}")
            
        except ImportError:
            # Event processor not yet implemented, log and continue
            logger.debug(f"{self.crawler_name}: Event processor not available, skipping recalculation trigger")
        except Exception as e:
            logger.error(f"{self.crawler_name}: Failed to trigger score recalculation: {e}")
    
    # ========================================================================
    # RATE LIMITING
    # ========================================================================
    
    def rate_limit(self):
        """Apply rate limiting between requests"""
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - elapsed
                time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    async def rate_limit_async(self):
        """Async version of rate limiting"""
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - elapsed
                await asyncio.sleep(sleep_time)
        self.last_request_time = time.time()
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def find_athlete_by_name(
        self,
        athlete_name: str,
        sport: Optional[str] = None
    ) -> Optional[uuid.UUID]:
        """
        Find athlete UUID by name (fuzzy matching)
        
        Args:
            athlete_name: Athlete name to search for
            sport: Optional sport filter
        
        Returns:
            Athlete UUID if found, None otherwise
        """
        try:
            with self.storage.get_session() as session:
                from gravity.db.models import Athlete
                from sqlalchemy import or_
                
                # Try exact match first
                query = session.query(Athlete).filter(
                    Athlete.canonical_name.ilike(f"%{athlete_name}%")
                )
                
                if sport:
                    query = query.filter(Athlete.sport == sport)
                
                athlete = query.first()
                
                if athlete:
                    return athlete.athlete_id
                
                return None
                
        except Exception as e:
            logger.error(f"{self.crawler_name}: Failed to find athlete {athlete_name}: {e}")
            return None
    
    def get_athlete_info(self, athlete_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        Get athlete information from database
        
        Args:
            athlete_id: Athlete UUID
        
        Returns:
            Athlete info dict or None
        """
        try:
            with self.storage.get_session() as session:
                from gravity.db.models import Athlete
                
                athlete = session.query(Athlete).filter(
                    Athlete.athlete_id == athlete_id
                ).first()
                
                if athlete:
                    return {
                        'athlete_id': str(athlete.athlete_id),
                        'name': athlete.canonical_name,
                        'sport': athlete.sport,
                        'school': athlete.school,
                        'position': athlete.position
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"{self.crawler_name}: Failed to get athlete info: {e}")
            return None
    
    def create_crawl_result(
        self,
        success: bool,
        events_created: int = 0,
        errors: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create standardized crawl result dict
        
        Args:
            success: Whether crawl was successful
            events_created: Number of events created
            errors: List of error messages
            metadata: Additional metadata
        
        Returns:
            Standardized result dict
        """
        result = {
            'crawler': self.crawler_name,
            'success': success,
            'events_created': events_created,
            'timestamp': datetime.utcnow().isoformat(),
            'errors': errors or [],
            'metadata': metadata or {}
        }
        
        return result


class CrawlerError(Exception):
    """Base exception for crawler errors"""
    pass


class CrawlerRateLimitError(CrawlerError):
    """Raised when rate limit is exceeded"""
    pass


class CrawlerDataNotFoundError(CrawlerError):
    """Raised when expected data is not found"""
    pass
