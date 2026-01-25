"""
Crawler Orchestrator
Coordinates all 8 crawlers with scheduling and event-driven triggers
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from gravity.crawlers.base_crawler import BaseCrawler
from gravity.crawlers.news_article_crawler import NewsArticleCrawler
from gravity.crawlers.social_media_crawler import SocialMediaCrawler
from gravity.crawlers.transfer_portal_crawler import TransferPortalCrawler
from gravity.crawlers.sentiment_crawler import SentimentCrawler
from gravity.crawlers.injury_report_crawler import InjuryReportCrawler
from gravity.crawlers.brand_partnership_crawler import BrandPartnershipCrawler
from gravity.crawlers.game_stats_crawler import GameStatsCrawler
from gravity.crawlers.trade_crawler import TradeCrawler

logger = logging.getLogger(__name__)


class CrawlerOrchestrator:
    """
    Orchestrates execution of all crawlers
    """
    
    def __init__(self):
        """Initialize orchestrator with all crawlers"""
        self.crawlers = {
            'news_article': NewsArticleCrawler(),
            'social_media': SocialMediaCrawler(),
            'transfer_portal': TransferPortalCrawler(),
            'sentiment': SentimentCrawler(),
            'injury_report': InjuryReportCrawler(),
            'brand_partnership': BrandPartnershipCrawler(),
            'game_stats': GameStatsCrawler(),
            'trade': TradeCrawler()
        }
        
        logger.info(f"Crawler orchestrator initialized with {len(self.crawlers)} crawlers")
    
    async def run_all_crawlers(
        self,
        athlete_id: uuid.UUID,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run all crawlers for an athlete
        
        Args:
            athlete_id: Athlete UUID
            **kwargs: Additional parameters to pass to crawlers
        
        Returns:
            Aggregated results dict
        """
        logger.info(f"Running all crawlers for athlete {athlete_id}")
        
        results = {
            'athlete_id': str(athlete_id),
            'timestamp': datetime.utcnow().isoformat(),
            'crawlers': {},
            'summary': {
                'total_events_created': 0,
                'crawlers_successful': 0,
                'crawlers_failed': 0,
                'errors': []
            }
        }
        
        # Run all crawlers in parallel
        tasks = []
        crawler_names = []
        
        for name, crawler in self.crawlers.items():
            task = crawler.crawl(athlete_id=athlete_id, **kwargs)
            tasks.append(task)
            crawler_names.append(name)
        
        # Wait for all to complete
        crawler_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for name, result in zip(crawler_names, crawler_results):
            if isinstance(result, Exception):
                logger.error(f"Crawler {name} failed with exception: {result}")
                results['crawlers'][name] = {
                    'success': False,
                    'error': str(result)
                }
                results['summary']['crawlers_failed'] += 1
                results['summary']['errors'].append(f"{name}: {str(result)}")
            elif result and result.get('success'):
                results['crawlers'][name] = result
                results['summary']['total_events_created'] += result.get('events_created', 0)
                results['summary']['crawlers_successful'] += 1
            else:
                results['crawlers'][name] = result or {'success': False}
                results['summary']['crawlers_failed'] += 1
                if result and result.get('errors'):
                    results['summary']['errors'].extend(result['errors'])
        
        logger.info(f"Crawler execution complete: {results['summary']['crawlers_successful']}/{len(self.crawlers)} successful, "
                   f"{results['summary']['total_events_created']} events created")
        
        return results
    
    async def run_crawler(
        self,
        name: str,
        athlete_id: Optional[uuid.UUID] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run a specific crawler
        
        Args:
            name: Crawler name
            athlete_id: Optional athlete UUID
            **kwargs: Additional parameters
        
        Returns:
            Crawler result dict
        """
        if name not in self.crawlers:
            return {
                'success': False,
                'error': f"Unknown crawler: {name}",
                'available_crawlers': list(self.crawlers.keys())
            }
        
        crawler = self.crawlers[name]
        return await crawler.crawl(athlete_id=athlete_id, **kwargs)
    
    async def run_sport_crawlers(
        self,
        sport: str,
        athlete_ids: List[uuid.UUID],
        crawler_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run crawlers for multiple athletes in a sport
        
        Args:
            sport: Sport identifier
            athlete_ids: List of athlete UUIDs
            crawler_names: Optional list of crawler names (if None, runs all)
        
        Returns:
            Aggregated results dict
        """
        logger.info(f"Running {sport} crawlers for {len(athlete_ids)} athletes")
        
        if crawler_names is None:
            crawler_names = list(self.crawlers.keys())
        
        # Filter crawlers that support this sport
        supported_crawlers = {
            name: crawler
            for name, crawler in self.crawlers.items()
            if name in crawler_names and sport in crawler.get_supported_sports()
        }
        
        results = {
            'sport': sport,
            'athletes_processed': 0,
            'total_events_created': 0,
            'crawlers_run': list(supported_crawlers.keys()),
            'errors': []
        }
        
        # Process athletes in batches (to avoid overwhelming APIs)
        batch_size = 10
        for i in range(0, len(athlete_ids), batch_size):
            batch = athlete_ids[i:i+batch_size]
            
            # Run crawlers for batch
            batch_tasks = []
            for athlete_id in batch:
                for name, crawler in supported_crawlers.items():
                    batch_tasks.append(crawler.crawl(athlete_id=athlete_id, sport=sport))
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Aggregate results
            for result in batch_results:
                if isinstance(result, Exception):
                    results['errors'].append(str(result))
                elif result and result.get('success'):
                    results['total_events_created'] += result.get('events_created', 0)
                    results['athletes_processed'] += 1
        
        logger.info(f"Sport crawl complete: {results['athletes_processed']}/{len(athlete_ids)} athletes, "
                   f"{results['total_events_created']} events created")
        
        return results
    
    def get_crawler_status(self) -> Dict[str, Any]:
        """
        Get status of all crawlers
        
        Returns:
            Status dict
        """
        status = {
            'crawlers': {},
            'total_crawlers': len(self.crawlers),
            'supported_sports': {}
        }
        
        for name, crawler in self.crawlers.items():
            status['crawlers'][name] = {
                'name': crawler.get_crawler_name(),
                'supported_sports': crawler.get_supported_sports(),
                'rate_limit_delay': crawler.rate_limit_delay
            }
            
            # Aggregate supported sports
            for sport in crawler.get_supported_sports():
                if sport not in status['supported_sports']:
                    status['supported_sports'][sport] = []
                status['supported_sports'][sport].append(name)
        
        return status
    
    def get_crawler(self, name: str) -> Optional[BaseCrawler]:
        """
        Get a crawler instance by name
        
        Args:
            name: Crawler name
        
        Returns:
            Crawler instance or None
        """
        return self.crawlers.get(name)
