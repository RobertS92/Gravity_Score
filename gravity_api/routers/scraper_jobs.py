"""Scraper pipeline control plane (queue + circuits). gravity-scrapers should mirror for production."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from gravity_api.auth_deps import require_user_id
from gravity_api.config import get_settings
from gravity_api.database import get_db
from gravity_api.services.scraper_prop_shop import COLLECTOR_MAP, STATE

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
    cols = body.collectors or COLLECTOR_MAP["scheduled_full"]
    STATE.enqueue(
        "P2",
        {"type": "athlete_rescrape", "athlete_id": athlete_id, "collectors": cols},
    )
    return {"ok": True, "queued": True, "priority": "P2"}


class EventBody(BaseModel):
    event_type: str
    athlete_id: Optional[str] = None
    source: str = "espn"
    payload: Dict[str, Any] = Field(default_factory=dict)


@router.post("/jobs/event")
async def enqueue_event(
    body: EventBody,
    _: uuid.UUID = Depends(require_ops),
):
    pmap = {"transfer_portal": "P0", "injury_report": "P0", "nil_deal": "P1", "school_submission": "P2"}
    pr = pmap.get(body.event_type, "P3")
    collectors = COLLECTOR_MAP.get(body.event_type, COLLECTOR_MAP["scheduled_full"])
    STATE.enqueue(
        pr,
        {
            "type": body.event_type,
            "athlete_id": body.athlete_id,
            "source": body.source,
            "payload": body.payload,
            "collectors": collectors,
        },
    )
    return {"ok": True, "priority": pr}


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
