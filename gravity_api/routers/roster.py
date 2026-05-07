"""Roster Builder — save, load, and score NIL rosters."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from gravity_api.auth_deps import require_user_id
from gravity_api.config import get_settings
from gravity_api.database import get_db
from gravity_api.services.roster_lifecycle import (
    RosterLifecycleInput,
    apply_roster_lifecycle_sync,
    backfill_active_athlete_scores,
)
from gravity_api.services.roster_value import score_roster

router = APIRouter()


def _require_internal_key(x_gravity_internal_key: str | None = Header(None)) -> None:
    settings = get_settings()
    expected = settings.internal_api_key
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Set GRAVITY_INTERNAL_API_KEY to enable roster lifecycle sync",
        )
    if not x_gravity_internal_key or x_gravity_internal_key != expected:
        raise HTTPException(status_code=403, detail="Invalid X-Gravity-Internal-Key")


async def _score_and_prune_slots(
    db: asyncpg.Connection,
    slots: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Drop slots for athletes with is_active=false (transfer, draft, etc.) or missing rows;
    re-score so returned payload matches persisted roster.
    """
    scored = await score_roster(db, slots)
    removed = scored.get("removed_athletes") or []
    if not removed:
        return scored, slots
    dead = {str(x["athlete_id"]) for x in removed}
    pruned = [s for s in slots if str(s.get("athlete_id")) not in dead]
    if len(pruned) == len(slots):
        return scored, slots
    scored = await score_roster(db, pruned)
    return scored, pruned


def _slots_json(slots: list[dict[str, Any]]) -> str:
    return json.dumps(
        [
            {"athlete_id": str(s["athlete_id"]), "nil_cost_override": s.get("nil_cost_override")}
            for s in slots
        ]
    )


def _slots_response(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Shape stored in roster_builds.slots (client sync)."""
    return [
        {"athlete_id": str(s["athlete_id"]), "nil_cost_override": s.get("nil_cost_override")}
        for s in slots
    ]


class RosterSlot(BaseModel):
    athlete_id: str
    nil_cost_override: Optional[float] = None


class RosterSaveBody(BaseModel):
    id: Optional[str] = None          # if provided, update existing
    name: str = Field(default="My Roster", max_length=120)
    budget_usd: float = Field(default=1_000_000, ge=0)
    slots: List[RosterSlot] = Field(default_factory=list)


class RosterLifecycleAthlete(BaseModel):
    athlete_id: str
    lifecycle_status: str = Field(
        default="active_on_roster",
        pattern="^(active_on_roster|transferred|left_for_draft|graduated|out_other)$",
    )
    is_active: bool = True
    school: Optional[str] = None
    conference: Optional[str] = None
    sport: Optional[str] = None
    status_reason: Optional[str] = None


class RosterLifecycleSyncBody(BaseModel):
    athletes: list[RosterLifecycleAthlete] = Field(default_factory=list)
    sport_scope: Optional[str] = None
    verified_at: Optional[datetime] = None
    mode: str = Field(default="replace_scope", pattern="^(replace_scope|patch)$")
    trigger_rescore: bool = True


class RosterScoreBackfillBody(BaseModel):
    limit: int = Field(default=250, ge=1, le=5000)
    sport: Optional[str] = None


@router.get("")
@router.get("/", include_in_schema=False)
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
    scored, pruned = await _score_and_prune_slots(db, slots)
    if len(pruned) != len(slots):
        await db.execute(
            """UPDATE roster_builds
               SET slots = $1::jsonb, updated_at = NOW()
               WHERE id = $2 AND user_id = $3""",
            _slots_json(pruned),
            rid,
            user_id,
        )

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "budget_usd": float(row["budget_usd"]),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "slots": _slots_response(pruned),
        **scored,
    }


@router.post("")
@router.post("/", include_in_schema=False)
async def save_roster(
    body: RosterSaveBody,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    """Create or update a roster. Returns the roster with full scoring."""
    slots_raw = [
        {"athlete_id": s.athlete_id, "nil_cost_override": s.nil_cost_override}
        for s in body.slots
    ]
    scored, slots_final = await _score_and_prune_slots(db, slots_raw)
    slots_json = _slots_json(slots_final)

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

    return {
        "id": str(final_id),
        "name": body.name,
        "budget_usd": body.budget_usd,
        "slots": _slots_response(slots_final),
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
    scored, pruned = await _score_and_prune_slots(db, slots_raw)
    return {
        "name": body.name,
        "budget_usd": body.budget_usd,
        "slots": _slots_response(pruned),
        **scored,
    }


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


@router.post("/lifecycle/sync")
async def sync_roster_lifecycle(
    body: RosterLifecycleSyncBody,
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    """
    Authoritative roster lifecycle sync.
    - Updates school/conference/sport + active status for known athletes.
    - Tracks lifecycle status (transfer, draft, graduation, out).
    - Stamps roster_verified_at for processed athletes.
    - In replace_scope mode, marks out-of-scope athletes inactive for the given sport.
    - Optionally triggers score refresh for changed active athletes.
    """
    inputs = [
        RosterLifecycleInput(
            athlete_id=row.athlete_id,
            lifecycle_status=row.lifecycle_status,
            is_active=row.is_active,
            school=row.school,
            conference=row.conference,
            sport=row.sport,
            status_reason=row.status_reason,
        )
        for row in body.athletes
    ]
    try:
        return await apply_roster_lifecycle_sync(
            db,
            inputs,
            sport_scope=body.sport_scope,
            verified_at=body.verified_at,
            mode=body.mode,
            trigger_rescore=body.trigger_rescore,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/lifecycle/backfill-scores")
async def backfill_roster_scores(
    body: RosterScoreBackfillBody,
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    """
    Backfill missing athlete_gravity_scores rows for active athletes.
    Use after major roster imports or when score coverage drifts.
    """
    return await backfill_active_athlete_scores(
        db,
        limit=body.limit,
        sport=body.sport,
    )
