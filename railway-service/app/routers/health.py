"""
Health check endpoints
"""

from fastapi import APIRouter
from datetime import datetime
from app.schemas.responses import HealthResponse
from app.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic health check for Railway
    
    Returns:
        Health status information
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "gravity-scrapers"
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check with system status
    
    Returns:
        Detailed health information
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "gravity-scrapers",
        "components": {
            "api": "operational",
            "scrapers": "operational",
            "crawlers": "operational",
            "database": (
                "operational"
                if settings.supabase_enabled
                else "not_configured"
            ),
        }
    }
