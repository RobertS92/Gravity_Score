import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from gravity_api.config import get_settings
from gravity_api.database import get_db
from gravity_api.services.athlete_score_sync import sync_athlete_score_from_ml
from gravity_api.services.gravity_network_v2 import (
    score_athlete_v2,
    score_brand_v2,
    score_fit_v2,
    score_team_v2,
)
from gravity_api.services.model_registry_v2 import list_models, promote_model

router = APIRouter()


class FitRequest(BaseModel):
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    context: list[float] = Field(default_factory=list)


class PromoteModelRequest(BaseModel):
    model_key: str
    model_version: str


def _require_internal_key(x_gravity_internal_key: str | None = Header(None)) -> None:
    settings = get_settings()
    expected = settings.internal_api_key
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Set GRAVITY_INTERNAL_API_KEY to enable score sync",
        )
    if not x_gravity_internal_key or x_gravity_internal_key != expected:
        raise HTTPException(status_code=403, detail="Invalid X-Gravity-Internal-Key")


@router.get("/{athlete_id}/latest")
async def latest_score(athlete_id: str, db: asyncpg.Connection = Depends(get_db)):
    row = await db.fetchrow(
        """SELECT * FROM athlete_gravity_scores
           WHERE athlete_id = $1
           ORDER BY calculated_at DESC LIMIT 1""",
        athlete_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No score for athlete")
    return dict(row)


@router.post("/athletes/{athlete_id}/sync-from-ml")
async def sync_score_from_ml(
    athlete_id: str,
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    """Append a score row from gravity-ml (athlete + optional program/company gravity)."""
    try:
        return await sync_athlete_score_from_ml(db, athlete_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


async def _run_v2(operation):
    try:
        return await operation
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, asyncpg.PostgresError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gravity ML scoring failed: {exc}") from exc


@router.post("/v2/athletes/{athlete_id}")
async def score_athlete_network_v2(
    athlete_id: str,
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    return await _run_v2(score_athlete_v2(db, athlete_id))


@router.post("/v2/teams/{team_id}")
async def score_team_network_v2(
    team_id: str,
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    return await _run_v2(score_team_v2(db, team_id))


@router.post("/v2/brands/{brand_id}")
async def score_brand_network_v2(
    brand_id: str,
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    return await _run_v2(score_brand_v2(db, brand_id))


@router.post("/v2/fit")
async def score_relationship_network_v2(
    body: FitRequest,
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    return await _run_v2(
        score_fit_v2(
            db,
            body.source_type,
            body.source_id,
            body.target_type,
            body.target_id,
            body.context,
        )
    )


@router.get("/v2/models")
async def models_network_v2(
    model_key: str | None = None,
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    return {"models": await list_models(db, model_key)}


@router.post("/v2/models/promote")
async def promote_model_network_v2(
    body: PromoteModelRequest,
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    try:
        return await promote_model(db, body.model_key, body.model_version)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
