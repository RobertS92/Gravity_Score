import uuid
from typing import Any, List

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from gravity_api.auth_deps import optional_user_id
from gravity_api.database import get_db

router = APIRouter()


async def _fetch_alerts(db: asyncpg.Connection, uid: uuid.UUID) -> dict[str, Any]:
    rows = await db.fetch(
        """SELECT sa.*, a.name AS athlete_name
           FROM score_alerts sa
           JOIN athletes a ON a.id = sa.athlete_id
           WHERE sa.user_id = $1
           ORDER BY sa.created_at DESC
           LIMIT 100""",
        uid,
    )
    unread = sum(1 for r in rows if not r["read"])
    return {"unread": unread, "items": [dict(r) for r in rows]}


@router.get("/")
async def get_alerts(
    db: asyncpg.Connection = Depends(get_db),
    effective_user: uuid.UUID | None = Depends(optional_user_id),
):
    if not effective_user:
        return {"unread": 0, "items": []}
    return await _fetch_alerts(db, effective_user)


@router.get("/{user_id}")
async def get_alerts_by_path(user_id: str, db: asyncpg.Connection = Depends(get_db)):
    try:
        uid = uuid.UUID(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="user_id must be UUID") from e
    return await _fetch_alerts(db, uid)
