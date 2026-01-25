"""
Athlete endpoints
On-demand refresh and status checking
"""

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from app.auth import verify_api_key
from app.services.scraper_service import ScraperService
from app.services.crawler_service import CrawlerService
from app.services.scheduler_service import SchedulerService
from app.schemas.responses import RefreshResponse
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


async def _refresh_athlete_task(
    athlete_id: str,
    sport: str,
    scraper: ScraperService,
    crawler: CrawlerService
):
    """Background task for athlete refresh"""
    try:
        logger.info(f"Starting background refresh for athlete {athlete_id}")
        await scraper.scrape_athlete(athlete_id, sport)
        await crawler.run_all_crawlers(athlete_id)
        logger.info(f"Completed background refresh for athlete {athlete_id}")
    except Exception as e:
        logger.error(f"Background refresh failed for athlete {athlete_id}: {e}")


@router.post("/{athlete_id}/refresh", response_model=RefreshResponse)
async def refresh_athlete(
    athlete_id: str,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """
    Trigger on-demand refresh for athlete
    
    Args:
        athlete_id: UUID of athlete to refresh
        background_tasks: FastAPI background tasks
        api_key: API key for authentication
        
    Returns:
        Refresh status
    """
    scraper = ScraperService()
    crawler = CrawlerService()
    
    # Get athlete info
    try:
        athlete = scraper.supabase.table('athletes')\
            .select('sport')\
            .eq('athlete_id', athlete_id)\
            .single()\
            .execute()
        
        if not athlete.data:
            raise HTTPException(status_code=404, detail="Athlete not found")
        
        sport = athlete.data['sport']
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch athlete {athlete_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch athlete")
    
    # Run in background
    background_tasks.add_task(
        _refresh_athlete_task,
        athlete_id,
        sport,
        scraper,
        crawler
    )
    
    return {
        "status": "started",
        "athlete_id": athlete_id,
        "message": "Refresh started. Updates will appear in 30-60 seconds."
    }


@router.get("/{athlete_id}/status")
async def get_athlete_status(athlete_id: str):
    """
    Get current status of athlete data
    
    Args:
        athlete_id: UUID of athlete
        
    Returns:
        Status information
    """
    scraper = ScraperService()
    
    try:
        # Get athlete and latest payload info
        athlete = scraper.supabase.table('athletes')\
            .select('*')\
            .eq('athlete_id', athlete_id)\
            .single()\
            .execute()
        
        if not athlete.data:
            raise HTTPException(status_code=404, detail="Athlete not found")
        
        # Get latest scraper run
        latest_payload = scraper.supabase.table('raw_payloads')\
            .select('fetched_at, source')\
            .eq('athlete_id', athlete_id)\
            .order('fetched_at', desc=True)\
            .limit(1)\
            .execute()
        
        return {
            "athlete_id": athlete_id,
            "name": athlete.data.get('canonical_name'),
            "sport": athlete.data.get('sport'),
            "is_active": athlete.data.get('is_active'),
            "last_scraped": latest_payload.data[0]['fetched_at'] if latest_payload.data else None,
            "last_source": latest_payload.data[0]['source'] if latest_payload.data else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get status for athlete {athlete_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get athlete status")
