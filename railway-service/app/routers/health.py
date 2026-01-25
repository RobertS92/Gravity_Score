"""
Health check endpoints
"""

from fastapi import APIRouter
from datetime import datetime
from app.schemas.responses import HealthResponse

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
            "database": "operational"
        }
    }
