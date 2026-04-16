"""
Job management endpoints
Trigger and monitor scraper/crawler jobs
"""

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from app.auth import verify_api_key
from app.services.scheduler_service import SchedulerService
from app.services.supabase_client import get_supabase_client
from app.config import settings
from app.schemas.responses import JobResponse, JobStatusResponse
from typing import List
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/daily", response_model=JobResponse)
async def trigger_daily_job(
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """
    Trigger daily VIP update job (top 100 athletes)
    
    Args:
        background_tasks: FastAPI background tasks
        api_key: API key for authentication
        
    Returns:
        Job trigger confirmation
    """
    if not settings.supabase_enabled:
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured; daily jobs require SUPABASE_URL and SUPABASE_SERVICE_KEY.",
        )

    scheduler = SchedulerService()

    # Run in background
    background_tasks.add_task(scheduler.run_daily_job)

    logger.info("Daily VIP job triggered")
    
    return {
        "status": "started",
        "job_type": "daily_vip"
    }


@router.post("/weekly", response_model=JobResponse)
async def trigger_weekly_job(
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """
    Trigger weekly full scrape job (all athletes)
    
    Args:
        background_tasks: FastAPI background tasks
        api_key: API key for authentication
        
    Returns:
        Job trigger confirmation
    """
    if not settings.supabase_enabled:
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured; weekly jobs require SUPABASE_URL and SUPABASE_SERVICE_KEY.",
        )

    scheduler = SchedulerService()

    # Run in background
    background_tasks.add_task(scheduler.run_weekly_job)

    logger.info("Weekly full job triggered")
    
    return {
        "status": "started",
        "job_type": "weekly_full"
    }


@router.get("/status", response_model=List[JobStatusResponse])
async def get_jobs_status(limit: int = 20):
    """
    Get recent job status (public endpoint for monitoring)
    
    Args:
        limit: Number of recent jobs to return
        
    Returns:
        List of recent job statuses
    """
    supabase = get_supabase_client()
    if not supabase:
        return []

    try:
        jobs = supabase.table('scraper_jobs')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(limit)\
            .execute()
        
        return jobs.data or []
    except Exception as e:
        logger.error(f"Failed to fetch job statuses: {e}")
        return []


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get status of a specific job
    
    Args:
        job_id: UUID of job
        
    Returns:
        Job status information
    """
    supabase = get_supabase_client()
    if not supabase:
        return {
            "id": job_id,
            "job_type": "unknown",
            "status": "not_configured",
        }

    try:
        job = supabase.table('scraper_jobs')\
            .select('*')\
            .eq('id', job_id)\
            .single()\
            .execute()
        
        if not job.data:
            return {
                "id": job_id,
                "job_type": "unknown",
                "status": "not_found"
            }
        
        return job.data
    except Exception as e:
        logger.error(f"Failed to fetch job {job_id}: {e}")
        return {
            "id": job_id,
            "job_type": "unknown",
            "status": "error"
        }
