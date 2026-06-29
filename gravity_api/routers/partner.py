"""Partner API — Gravity Score distribution for third-party sites.

Authenticate with ``Authorization: Bearer <partner_api_key>``.

Keys are issued via ``POST /v2/partner/admin/keys`` (internal) or the
``GRAVITY_PARTNER_API_KEY`` env bootstrap for development.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from gravity_api.config import get_settings
from gravity_api.database import get_db
from gravity_api.partner_auth import require_partner, require_scope
from gravity_api.partner_types import PartnerContext
from gravity_api.services.athlete_search import search_athletes as run_athlete_search
from gravity_api.services.partner_api import (
    ATTRIBUTION_TEXT,
    ATTRIBUTION_URL,
    create_partner_api_key,
    format_partner_athlete_detail,
    format_partner_athlete_summary,
    format_partner_score_row,
    format_score_history_point,
)
from gravity_api.services.sport_query import cap_prefs_to_db_slugs

router = APIRouter()


class CreatePartnerKeyBody(BaseModel):
    partner_name: str = Field(..., min_length=1, max_length=200)
    scopes: List[str] = Field(default_factory=lambda: ["scores:read", "search:read"])
    allowed_origins: Optional[List[str]] = None
    rate_limit_per_minute: int = Field(default=120, ge=1, le=10000)
    expires_at: Optional[datetime] = None


def _require_internal_key(x_gravity_internal_key: str | None = Header(None)) -> None:
    settings = get_settings()
    expected = settings.internal_api_key
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Set GRAVITY_INTERNAL_API_KEY to manage partner keys",
        )
    if not x_gravity_internal_key or x_gravity_internal_key != expected:
        raise HTTPException(status_code=403, detail="Invalid X-Gravity-Internal-Key")


@router.get("/health")
async def partner_health():
    """Public health check for partner integrations (no auth)."""
    return {
        "status": "ok",
        "service": "gravity-partner-api",
        "version": "1.0.0",
        "attribution": {"text": ATTRIBUTION_TEXT, "url": ATTRIBUTION_URL},
    }


@router.get("/athletes")
async def partner_search_athletes(
    q: Optional[str] = None,
    sport: Optional[str] = None,
    sports: Optional[str] = Query(
        None,
        description="Comma-separated cap codes: CFB,NCAAB,NCAAW",
    ),
    school: Optional[str] = None,
    min_gravity: Optional[float] = None,
    max_gravity: Optional[float] = None,
    sort_by: str = "gravity_score",
    sort_dir: str = "desc",
    limit: int = Query(default=25, le=100),
    offset: int = 0,
    db: asyncpg.Connection = Depends(get_db),
    partner: PartnerContext = Depends(require_partner),
):
    require_scope(partner, "search:read")
    sports_db: Optional[List[str]] = None
    if not sport and sports and sports.strip():
        sports_db = cap_prefs_to_db_slugs([s.strip() for s in sports.split(",") if s.strip()])
    raw = await run_athlete_search(
        db,
        q=q,
        sport=sport,
        sports_db=sports_db,
        school=school,
        min_gravity=min_gravity,
        max_gravity=max_gravity,
        exclude_inactive=True,
        roster_verified_within_days=None if (q and q.strip()) else 14,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    athletes = [format_partner_athlete_summary(row) for row in raw["athletes"]]
    return {
        "athletes": athletes,
        "total": raw["total"],
        "returned": raw["returned"],
        "offset": offset,
        "limit": limit,
        "attribution": {"text": ATTRIBUTION_TEXT, "url": ATTRIBUTION_URL},
    }


@router.get("/athletes/resolve")
async def partner_resolve_athlete(
    name: str = Query(..., min_length=1, max_length=200),
    school: Optional[str] = None,
    sport: Optional[str] = None,
    limit: int = Query(default=5, le=20),
    db: asyncpg.Connection = Depends(get_db),
    partner: PartnerContext = Depends(require_partner),
):
    """Resolve athlete identity by name (and optional school/sport)."""
    require_scope(partner, "search:read")
    raw = await run_athlete_search(
        db,
        q=name.strip(),
        sport=sport,
        school=school,
        exclude_inactive=True,
        roster_verified_within_days=None,
        sort_by="gravity_score",
        sort_dir="desc",
        limit=limit,
        offset=0,
    )
    matches = [format_partner_athlete_summary(row) for row in raw["athletes"]]
    return {
        "query": {"name": name, "school": school, "sport": sport},
        "matches": matches,
        "attribution": {"text": ATTRIBUTION_TEXT, "url": ATTRIBUTION_URL},
    }


@router.get("/athletes/{athlete_id}")
async def partner_get_athlete(
    athlete_id: str,
    db: asyncpg.Connection = Depends(get_db),
    partner: PartnerContext = Depends(require_partner),
):
    require_scope(partner, "scores:read")
    athlete = await db.fetchrow("SELECT * FROM athletes WHERE id = $1", athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    latest = await db.fetchrow(
        """SELECT athlete_id, gravity_score, brand_score, proof_score,
                  proximity_score, velocity_score, risk_score,
                  confidence, model_version, calculated_at,
                  dollar_p10_usd, dollar_p50_usd, dollar_p90_usd
           FROM athlete_gravity_scores
           WHERE athlete_id = $1
           ORDER BY calculated_at DESC
           LIMIT 1""",
        athlete_id,
    )
    return format_partner_athlete_detail(athlete, latest)


@router.get("/scores/{athlete_id}")
async def partner_latest_score(
    athlete_id: str,
    db: asyncpg.Connection = Depends(get_db),
    partner: PartnerContext = Depends(require_partner),
):
    require_scope(partner, "scores:read")
    exists = await db.fetchval("SELECT 1 FROM athletes WHERE id = $1", athlete_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Athlete not found")
    row = await db.fetchrow(
        """SELECT athlete_id, gravity_score, brand_score, proof_score,
                  proximity_score, velocity_score, risk_score,
                  confidence, model_version, calculated_at,
                  dollar_p10_usd, dollar_p50_usd, dollar_p90_usd
           FROM athlete_gravity_scores
           WHERE athlete_id = $1
           ORDER BY calculated_at DESC
           LIMIT 1""",
        athlete_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No score for athlete")
    return format_partner_score_row(row)


@router.get("/athletes/{athlete_id}/score-history")
async def partner_score_history(
    athlete_id: str,
    weeks: int = Query(default=12, le=52),
    db: asyncpg.Connection = Depends(get_db),
    partner: PartnerContext = Depends(require_partner),
):
    require_scope(partner, "scores:read")
    exists = await db.fetchval("SELECT 1 FROM athletes WHERE id = $1", athlete_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Athlete not found")
    rows = await db.fetch(
        """SELECT gravity_score, brand_score, proof_score,
                  proximity_score, velocity_score, risk_score,
                  confidence, calculated_at
           FROM athlete_gravity_scores
           WHERE athlete_id = $1
           ORDER BY calculated_at DESC
           LIMIT $2""",
        athlete_id,
        weeks,
    )
    return {
        "athlete_id": athlete_id,
        "history": [format_score_history_point(r) for r in rows],
        "attribution": {"text": ATTRIBUTION_TEXT, "url": ATTRIBUTION_URL},
    }


@router.post("/admin/keys")
async def create_partner_key(
    body: CreatePartnerKeyBody,
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    """Issue a new partner API key (internal only). Raw key returned once."""
    try:
        return await create_partner_api_key(
            db,
            partner_name=body.partner_name,
            scopes=body.scopes,
            allowed_origins=body.allowed_origins,
            rate_limit_per_minute=body.rate_limit_per_minute,
            expires_at=body.expires_at,
        )
    except asyncpg.UndefinedTableError:
        raise HTTPException(
            status_code=503,
            detail="Apply migration 033_partner_api.sql before creating keys",
        ) from None


@router.get("/admin/keys")
async def list_partner_keys(
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    """List partner keys (prefix only — never the raw secret)."""
    try:
        rows = await db.fetch(
            """SELECT id, partner_name, key_prefix, scopes, allowed_origins,
                      rate_limit_per_minute, is_active, created_at, last_used_at, expires_at
               FROM partner_api_keys
               ORDER BY created_at DESC"""
        )
    except asyncpg.UndefinedTableError:
        raise HTTPException(
            status_code=503,
            detail="Apply migration 033_partner_api.sql before listing keys",
        ) from None
    return {
        "keys": [
            {
                "id": str(r["id"]),
                "partner_name": r["partner_name"],
                "key_prefix": r["key_prefix"],
                "scopes": list(r["scopes"] or []),
                "allowed_origins": list(r["allowed_origins"] or []),
                "rate_limit_per_minute": r["rate_limit_per_minute"],
                "is_active": r["is_active"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "last_used_at": r["last_used_at"].isoformat() if r["last_used_at"] else None,
                "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
            }
            for r in rows
        ]
    }
