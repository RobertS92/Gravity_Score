"""Watchlist — requires authenticated user_accounts row."""

import uuid
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from gravity_api.database import get_db

router = APIRouter()


@router.get("/")
async def get_watchlist(
    user_id: Optional[str] = None,
    db: asyncpg.Connection = Depends(get_db),
):
    if not user_id:
        return {"athletes": []}
    try:
        uid = uuid.UUID(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="user_id must be UUID") from e
    rows = await db.fetch(
        """SELECT w.*, a.name, a.school, a.sport
           FROM watchlists w
           JOIN athletes a ON a.id = w.athlete_id
           WHERE w.user_id = $1
           ORDER BY w.created_at DESC""",
        uid,
    )
    return {"athletes": [dict(r) for r in rows]}
