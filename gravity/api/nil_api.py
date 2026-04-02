"""
NIL API - FastAPI endpoints for valuation and underwriting
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import date
import uuid
import logging

from gravity.valuation import calculate_iacv, underwrite_deal
from gravity.packs import aggregate_pack_data, export_pack_json, generate_pack_pdf
from gravity.nil import run_nil_collection, calculate_and_store_features
from gravity.scoring import calculate_gravity_score

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Gravity NIL API",
    description="Underwriting-grade NIL valuation and deal decisioning API",
    version="1.0"
)


# ============================================================================
# Request/Response Models
# ============================================================================

class ValuationRequest(BaseModel):
    athlete_id: str
    season_id: str
    as_of_date: Optional[str] = None


class DealProposal(BaseModel):
    price: float = Field(..., gt=0)
    term_months: int = Field(default=12, gt=0)
    structure_type: str = Field(default="fixed")
    is_exclusive: bool = False
    is_category_exclusive: bool = False
    territory: str = Field(default="local")
    rights: list = Field(default_factory=list)
    deliverables: list = Field(default_factory=list)


class UnderwritingRequest(BaseModel):
    athlete_id: str
    season_id: str
    deal_proposal: DealProposal
    as_of_date: Optional[str] = None


class PackRequest(BaseModel):
    athlete_id: str
    season_id: str
    deal_proposal: Optional[DealProposal] = None
    as_of_date: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    json_url: Optional[str] = None
    pdf_url: Optional[str] = None


# ============================================================================
# Health Check
# ============================================================================

@app.get("/")
async def root():
    """API root"""
    return {
        "service": "Gravity NIL API",
        "version": "1.0",
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


# ============================================================================
# Valuation Endpoints
# ============================================================================

@app.post("/api/v1/athletes/{athlete_id}/valuation")
async def get_valuation(athlete_id: str, request: ValuationRequest):
    """
    Calculate IACV for athlete
    
    Returns P25/P50/P75 valuations with confidence intervals
    """
    try:
        athlete_uuid = uuid.UUID(athlete_id)
        as_of_date = date.fromisoformat(request.as_of_date) if request.as_of_date else None
        
        result = calculate_iacv(athlete_uuid, request.season_id, as_of_date)
        
        return {
            "success": True,
            "athlete_id": athlete_id,
            "valuation": result
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
    except Exception as e:
        logger.error(f"Valuation failed: {e}")
        raise HTTPException(status_code=500, detail="Valuation calculation failed")


@app.post("/api/v1/athletes/{athlete_id}/underwrite")
async def underwrite(athlete_id: str, request: UnderwritingRequest):
    """
    Underwrite a specific NIL deal
    
    Returns decision (approve/counter/no-go) with rationale
    """
    try:
        athlete_uuid = uuid.UUID(athlete_id)
        as_of_date = date.fromisoformat(request.as_of_date) if request.as_of_date else None
        
        deal_proposal = request.deal_proposal.dict()
        
        result = underwrite_deal(
            athlete_uuid,
            request.season_id,
            deal_proposal,
            as_of_date
        )
        
        return {
            "success": True,
            "athlete_id": athlete_id,
            "underwriting": result
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
    except Exception as e:
        logger.error(f"Underwriting failed: {e}")
        raise HTTPException(status_code=500, detail="Underwriting failed")


# ============================================================================
# Pack Generation Endpoints
# ============================================================================

@app.post("/api/v1/athletes/{athlete_id}/negotiation-pack")
async def request_pack(athlete_id: str, request: PackRequest, background_tasks: BackgroundTasks):
    """
    Request negotiation pack generation (async)
    
    Returns job_id for status tracking
    """
    try:
        athlete_uuid = uuid.UUID(athlete_id)
        job_id = str(uuid.uuid4())
        
        # Add to background tasks
        background_tasks.add_task(
            generate_pack_background,
            job_id,
            athlete_uuid,
            request.season_id,
            request.deal_proposal.dict() if request.deal_proposal else None,
            date.fromisoformat(request.as_of_date) if request.as_of_date else None
        )
        
        return {
            "success": True,
            "job_id": job_id,
            "status": "processing",
            "message": "Pack generation started"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
    except Exception as e:
        logger.error(f"Pack request failed: {e}")
        raise HTTPException(status_code=500, detail="Pack request failed")


@app.get("/api/v1/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Get job status and download URLs when ready
    
    Note: In production, this would check a job queue/database
    """
    # Placeholder implementation
    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Check back in a moment"
    }


# ============================================================================
# Data Collection Endpoints
# ============================================================================

@app.post("/api/v1/athletes/collect-nil")
async def collect_nil_data(
    athlete_name: str,
    school: Optional[str] = None,
    sport: str = "football"
):
    """
    Trigger NIL data collection for an athlete
    """
    try:
        result = run_nil_collection(athlete_name, school, sport)
        
        return {
            "success": True,
            "collection_summary": result.get('summary', {}),
            "sources_successful": len(result.get('sources', {}))
        }
        
    except Exception as e:
        logger.error(f"NIL collection failed: {e}")
        raise HTTPException(status_code=500, detail="NIL data collection failed")


@app.post("/api/v1/athletes/{athlete_id}/calculate-features")
async def calculate_features(athlete_id: str, season_id: str):
    """
    Calculate and store features for an athlete
    """
    try:
        athlete_uuid = uuid.UUID(athlete_id)
        snapshot_id = calculate_and_store_features(athlete_uuid, season_id)
        
        return {
            "success": True,
            "snapshot_id": str(snapshot_id),
            "message": "Features calculated and stored"
        }
        
    except Exception as e:
        logger.error(f"Feature calculation failed: {e}")
        raise HTTPException(status_code=500, detail="Feature calculation failed")


@app.post("/api/v1/athletes/{athlete_id}/calculate-gravity")
async def calculate_gravity(athlete_id: str, season_id: str):
    """
    Calculate and store Gravity score for an athlete
    """
    try:
        athlete_uuid = uuid.UUID(athlete_id)
        score = calculate_gravity_score(athlete_uuid, season_id, date.today())
        
        return {
            "success": True,
            "gravity_score": score
        }
        
    except Exception as e:
        logger.error(f"Gravity calculation failed: {e}")
        raise HTTPException(status_code=500, detail="Gravity calculation failed")


# ============================================================================
# Background Tasks
# ============================================================================

async def generate_pack_background(
    job_id: str,
    athlete_id: uuid.UUID,
    season_id: str,
    deal_proposal: Optional[Dict],
    as_of_date: Optional[date]
):
    """Background task for pack generation"""
    try:
        logger.info(f"Generating pack for job {job_id}")
        
        # Aggregate data
        pack_data = aggregate_pack_data(athlete_id, season_id, deal_proposal, as_of_date)
        
        # Export JSON
        json_path = f"data/packs/{job_id}.json"
        export_pack_json(pack_data, json_path)
        
        # Export PDF
        pdf_path = f"data/packs/{job_id}.pdf"
        generate_pack_pdf(pack_data, pdf_path)
        
        logger.info(f"Pack generated successfully for job {job_id}")
        
        # In production, update job status in database
        
    except Exception as e:
        logger.error(f"Pack generation failed for job {job_id}: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
