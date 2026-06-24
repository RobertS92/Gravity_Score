"""Sport-specific athlete pipeline endpoints."""

from __future__ import annotations

import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from gravity_api.database import get_db
from gravity_api.routers.scores import _require_internal_key
from gravity_api.services.sport_pipeline.config import ALL_SPORT_PIPELINES
from gravity_api.services.sport_pipeline.run import run_athlete_pipeline, run_feature_pipeline

router = APIRouter()


class PipelineRunBody(BaseModel):
    score: bool = True


class NightlyBody(BaseModel):
    sport: str | None = None
    athlete_limit: int = Field(100, ge=1, le=2000)
    concurrency: int | None = Field(None, ge=1, le=32)
    scrape_concurrency: int = Field(3, ge=1, le=32)
    score_concurrency: int = Field(8, ge=1, le=32)
    sport_parallel: int = Field(1, ge=1, le=8)
    scrape: bool = True
    rebuild_cohorts: bool = True
    score: bool = True


class ExportCsvBody(BaseModel):
    mode: str = Field("scored", pattern="^(scored|labeled|teams)$")
    sport: str | None = None
    target_key: str = "nil_valuation_usd"
    limit: int = Field(50_000, ge=1, le=200_000)


@router.post("/nightly")
async def run_nightly_pipeline(
    body: NightlyBody = NightlyBody(),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    """Per-sport stale scrape → cohort rebuild → BPXVR score (all 8 sports by default)."""
    from gravity_api.services.sport_pipeline.nightly import (
        run_nightly_all_sports,
        run_nightly_for_sport,
    )

    if body.sport:
        result = await run_nightly_for_sport(
            db,
            sport=body.sport,
            athlete_limit=body.athlete_limit,
            concurrency=body.concurrency,
            scrape_concurrency=body.scrape_concurrency,
            score_concurrency=body.score_concurrency,
            scrape=body.scrape,
            rebuild_cohorts=body.rebuild_cohorts,
            score=body.score,
        )
        return {
            "sport": result.sport,
            "stale_found": result.stale_found,
            "scraped_ok": result.scraped_ok,
            "scraped_fail": result.scraped_fail,
            "cohort_baselines_written": result.cohort_baselines_written,
            "scored_ok": result.scored_ok,
            "scored_fail": result.scored_fail,
            "errors": result.errors[:20],
        }
    return await run_nightly_all_sports(
        db,
        athlete_limit_per_sport=body.athlete_limit,
        concurrency=body.concurrency,
        scrape_concurrency=body.scrape_concurrency,
        score_concurrency=body.score_concurrency,
        sport_parallel=body.sport_parallel,
    )


@router.post("/cohorts/rebuild")
async def rebuild_cohorts(
    sport: str | None = None,
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    """Rebuild gravity_cohort_baselines (after bulk scrape)."""
    from gravity_api.services.sport_pipeline.nightly import rebuild_cohorts_for_sport
    from gravity_api.services.sport_pipeline.config import ALL_SPORT_PIPELINES

    if sport:
        n = await rebuild_cohorts_for_sport(db, sport)
        return {"sport": sport, "baselines_written": n}
    totals = {}
    for s in ALL_SPORT_PIPELINES:
        totals[s] = await rebuild_cohorts_for_sport(db, s)
    return {"baselines_written": totals}


@router.get("/sports")
async def list_sport_pipelines(_: None = Depends(_require_internal_key)):
    return {
        "sports": {
            k: {
                "model_key": v.model_key,
                "ml_endpoint": v.ml_endpoint,
                "league": v.league,
                "terminal_visible": v.terminal_visible,
                "college_pro_bridge": v.college_pro_bridge,
            }
            for k, v in ALL_SPORT_PIPELINES.items()
        }
    }


@router.post("/export/training-csv")
async def export_training_csv(
    body: ExportCsvBody = ExportCsvBody(),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    """Download training CSV for Colab (internal key required)."""
    from gravity_api.jobs.export_training_csv import (
        export_labeled_rows,
        export_scored_athletes,
        export_teams,
    )
    from gravity_api.services.training_export import rows_to_csv

    if body.mode == "scored":
        rows = await export_scored_athletes(db, sport=body.sport, limit=body.limit)
        filename = f"gravity_athletes_{body.sport or 'all'}_scored.csv"
    elif body.mode == "labeled":
        rows = await export_labeled_rows(
            db,
            entity_type="athlete",
            target_key=body.target_key,
            sport=body.sport,
            limit=body.limit,
        )
        filename = f"gravity_labeled_{body.target_key}.csv"
    else:
        rows = await export_teams(db, sport=body.sport)
        filename = f"gravity_teams_{body.sport or 'all'}.csv"

    csv_text = rows_to_csv(rows)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/athletes/{athlete_id}/features")
async def run_features_only(
    athlete_id: str,
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    try:
        uuid.UUID(athlete_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid athlete_id") from e
    try:
        return await run_feature_pipeline(db, athlete_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/athletes/{athlete_id}/run")
async def run_full_pipeline(
    athlete_id: str,
    body: PipelineRunBody = PipelineRunBody(),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    """Feature engineering + BPXVR snapshot + sport-specific ML score."""
    try:
        uuid.UUID(athlete_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid athlete_id") from e
    try:
        return await run_athlete_pipeline(db, athlete_id, score=body.score)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
