"""
Response schemas for API endpoints
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class RefreshResponse(BaseModel):
    """Response for athlete refresh request"""
    status: str
    athlete_id: str
    message: str


class JobResponse(BaseModel):
    """Response for job trigger"""
    status: str
    job_type: str
    job_id: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Job status information"""
    id: str
    job_type: str
    status: str
    athletes_total: Optional[int] = 0
    athletes_processed: Optional[int] = 0
    athletes_failed: Optional[int] = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    errors: Optional[Dict[str, Any]] = None


class CrawlerStatusResponse(BaseModel):
    """Crawler status information"""
    available: bool
    status: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    service: str = "gravity-scrapers"
