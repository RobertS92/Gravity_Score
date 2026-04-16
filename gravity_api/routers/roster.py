"""Roster Builder — save, load, and score NIL rosters."""

from __future__ import annotations

import uuid
from typing import Any, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from gravity_api.auth_deps import require_user_id
from gravity_api.database import get_db
from gravity_api.services.roster_value import score_roster

router = APIRouter()


class RosterSlot(BaseModel):
    athlete_id: str
    nil_cost_override: Optional[float] = None


class RosterSaveBody(BaseModel):
    id: Optional[str] = None          # if provided, update existing
    name: str = Field(default="My Roster", max_length=120)
    budget_usd: float = Field(default=1_000_000, ge=0)
    slots: List[RosterSlot] = Field(default_factory=list)


@router.get("/")
async def list_rosters(
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    """Return all saved rosters for the authenticated user (summary only)."""
    rows = await db.fetch(
        """SELECT id, name, budget_usd, jsonb_array_length(slots) AS slot_count,
                  created_at, updated_at
           FROM roster_builds
           WHERE user_id = $1
           ORDER BY updated_at DESC""",
        user_id,
    )
    return {
        "rosters": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "budget_usd": float(r["budget_usd"]),
                "slot_count": r["slot_count"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rows
        ]
    }


@router.get("/{roster_id}")
async def get_roster(
    roster_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    """Return a roster with full scoring applied to each slot."""
    try:
        rid = uuid.UUID(roster_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid roster_id") from exc

    row = await db.fetchrow(
        "SELECT * FROM roster_builds WHERE id = $1 AND user_id = $2",
        rid,
        user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Roster not found")

    slots: List[dict[str, Any]] = row["slots"] or []
    scored = await score_roster(db, slots)

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "budget_usd": float(row["budget_usd"]),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        **scored,
    }


@router.post("/")
async def save_roster(
    body: RosterSaveBody,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    """Create or update a roster. Returns the roster with full scoring."""
    import json

    slots_json = json.dumps(
        [{"athlete_id": s.athlete_id, "nil_cost_override": s.nil_cost_override}
         for s in body.slots]
    )

    if body.id:
        try:
            rid = uuid.UUID(body.id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid id") from exc

        row = await db.fetchrow(
            """UPDATE roster_builds
               SET name=$1, budget_usd=$2, slots=$3::jsonb, updated_at=NOW()
               WHERE id=$4 AND user_id=$5
               RETURNING id""",
            body.name,
            body.budget_usd,
            slots_json,
            rid,
            user_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Roster not found")
        final_id = rid
    else:
        row = await db.fetchrow(
            """INSERT INTO roster_builds (user_id, name, budget_usd, slots)
               VALUES ($1, $2, $3, $4::jsonb)
               RETURNING id""",
            user_id,
            body.name,
            body.budget_usd,
            slots_json,
        )
        final_id = row["id"]

    slots_raw = [
        {"athlete_id": s.athlete_id, "nil_cost_override": s.nil_cost_override}
        for s in body.slots
    ]
    scored = await score_roster(db, slots_raw)

    return {
        "id": str(final_id),
        "name": body.name,
        "budget_usd": body.budget_usd,
        **scored,
    }


@router.post("/score")
async def score_roster_preview(
    body: RosterSaveBody,
    db: asyncpg.Connection = Depends(get_db),
    _user_id: uuid.UUID = Depends(require_user_id),
):
    """Score a roster without saving. Used for real-time preview."""
    slots_raw = [
        {"athlete_id": s.athlete_id, "nil_cost_override": s.nil_cost_override}
        for s in body.slots
    ]
    scored = await score_roster(db, slots_raw)
    return {"name": body.name, "budget_usd": body.budget_usd, **scored}


@router.delete("/{roster_id}")
async def delete_roster(
    roster_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    try:
        rid = uuid.UUID(roster_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid roster_id") from exc

    result = await db.execute(
        "DELETE FROM roster_builds WHERE id=$1 AND user_id=$2",
        rid,
        user_id,
    )
    deleted = int(result.split()[-1]) if result else 0
    if not deleted:
        raise HTTPException(status_code=404, detail="Roster not found")
    return {"ok": True}
