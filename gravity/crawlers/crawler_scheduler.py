"""
Crawler Scheduler
Schedules crawlers with cron jobs and event-driven triggers
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, time as dt_time
from enum import Enum

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logger.warning("APScheduler not available - scheduling disabled")

from gravity.crawlers.crawler_orchestrator import CrawlerOrchestrator

logger = logging.getLogger(__name__)


class ScheduleInterval(Enum):
    """Schedule interval types"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    CUSTOM = "custom"


class CrawlerScheduler:
    """
    Schedules crawlers with cron jobs and event-driven triggers
    """
    
    def __init__(self):
        if not APSCHEDULER_AVAILABLE:
            logger.warning("APScheduler not available - scheduler will use manual triggers only")
            self.scheduler = None
        else:
            self.scheduler = AsyncIOScheduler()
            self.scheduler.start()
        
        self.orchestrator = CrawlerOrchestrator()
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        logger.info("Crawler scheduler initialized")
    
    def schedule_crawler(
        self,
        crawler_name: str,
        interval: str = 'daily',
        time: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Schedule a crawler to run at intervals
        
        Args:
            crawler_name: Crawler name
            interval: Interval string ('1h', 'daily', 'weekly', etc.)
            time: Optional time string for daily schedules (e.g., '02:00')
            **kwargs: Additional crawler parameters
        
        Returns:
            True if scheduled successfully
        """
        if not self.scheduler:
            logger.warning("Scheduler not available - cannot schedule crawler")
            return False
        
        try:
            # Parse interval
            if interval == 'daily':
                if time:
                    hour, minute = map(int, time.split(':'))
                    trigger = CronTrigger(hour=hour, minute=minute)
                else:
                    trigger = CronTrigger(hour=2, minute=0)  # Default 2 AM
            elif interval.endswith('h'):
                hours = int(interval[:-1])
                trigger = IntervalTrigger(hours=hours)
            elif interval.endswith('m'):
                minutes = int(interval[:-1])
                trigger = IntervalTrigger(minutes=minutes)
            else:
                logger.error(f"Unknown interval format: {interval}")
                return False
            
            # Schedule job
            self.scheduler.add_job(
                self._run_scheduled_crawler,
                trigger=trigger,
                args=[crawler_name],
                kwargs=kwargs,
                id=f"crawler_{crawler_name}",
                replace_existing=True
            )
            
            logger.info(f"Scheduled crawler {crawler_name} with interval {interval}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to schedule crawler {crawler_name}: {e}")
            return False
    
    async def _run_scheduled_crawler(
        self,
        crawler_name: str,
        **kwargs
    ) -> None:
        """Run a scheduled crawler"""
        try:
            logger.info(f"Running scheduled crawler: {crawler_name}")
            
            # For scheduled runs, typically run league-wide
            if crawler_name in ['injury_report', 'game_stats', 'trade']:
                # These crawlers support league-wide crawling
                sport = kwargs.get('sport', 'nfl')  # Default sport
                result = await self.orchestrator.run_crawler(
                    crawler_name,
                    sport=sport,
                    **kwargs
                )
            else:
                # Other crawlers need athlete_id or athlete_name
                # For scheduled runs, might need to iterate over athletes
                logger.debug(f"Crawler {crawler_name} requires athlete_id for scheduled runs")
            
        except Exception as e:
            logger.error(f"Scheduled crawler execution failed: {e}")
    
    def register_event_handler(
        self,
        event_type: str,
        handler: Callable
    ) -> None:
        """
        Register an event-driven handler
        
        Args:
            event_type: Event type (e.g., 'athlete_created', 'game_completed')
            handler: Async handler function
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
        logger.info(f"Registered event handler for {event_type}")
    
    async def trigger_event(
        self,
        event_type: str,
        **kwargs
    ) -> None:
        """
        Trigger an event-driven crawler execution
        
        Args:
            event_type: Event type
            **kwargs: Event data
        """
        handlers = self.event_handlers.get(event_type, [])
        
        if not handlers:
            logger.debug(f"No handlers registered for event type: {event_type}")
            return
        
        logger.info(f"Triggering event handlers for {event_type}")
        
        for handler in handlers:
            try:
                await handler(**kwargs)
            except Exception as e:
                logger.error(f"Event handler failed for {event_type}: {e}")
    
    def setup_default_schedules(self) -> None:
        """Set up default crawler schedules"""
        if not self.scheduler:
            logger.warning("Scheduler not available - cannot set up default schedules")
            return
        
        # Daily at 2 AM - News, Brand Partnerships
        self.schedule_crawler('news_article', interval='daily', time='02:00')
        self.schedule_crawler('brand_partnership', interval='daily', time='02:00')
        
        # Every 6 hours - Injuries, Sentiment
        self.schedule_crawler('injury_report', interval='6h')
        self.schedule_crawler('sentiment', interval='6h')
        
        # Hourly - Transfer Portal (time-sensitive)
        self.schedule_crawler('transfer_portal', interval='1h')
        
        # Every 2-4 hours during season - Game Stats
        self.schedule_crawler('game_stats', interval='2h')
        
        # Every 4 hours - Social Media
        self.schedule_crawler('social_media', interval='4h')
        
        # Trade Crawler - Variable frequency
        self.schedule_crawler('trade', interval='2h')
        
        logger.info("Default crawler schedules configured")
    
    def setup_event_handlers(self) -> None:
        """Set up default event-driven handlers"""
        # Handler for new athlete created
        async def on_athlete_created(athlete_id: uuid.UUID):
            await self.orchestrator.run_crawler('brand_partnership', athlete_id=athlete_id)
            await self.orchestrator.run_crawler('social_media', athlete_id=athlete_id)
        
        self.register_event_handler('athlete_created', on_athlete_created)
        
        # Handler for game completion
        async def on_game_completed(game_id: str, athlete_ids: List[uuid.UUID], sport: str):
            for athlete_id in athlete_ids:
                await self.orchestrator.run_crawler('game_stats', athlete_id=athlete_id, sport=sport)
        
        self.register_event_handler('game_completed', on_game_completed)
        
        # Handler for trade deadline
        async def on_trade_deadline(sport: str):
            await self.orchestrator.run_crawler('trade', sport=sport, high_frequency=True)
        
        self.register_event_handler('trade_deadline_started', on_trade_deadline)
        
        logger.info("Default event handlers configured")
    
    def get_scheduled_jobs(self) -> List[Dict[str, Any]]:
        """
        Get list of scheduled jobs
        
        Returns:
            List of job dicts
        """
        if not self.scheduler:
            return []
        
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        
        return jobs
    
    def remove_job(self, job_id: str) -> bool:
        """
        Remove a scheduled job
        
        Args:
            job_id: Job ID
        
        Returns:
            True if removed successfully
        """
        if not self.scheduler:
            return False
        
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed scheduled job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            return False
    
    def shutdown(self) -> None:
        """Shutdown scheduler"""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("Scheduler shut down")
