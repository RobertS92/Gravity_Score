"""
Gravity Scrapers & Crawlers API
Main FastAPI application for Railway deployment
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import athletes, jobs, crawlers, health
from app.config import settings
from app.services.scheduler_service import SchedulerService
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Gravity Scrapers & Crawlers API",
    description="Automated data collection for athlete marketability scoring",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for Lovable frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(athletes.router, prefix="/api/v1/athletes", tags=["Athletes"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(crawlers.router, prefix="/api/v1/crawlers", tags=["Crawlers"])


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("=" * 60)
    logger.info("Starting Gravity Scrapers Service")
    logger.info(f"API Key configured: {bool(settings.API_KEY)}")
    logger.info(f"Supabase URL: {settings.SUPABASE_URL}")
    logger.info(f"CORS Origins: {settings.cors_origins_list}")
    logger.info("=" * 60)
    
    # Initialize and start scheduler
    try:
        scheduler = SchedulerService()
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("Scheduler initialized and started")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        logger.warning("Continuing without scheduler - manual triggers only")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Gravity Scrapers Service")
    
    if hasattr(app.state, "scheduler"):
        try:
            app.state.scheduler.stop()
            logger.info("Scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Gravity Scrapers & Crawlers API",
        "version": "2.0.0",
        "status": "operational",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=True
    )
