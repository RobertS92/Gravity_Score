"""
Scheduler Service
Orchestrates scheduled scraper and crawler jobs
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.scraper_service import ScraperService
from app.services.crawler_service import CrawlerService
from app.services.supabase_client import get_supabase_client
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Service to schedule and manage scraper/crawler jobs
    Handles daily, weekly, and on-demand jobs
    """
    
    def __init__(self):
        """Initialize scheduler service"""
        self.scheduler = AsyncIOScheduler()
        self.scraper_service = ScraperService()
        self.crawler_service = CrawlerService()
        self.supabase = get_supabase_client()
        self._started = False
        
        logger.info("Scheduler service initialized")
    
    def start(self):
        """Start the scheduler"""
        if self._started:
            logger.warning("Scheduler already started")
            return
        
        # Note: GitHub Actions will trigger daily/weekly jobs via API
        # This scheduler handles internal periodic tasks
        
        # Health check every hour
        self.scheduler.add_job(
            self._health_check,
            trigger=CronTrigger(minute=0),
            id='hourly_health_check',
            replace_existing=True
        )
        
        self.scheduler.start()
        self._started = True
        logger.info("Scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        if self._started:
            self.scheduler.shutdown()
            self._started = False
            logger.info("Scheduler stopped")
    
    async def _health_check(self):
        """Internal health check"""
        logger.info("Running scheduled health check")
    
    async def run_daily_job(self) -> str:
        """
        Daily VIP update (top 100 athletes by Gravity score)
        
        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        
        logger.info(f"Starting daily VIP job {job_id}")
        
        # Create job record
        try:
            self.supabase.table('scraper_jobs').insert({
                'id': job_id,
                'job_type': 'daily_vip',
                'status': 'running',
                'started_at': datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"Failed to create job record: {e}")
            return job_id
        
        try:
            # Get top 100 athletes by Gravity score
            athletes = self.supabase.table('athletes')\
                .select('athlete_id, canonical_name, sport')\
                .order('metadata->total_gravity', desc=True)\
                .limit(100)\
                .execute()
            
            total = len(athletes.data) if athletes.data else 0
            processed = 0
            failed = 0
            errors = []
            
            logger.info(f"Processing {total} athletes for daily job")
            
            for athlete in (athletes.data or []):
                try:
                    # Run scrapers
                    scraper_result = await self.scraper_service.scrape_athlete(
                        athlete['athlete_id'],
                        athlete['sport']
                    )
                    
                    # Run crawlers
                    crawler_result = await self.crawler_service.run_all_crawlers(
                        athlete['athlete_id']
                    )
                    
                    if scraper_result.get('success') and crawler_result.get('success'):
                        processed += 1
                    else:
                        failed += 1
                        errors.append({
                            'athlete_id': athlete['athlete_id'],
                            'scraper_error': scraper_result.get('error'),
                            'crawler_error': crawler_result.get('error')
                        })
                except Exception as e:
                    logger.error(f"Failed to process {athlete['athlete_id']}: {e}")
                    failed += 1
                    errors.append({
                        'athlete_id': athlete['athlete_id'],
                        'error': str(e)
                    })
            
            # Update job record
            self.supabase.table('scraper_jobs').update({
                'status': 'completed',
                'athletes_total': total,
                'athletes_processed': processed,
                'athletes_failed': failed,
                'errors': {'errors': errors[:10]},  # Store first 10 errors
                'completed_at': datetime.utcnow().isoformat()
            }).eq('id', job_id).execute()
            
            logger.info(
                f"Daily job {job_id} completed - "
                f"Total: {total}, Processed: {processed}, Failed: {failed}"
            )
            
        except Exception as e:
            logger.error(f"Daily job {job_id} failed: {e}")
            self.supabase.table('scraper_jobs').update({
                'status': 'failed',
                'errors': {'message': str(e)},
                'completed_at': datetime.utcnow().isoformat()
            }).eq('id', job_id).execute()
        
        return job_id
    
    async def run_weekly_job(self) -> str:
        """
        Weekly full scrape (all athletes)
        
        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        
        logger.info(f"Starting weekly full job {job_id}")
        
        # Create job record
        try:
            self.supabase.table('scraper_jobs').insert({
                'id': job_id,
                'job_type': 'weekly_full',
                'status': 'running',
                'started_at': datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"Failed to create job record: {e}")
            return job_id
        
        try:
            # Get all active athletes
            athletes = self.supabase.table('athletes')\
                .select('athlete_id, canonical_name, sport')\
                .eq('is_active', True)\
                .execute()
            
            total = len(athletes.data) if athletes.data else 0
            processed = 0
            failed = 0
            batch_size = 50
            
            logger.info(f"Processing {total} athletes for weekly job in batches of {batch_size}")
            
            # Process in batches
            for i in range(0, total, batch_size):
                batch = athletes.data[i:i + batch_size]
                
                for athlete in batch:
                    try:
                        # Run scrapers
                        scraper_result = await self.scraper_service.scrape_athlete(
                            athlete['athlete_id'],
                            athlete['sport']
                        )
                        
                        # Run crawlers
                        crawler_result = await self.crawler_service.run_all_crawlers(
                            athlete['athlete_id']
                        )
                        
                        if scraper_result.get('success') and crawler_result.get('success'):
                            processed += 1
                        else:
                            failed += 1
                    except Exception as e:
                        logger.error(f"Failed to process {athlete['athlete_id']}: {e}")
                        failed += 1
                
                # Update progress
                self.supabase.table('scraper_jobs').update({
                    'athletes_processed': processed,
                    'athletes_failed': failed
                }).eq('id', job_id).execute()
                
                logger.info(f"Weekly job progress: {processed}/{total} processed")
            
            # Update job record
            self.supabase.table('scraper_jobs').update({
                'status': 'completed',
                'athletes_total': total,
                'athletes_processed': processed,
                'athletes_failed': failed,
                'completed_at': datetime.utcnow().isoformat()
            }).eq('id', job_id).execute()
            
            logger.info(
                f"Weekly job {job_id} completed - "
                f"Total: {total}, Processed: {processed}, Failed: {failed}"
            )
            
        except Exception as e:
            logger.error(f"Weekly job {job_id} failed: {e}")
            self.supabase.table('scraper_jobs').update({
                'status': 'failed',
                'errors': {'message': str(e)},
                'completed_at': datetime.utcnow().isoformat()
            }).eq('id', job_id).execute()
        
        return job_id
    
    async def scrape_single_athlete(
        self,
        athlete_id: str,
        run_crawlers: bool = True
    ) -> Dict[str, Any]:
        """
        Scrape data for a single athlete (on-demand)
        
        Args:
            athlete_id: UUID of athlete
            run_crawlers: Whether to also run crawlers
            
        Returns:
            Dict with results
        """
        logger.info(f"On-demand scrape for athlete {athlete_id}")
        
        # Get athlete info
        try:
            athlete = self.supabase.table('athletes')\
                .select('*')\
                .eq('athlete_id', athlete_id)\
                .single()\
                .execute()
            
            if not athlete.data:
                return {
                    'success': False,
                    'error': f'Athlete {athlete_id} not found'
                }
            
            athlete_data = athlete.data
        except Exception as e:
            logger.error(f"Failed to fetch athlete {athlete_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        
        # Run scraper
        scraper_result = await self.scraper_service.scrape_athlete(
            athlete_id,
            athlete_data['sport']
        )
        
        # Optionally run crawlers
        crawler_result = None
        if run_crawlers:
            crawler_result = await self.crawler_service.run_all_crawlers(
                athlete_id
            )
        
        return {
            'success': True,
            'athlete_id': athlete_id,
            'scraper_result': scraper_result,
            'crawler_result': crawler_result
        }
