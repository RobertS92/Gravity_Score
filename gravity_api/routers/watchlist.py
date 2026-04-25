"""Watchlist — add, remove, and list watchlisted athletes per user."""

import uuid
from typing import Any, List

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from gravity_api.auth_deps import optional_user_id, require_user_id
from gravity_api.database import get_db

router = APIRouter()


class WatchlistAddBody(BaseModel):
    athlete_id: str


async def _fetch_watchlist(db: asyncpg.Connection, uid: uuid.UUID) -> List[dict[str, Any]]:
    rows = await db.fetch(
        """SELECT w.athlete_id, a.name, a.school, a.sport, a.position, a.conference,
                  s.gravity_score, s.brand_score, s.proof_score,
                  s.proximity_score, s.velocity_score, s.risk_score,
                  s.company_gravity_score, s.brand_gravity_score,
                  s.dollar_p10_usd, s.dollar_p50_usd, s.dollar_p90_usd
           FROM watchlists w
           JOIN athletes a ON a.id = w.athlete_id
           LEFT JOIN LATERAL (
               SELECT * FROM athlete_gravity_scores
               WHERE athlete_id = a.id
               ORDER BY calculated_at DESC LIMIT 1
           ) s ON true
           WHERE w.user_id = $1
           ORDER BY w.created_at DESC""",
        uid,
    )
    return [dict(r) for r in rows]


@router.get("")
@router.get("/", include_in_schema=False)
async def get_watchlist(
    db: asyncpg.Connection = Depends(get_db),
    effective_user: uuid.UUID | None = Depends(optional_user_id),
):
    if not effective_user:
        return {"athletes": []}
    return {"athletes": await _fetch_watchlist(db, effective_user)}


@router.post("")
@router.post("/", include_in_schema=False)
async def add_to_watchlist(
    body: WatchlistAddBody,
    db: asyncpg.Connection = Depends(get_db),
    effective_user: uuid.UUID = Depends(require_user_id),
):
    """Add an athlete to the authenticated user's watchlist."""
    try:
        athlete_uuid = uuid.UUID(body.athlete_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid athlete_id") from e

    exists = await db.fetchval(
        "SELECT 1 FROM athletes WHERE id = $1", athlete_uuid
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Athlete not found")

    await db.execute(
        """INSERT INTO watchlists (user_id, athlete_id)
           VALUES ($1, $2)
           ON CONFLICT (user_id, athlete_id) DO NOTHING""",
        effective_user,
        athlete_uuid,
    )
    return {"ok": True, "athlete_id": body.athlete_id}


@router.delete("/{athlete_id}")
async def remove_from_watchlist(
    athlete_id: str,
    db: asyncpg.Connection = Depends(get_db),
    effective_user: uuid.UUID = Depends(require_user_id),
):
    """Remove an athlete from the authenticated user's watchlist."""
    try:
        athlete_uuid = uuid.UUID(athlete_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid athlete_id") from e

    result = await db.execute(
        "DELETE FROM watchlists WHERE user_id = $1 AND athlete_id = $2",
        effective_user,
        athlete_uuid,
    )
    deleted = int(result.split()[-1]) if result else 0
    return {"ok": True, "deleted": deleted}


@router.get("/{user_id}")
async def get_watchlist_by_path(
    user_id: str,
    db: asyncpg.Connection = Depends(get_db),
    effective_user: uuid.UUID = Depends(require_user_id),
):
    """Path-style alias kept for legacy clients. Caller may only read their own watchlist."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="user_id must be UUID") from e
    if uid != effective_user:
        raise HTTPException(status_code=403, detail="Cannot read watchlist for another user")
    return {"athletes": await _fetch_watchlist(db, uid)}
