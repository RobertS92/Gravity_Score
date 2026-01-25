"""
Crawler API - FastAPI endpoints for manual triggering and monitoring
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import logging

from gravity.crawlers.crawler_orchestrator import CrawlerOrchestrator
from gravity.crawlers.crawler_scheduler import CrawlerScheduler
from gravity.crawlers.event_processor import EventProcessor
from gravity.crawlers.score_recalculator import ScoreRecalculator

logger = logging.getLogger(__name__)

# Create FastAPI app (or use existing app)
try:
    from gravity.api.nil_api import app
except ImportError:
    app = FastAPI(
        title="Gravity Crawler API",
        description="API for managing and monitoring crawlers",
        version="1.0"
    )

# Initialize components
orchestrator = CrawlerOrchestrator()
scheduler = CrawlerScheduler()
event_processor = EventProcessor()
score_recalculator = ScoreRecalculator()


# ============================================================================
# Request/Response Models
# ============================================================================

class CrawlerRunRequest(BaseModel):
    athlete_id: Optional[str] = None
    athlete_name: Optional[str] = None
    sport: Optional[str] = None
    crawler_params: Dict[str, Any] = Field(default_factory=dict)


class ScoreRecalculationRequest(BaseModel):
    athlete_id: str
    components: Optional[List[str]] = None
    season_id: Optional[str] = None
    as_of_date: Optional[str] = None


class CrawlerConfigRequest(BaseModel):
    is_enabled: Optional[bool] = None
    schedule_interval: Optional[str] = None
    schedule_time: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


# ============================================================================
# Manual Crawler Triggers
# ============================================================================

@app.post("/crawlers/{crawler_name}/run")
async def run_crawler(
    crawler_name: str,
    request: CrawlerRunRequest
):
    """
    Manually trigger a specific crawler for an athlete
    
    Args:
        crawler_name: Name of crawler to run
        request: Request with athlete_id or athlete_name
    
    Returns:
        Crawler execution result
    """
    try:
        # Resolve athlete_id if needed
        athlete_id = None
        if request.athlete_id:
            athlete_id = uuid.UUID(request.athlete_id)
        elif request.athlete_name:
            # Find athlete by name
            athlete_id = orchestrator.get_crawler('news_article').find_athlete_by_name(
                request.athlete_name,
                request.sport
            )
            if not athlete_id:
                raise HTTPException(
                    status_code=404,
                    detail=f"Athlete not found: {request.athlete_name}"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="athlete_id or athlete_name required"
            )
        
        # Run crawler
        result = await orchestrator.run_crawler(
            crawler_name,
            athlete_id=athlete_id,
            sport=request.sport,
            **request.crawler_params
        )
        
        return {
            'success': result.get('success', False),
            'crawler': crawler_name,
            'athlete_id': str(athlete_id),
            'events_created': result.get('events_created', 0),
            'errors': result.get('errors', []),
            'metadata': result.get('metadata', {})
        }
        
    except Exception as e:
        logger.error(f"Crawler execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/crawlers/run_all")
async def run_all_crawlers(
    request: CrawlerRunRequest,
    background_tasks: BackgroundTasks
):
    """
    Run all crawlers for an athlete
    
    Args:
        request: Request with athlete_id or athlete_name
        background_tasks: FastAPI background tasks
    
    Returns:
        Job status
    """
    try:
        # Resolve athlete_id
        athlete_id = None
        if request.athlete_id:
            athlete_id = uuid.UUID(request.athlete_id)
        elif request.athlete_name:
            athlete_id = orchestrator.get_crawler('news_article').find_athlete_by_name(
                request.athlete_name,
                request.sport
            )
            if not athlete_id:
                raise HTTPException(
                    status_code=404,
                    detail=f"Athlete not found: {request.athlete_name}"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="athlete_id or athlete_name required"
            )
        
        # Run in background
        background_tasks.add_task(
            orchestrator.run_all_crawlers,
            athlete_id,
            **request.crawler_params
        )
        
        return {
            'status': 'running',
            'athlete_id': str(athlete_id),
            'message': 'All crawlers started in background'
        }
        
    except Exception as e:
        logger.error(f"Failed to start crawlers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/crawlers/run_sport")
async def run_sport_crawlers(
    sport: str,
    athlete_ids: List[str],
    crawler_names: Optional[List[str]] = None,
    background_tasks: BackgroundTasks = None
):
    """
    Run crawlers for multiple athletes in a sport
    
    Args:
        sport: Sport identifier
        athlete_ids: List of athlete UUIDs
        crawler_names: Optional list of crawler names
        background_tasks: FastAPI background tasks
    
    Returns:
        Job status
    """
    try:
        athlete_uuids = [uuid.UUID(aid) for aid in athlete_ids]
        
        if background_tasks:
            background_tasks.add_task(
                orchestrator.run_sport_crawlers,
                sport,
                athlete_uuids,
                crawler_names
            )
            
            return {
                'status': 'running',
                'sport': sport,
                'athletes': len(athlete_uuids),
                'message': 'Sport crawlers started in background'
            }
        else:
            result = await orchestrator.run_sport_crawlers(
                sport,
                athlete_uuids,
                crawler_names
            )
            
            return result
        
    except Exception as e:
        logger.error(f"Sport crawler execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Crawler Status and Monitoring
# ============================================================================

@app.get("/crawlers/status")
async def crawler_status():
    """
    Get status of all crawlers
    
    Returns:
        Status dict with crawler information
    """
    try:
        status = orchestrator.get_crawler_status()
        
        # Add scheduler job information
        if scheduler:
            scheduled_jobs = scheduler.get_scheduled_jobs()
            status['scheduled_jobs'] = scheduled_jobs
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get crawler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/crawlers/{crawler_name}/executions")
async def crawler_executions(
    crawler_name: str,
    limit: int = 50
):
    """
    Get recent executions for a crawler
    
    Args:
        crawler_name: Crawler name
        limit: Maximum number of executions to return
    
    Returns:
        List of execution records
    """
    try:
        from gravity.storage import get_storage_manager
        from gravity.db.models import CrawlerExecution
        
        storage = get_storage_manager()
        
        with storage.get_session() as session:
            executions = session.query(CrawlerExecution).filter(
                CrawlerExecution.crawler_name == crawler_name
            ).order_by(CrawlerExecution.started_at.desc()).limit(limit).all()
            
            return [
                {
                    'execution_id': str(e.execution_id),
                    'athlete_id': str(e.athlete_id) if e.athlete_id else None,
                    'status': e.status,
                    'started_at': e.started_at.isoformat(),
                    'completed_at': e.completed_at.isoformat() if e.completed_at else None,
                    'duration_seconds': e.duration_seconds,
                    'events_created': e.events_created,
                    'errors': e.errors
                }
                for e in executions
            ]
        
    except Exception as e:
        logger.error(f"Failed to get crawler executions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/crawlers/config")
async def get_crawler_configs():
    """
    Get crawler configuration
    
    Returns:
        List of crawler configs
    """
    try:
        from gravity.storage import get_storage_manager
        from gravity.db.models import CrawlerConfig
        
        storage = get_storage_manager()
        
        with storage.get_session() as session:
            configs = session.query(CrawlerConfig).all()
            
            return [
                {
                    'crawler_name': c.crawler_name,
                    'is_enabled': c.is_enabled,
                    'schedule_interval': c.schedule_interval,
                    'schedule_time': c.schedule_time,
                    'last_run_at': c.last_run_at.isoformat() if c.last_run_at else None,
                    'next_run_at': c.next_run_at.isoformat() if c.next_run_at else None,
                    'config': c.config
                }
                for c in configs
            ]
        
    except Exception as e:
        logger.error(f"Failed to get crawler configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/crawlers/{crawler_name}/config")
async def update_crawler_config(
    crawler_name: str,
    config: CrawlerConfigRequest
):
    """
    Update crawler configuration
    
    Args:
        crawler_name: Crawler name
        config: Configuration updates
    
    Returns:
        Updated config
    """
    try:
        from gravity.storage import get_storage_manager
        from gravity.db.models import CrawlerConfig
        
        storage = get_storage_manager()
        
        with storage.get_session() as session:
            crawler_config = session.query(CrawlerConfig).filter(
                CrawlerConfig.crawler_name == crawler_name
            ).first()
            
            if not crawler_config:
                # Create new config
                crawler_config = CrawlerConfig(
                    crawler_name=crawler_name,
                    is_enabled=config.is_enabled if config.is_enabled is not None else True,
                    schedule_interval=config.schedule_interval,
                    schedule_time=config.schedule_time,
                    config=config.config or {}
                )
                session.add(crawler_config)
            else:
                # Update existing config
                if config.is_enabled is not None:
                    crawler_config.is_enabled = config.is_enabled
                if config.schedule_interval:
                    crawler_config.schedule_interval = config.schedule_interval
                if config.schedule_time:
                    crawler_config.schedule_time = config.schedule_time
                if config.config:
                    crawler_config.config.update(config.config)
                crawler_config.updated_at = datetime.utcnow()
            
            session.commit()
            session.refresh(crawler_config)
            
            return {
                'crawler_name': crawler_config.crawler_name,
                'is_enabled': crawler_config.is_enabled,
                'schedule_interval': crawler_config.schedule_interval,
                'schedule_time': crawler_config.schedule_time,
                'config': crawler_config.config
            }
        
    except Exception as e:
        logger.error(f"Failed to update crawler config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Score Recalculation
# ============================================================================

@app.post("/scores/recalculate/{athlete_id}")
async def recalculate_scores(
    athlete_id: str,
    request: ScoreRecalculationRequest
):
    """
    Manually trigger score recalculation
    
    Args:
        athlete_id: Athlete UUID
        request: Recalculation request
    
    Returns:
        Recalculation result
    """
    try:
        athlete_uuid = uuid.UUID(athlete_id)
        
        result = await score_recalculator.recalculate_scores(
            athlete_uuid,
            components=request.components,
            season_id=request.season_id,
            as_of_date=datetime.fromisoformat(request.as_of_date).date() if request.as_of_date else None
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Score recalculation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scores/recalculations/{athlete_id}")
async def get_recalculations(
    athlete_id: str,
    limit: int = 50
):
    """
    Get score recalculation history
    
    Args:
        athlete_id: Athlete UUID
        limit: Maximum number of records
    
    Returns:
        List of recalculation records
    """
    try:
        from gravity.storage import get_storage_manager
        from gravity.db.models import ScoreRecalculation
        
        storage = get_storage_manager()
        athlete_uuid = uuid.UUID(athlete_id)
        
        with storage.get_session() as session:
            recalculations = session.query(ScoreRecalculation).filter(
                ScoreRecalculation.athlete_id == athlete_uuid
            ).order_by(ScoreRecalculation.recalculated_at.desc()).limit(limit).all()
            
            return [
                {
                    'recalculation_id': str(r.recalculation_id),
                    'trigger_event_id': str(r.trigger_event_id) if r.trigger_event_id else None,
                    'trigger_event_type': r.trigger_event_type,
                    'components_recalculated': r.components_recalculated,
                    'old_gravity_score': r.old_gravity_score,
                    'new_gravity_score': r.new_gravity_score,
                    'score_delta': r.score_delta,
                    'recalculated_at': r.recalculated_at.isoformat()
                }
                for r in recalculations
            ]
        
    except Exception as e:
        logger.error(f"Failed to get recalculations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Health Check
# ============================================================================

@app.get("/crawlers/health")
async def crawler_health():
    """Health check for crawler system"""
    return {
        'status': 'healthy',
        'crawlers_available': len(orchestrator.crawlers),
        'scheduler_active': scheduler.scheduler is not None if scheduler else False,
        'timestamp': datetime.utcnow().isoformat()
    }
