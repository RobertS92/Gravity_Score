"""
Crawler control endpoints
Run and monitor crawlers
"""

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from app.auth import verify_api_key
from app.services.crawler_service import CrawlerService
from app.schemas.responses import CrawlerStatusResponse
from typing import Optional
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


async def _run_crawler_task(
    crawler_service: CrawlerService,
    crawler_name: str,
    athlete_id: str
):
    """Background task to run crawler"""
    try:
        await crawler_service.run_crawler(crawler_name, athlete_id)
    except Exception as e:
        logger.error(f"Crawler task failed: {e}")


@router.post("/{crawler_name}/run")
async def run_crawler(
    crawler_name: str,
    athlete_id: str,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """
    Run specific crawler for an athlete
    
    Args:
        crawler_name: Name of crawler to run
        athlete_id: UUID of athlete
        background_tasks: FastAPI background tasks
        api_key: API key for authentication
        
    Returns:
        Crawler run confirmation
    """
    crawler_service = CrawlerService()
    
    # Run in background
    background_tasks.add_task(
        _run_crawler_task,
        crawler_service,
        crawler_name,
        athlete_id
    )
    
    logger.info(f"Crawler '{crawler_name}' triggered for athlete {athlete_id}")
    
    return {
        "status": "started",
        "crawler_name": crawler_name,
        "athlete_id": athlete_id
    }


@router.post("/run-all")
async def run_all_crawlers(
    athlete_id: str,
    background_tasks: BackgroundTasks,
    sport: Optional[str] = None,
    api_key: str = Depends(verify_api_key),
):
    """
    Run all crawlers for an athlete
    
    Args:
        athlete_id: UUID of athlete
        sport: Optional sport filter
        background_tasks: FastAPI background tasks
        api_key: API key for authentication
        
    Returns:
        Crawler run confirmation
    """
    crawler_service = CrawlerService()
    
    # Run in background
    async def _run_all():
        try:
            await crawler_service.run_all_crawlers(athlete_id, sport)
        except Exception as e:
            logger.error(f"Failed to run all crawlers: {e}")
    
    background_tasks.add_task(_run_all)
    
    logger.info(f"All crawlers triggered for athlete {athlete_id}")
    
    return {
        "status": "started",
        "athlete_id": athlete_id,
        "sport": sport
    }


@router.get("/status", response_model=CrawlerStatusResponse)
async def get_crawler_status():
    """
    Get status of all crawlers
    
    Returns:
        Crawler status information
    """
    crawler_service = CrawlerService()
    
    try:
        status = crawler_service.get_crawler_status()
        return status
    except Exception as e:
        logger.error(f"Failed to get crawler status: {e}")
        return {
            "available": False,
            "error": str(e)
        }


@router.get("/available")
async def get_available_crawlers():
    """
    Get list of available crawlers
    
    Returns:
        List of crawler names
    """
    crawler_service = CrawlerService()
    
    try:
        crawlers = crawler_service.get_available_crawlers()
        return {
            "crawlers": crawlers
        }
    except Exception as e:
        logger.error(f"Failed to get available crawlers: {e}")
        return {
            "crawlers": [],
            "error": str(e)
        }
