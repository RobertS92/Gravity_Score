"""Team favorites — schools/programs the authenticated user is following.

Used by the live feed to surface team-level news (and athlete events
for everyone on those rosters), in addition to the user's per-athlete
watchlist.
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from gravity_api.auth_deps import require_user_id
from gravity_api.database import get_db

router = APIRouter()


class TeamFavoriteAddBody(BaseModel):
    team_id: str


def _rec_get(r: asyncpg.Record, key: str) -> Any:
    return r[key] if key in r.keys() else None


def _team_row(r: asyncpg.Record) -> dict[str, Any]:
    return {
        "team_id": str(r["team_id"]),
        "school_name": _rec_get(r, "school_name"),
        "short_name": _rec_get(r, "short_name"),
        "sport": _rec_get(r, "sport"),
        "conference": _rec_get(r, "conference"),
        "logo_url": _rec_get(r, "logo_url"),
        "created_at": r["created_at"].isoformat() if _rec_get(r, "created_at") else None,
    }


@router.get("")
@router.get("/", include_in_schema=False)
async def list_team_favorites(
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    rows = await db.fetch(
        """SELECT tf.team_id, tf.created_at,
                  t.school_name, t.sport, t.conference
           FROM team_favorites tf
           JOIN teams t ON t.id = tf.team_id
           WHERE tf.user_id = $1
           ORDER BY tf.created_at DESC""",
        user_id,
    )
    return {"teams": [_team_row(r) for r in rows]}


@router.post("")
@router.post("/", include_in_schema=False)
async def add_team_favorite(
    body: TeamFavoriteAddBody,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    try:
        team_uuid = uuid.UUID(body.team_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid team_id") from e

    exists = await db.fetchval("SELECT 1 FROM teams WHERE id = $1", team_uuid)
    if not exists:
        raise HTTPException(status_code=404, detail="Team not found")

    await db.execute(
        """INSERT INTO team_favorites (user_id, team_id)
           VALUES ($1, $2)
           ON CONFLICT (user_id, team_id) DO NOTHING""",
        user_id,
        team_uuid,
    )
    row = await db.fetchrow(
        """SELECT tf.team_id, tf.created_at,
                  t.school_name, t.sport, t.conference
           FROM team_favorites tf
           JOIN teams t ON t.id = tf.team_id
           WHERE tf.user_id = $1 AND tf.team_id = $2""",
        user_id,
        team_uuid,
    )
    if row is None:
        raise HTTPException(status_code=500, detail="Failed to record favorite")
    return _team_row(row)


@router.delete("/{team_id}")
async def remove_team_favorite(
    team_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid team_id") from e

    result = await db.execute(
        "DELETE FROM team_favorites WHERE user_id = $1 AND team_id = $2",
        user_id,
        team_uuid,
    )
    deleted = int(result.split()[-1]) if result else 0
    return {"ok": True, "deleted": deleted}
