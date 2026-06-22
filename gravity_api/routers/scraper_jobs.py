"""Scraper pipeline control plane (queue + circuits). gravity-scrapers should mirror for production."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from gravity_api.auth_deps import require_user_id
from gravity_api.config import get_settings
from gravity_api.database import get_db
from gravity_api.scraper_registry import build_registry, resolve_event_scraper_keys
from gravity_api.services.scraper_prop_shop import COLLECTOR_MAP, STATE
from gravity_api.services.scraper_registry_service import (
    list_registry,
    manifest_summary,
    record_run_result,
    scraper_health_summary,
    sync_registry_to_db,
)

router = APIRouter()


async def require_ops(
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
    x_internal_key: Optional[str] = Header(None, alias="X-Internal-Key"),
):
    settings = get_settings()
    if x_internal_key and settings.internal_api_key and x_internal_key == settings.internal_api_key:
        return user_id
    row = await db.fetchrow("SELECT role FROM user_accounts WHERE id = $1", user_id)
    if not row or row["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin or X-Internal-Key required")
    return user_id


class AthleteJobBody(BaseModel):
    collectors: List[str] = Field(default_factory=list)
    sport: str = "cfb"
    use_registry: bool = True


@router.post("/jobs/athlete/{athlete_id}")
async def enqueue_athlete_job(
    athlete_id: str,
    body: AthleteJobBody,
    _: uuid.UUID = Depends(require_ops),
):
    try:
        uuid.UUID(athlete_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid athlete_id") from e
    if body.use_registry and not body.collectors:
        cols = resolve_event_scraper_keys("scheduled_full", body.sport)
    else:
        cols = body.collectors or COLLECTOR_MAP["scheduled_full"]
    STATE.enqueue(
        "P2",
        {
            "type": "athlete_rescrape",
            "athlete_id": athlete_id,
            "sport": body.sport,
            "collectors": cols,
            "scraper_keys": cols if body.use_registry else None,
        },
    )
    return {"ok": True, "queued": True, "priority": "P2", "scraper_keys": cols}


class EventBody(BaseModel):
    event_type: str
    athlete_id: Optional[str] = None
    sport: str = "cfb"
    source: str = "espn"
    payload: Dict[str, Any] = Field(default_factory=dict)
    use_registry: bool = True


@router.post("/jobs/event")
async def enqueue_event(
    body: EventBody,
    _: uuid.UUID = Depends(require_ops),
):
    pmap = {
        "transfer_portal": "P0",
        "injury_report": "P0",
        "nil_deal": "P1",
        "school_submission": "P2",
        "achievements_update": "P2",
        "roster_sync": "P1",
    }
    pr = pmap.get(body.event_type, "P3")
    if body.use_registry:
        scraper_keys = resolve_event_scraper_keys(body.event_type, body.sport)
        collectors = COLLECTOR_MAP.get(body.event_type, COLLECTOR_MAP["scheduled_full"])
    else:
        scraper_keys = None
        collectors = COLLECTOR_MAP.get(body.event_type, COLLECTOR_MAP["scheduled_full"])
    STATE.enqueue(
        pr,
        {
            "type": body.event_type,
            "athlete_id": body.athlete_id,
            "sport": body.sport,
            "source": body.source,
            "payload": body.payload,
            "collectors": collectors,
            "scraper_keys": scraper_keys,
        },
    )
    return {"ok": True, "priority": pr, "scraper_keys": scraper_keys}


@router.get("/jobs/queue/status")
async def queue_status(_: uuid.UUID = Depends(require_ops)):
    return {"depth_by_priority": STATE.queue_depth()}


@router.get("/jobs/circuits")
async def circuits(_: uuid.UUID = Depends(require_ops)):
    return {"circuits": STATE.circuit_states()}


@router.post("/jobs/circuits/{source}/reset")
async def reset_circuit(
    source: str,
    _: uuid.UUID = Depends(require_ops),
):
    c = STATE.circuits.get(source)
    if not c:
        raise HTTPException(status_code=404, detail="Unknown source")
    c.reset()
    return {"ok": True, "source": source}


@router.get("/jobs/delta-report/{date}")
async def delta_report(
    date: str,
    _: uuid.UUID = Depends(require_ops),
):
    return {
        "date": date,
        "athletes_changed": None,
        "note": "Wire to raw_athlete_data.field_hashes in gravity-scrapers",
    }


@router.get("/registry/manifest")
async def registry_manifest(_: uuid.UUID = Depends(require_ops)):
    """In-memory manifest (no DB required). gravity-scrapers can mirror this contract."""
    return {
        "summary": manifest_summary(),
        "scrapers": [d.to_dict() for d in build_registry()],
    }


@router.post("/registry/sync")
async def registry_sync(
    db: asyncpg.Connection = Depends(get_db),
    _: uuid.UUID = Depends(require_ops),
):
    try:
        result = await sync_registry_to_db(db)
    except asyncpg.UndefinedTableError as e:
        raise HTTPException(
            status_code=503,
            detail="Apply migration 027_scraper_registry.sql before syncing",
        ) from e
    return {"ok": True, **result}


@router.get("/registry")
async def registry_list(
    sport: Optional[str] = Query(None),
    league_tier: Optional[str] = Query(None),
    dimension: Optional[str] = Query(None),
    terminal_only: bool = Query(False),
    db: asyncpg.Connection = Depends(get_db),
    _: uuid.UUID = Depends(require_ops),
):
    try:
        rows = await list_registry(
            db,
            sport=sport,
            league_tier=league_tier,
            dimension=dimension,
            terminal_only=terminal_only,
        )
    except asyncpg.UndefinedTableError:
        rows = [d.to_dict() for d in build_registry()]
    return {"scrapers": rows, "count": len(rows)}


@router.get("/registry/health")
async def registry_health(
    hours: int = Query(24, ge=1, le=168),
    db: asyncpg.Connection = Depends(get_db),
    _: uuid.UUID = Depends(require_ops),
):
    try:
        summary = await scraper_health_summary(db, hours=hours)
    except asyncpg.UndefinedTableError:
        summary = []
    return {"hours": hours, "scrapers": summary}


class RunResultBody(BaseModel):
    scraper_key: str
    status: str = Field(..., pattern="^(success|partial|failed|skipped)$")
    athlete_id: Optional[str] = None
    job_id: Optional[str] = None
    sport: Optional[str] = None
    fields_written: List[str] = Field(default_factory=list)
    fields_failed: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


@router.post("/runs")
async def post_run_result(
    body: RunResultBody,
    db: asyncpg.Connection = Depends(get_db),
    _: uuid.UUID = Depends(require_ops),
):
    try:
        run_id = await record_run_result(
            db,
            scraper_key=body.scraper_key,
            status=body.status,
            athlete_id=body.athlete_id,
            job_id=body.job_id,
            sport=body.sport,
            fields_written=body.fields_written,
            fields_failed=body.fields_failed,
            error_message=body.error_message,
            duration_ms=body.duration_ms,
            metadata=body.metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except asyncpg.UndefinedTableError as e:
        raise HTTPException(
            status_code=503,
            detail="Apply migration 027_scraper_registry.sql before recording runs",
        ) from e
    return {"ok": True, "run_id": run_id}


class RunScrapersBody(BaseModel):
    event_type: str = "scheduled_full"
    scraper_keys: list[str] = Field(default_factory=list)
    persist: bool = True
    score_after: bool = True


class RosterSyncBody(BaseModel):
    sport: str = Field(default="cfb", description="cfb | ncaab_mens | ncaab_womens")
    sports: list[str] | None = Field(
        default=None,
        description="When team_ids empty: sync these sports from school index",
    )
    team_ids: list[str] = Field(default_factory=list, description="ESPN team ids")
    roster_season: str | None = None
    rescrape_transfers: bool = True


@router.post("/run/{athlete_id}")
async def run_athlete_scrapers(
    athlete_id: str,
    body: RunScrapersBody,
    db: asyncpg.Connection = Depends(get_db),
    _: uuid.UUID = Depends(require_ops),
):
    """Execute micro-scrapers for one athlete (Firecrawl + ESPN + parsers)."""
    try:
        uuid.UUID(athlete_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid athlete_id") from e
    from gravity_api.scrapers.orchestrator import run_scrapers_for_athlete

    try:
        summary = await run_scrapers_for_athlete(
            db,
            athlete_id,
            event_type=body.event_type,
            scraper_keys=body.scraper_keys or None,
            persist=body.persist,
            score_after=body.score_after,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return summary


@router.post("/jobs/roster-sync")
async def run_roster_sync_job(
    body: RosterSyncBody,
    db: asyncpg.Connection = Depends(get_db),
    _: uuid.UUID = Depends(require_ops),
):
    """In-process ESPN roster sync (replaces gravity-scrapers POST /jobs/roster-sync)."""
    from gravity_api.scrapers.orchestrator import run_scrapers_for_athlete
    from gravity_api.scrapers.roster.school_index import default_team_ids_for_sport
    from gravity_api.services.roster_sync import sync_power5_sports, sync_sport_rosters

    async def _rescrape(conn: asyncpg.Connection, athlete_id: str) -> None:
        await run_scrapers_for_athlete(
            conn,
            athlete_id,
            event_type="roster_sync",
            score_after=True,
        )

    team_ids = [t.strip() for t in body.team_ids if t.strip()]
    if not team_ids:
        team_ids = default_team_ids_for_sport(body.sport)

    rescrape_fn = _rescrape if body.rescrape_transfers else None
    if team_ids:
        result = await sync_sport_rosters(
            db,
            body.sport,
            team_ids,
            roster_season=body.roster_season,
            rescrape_transfers=rescrape_fn,
        )
    else:
        results = await sync_power5_sports(
            db,
            body.sports,
            roster_season=body.roster_season,
            rescrape_transfers=rescrape_fn,
        )
        result = {"sports": results, "count": len(results)}
    return {"ok": True, "result": result}
