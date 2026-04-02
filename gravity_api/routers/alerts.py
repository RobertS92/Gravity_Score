import uuid
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from gravity_api.database import get_db

router = APIRouter()


@router.get("/")
async def get_alerts(
    user_id: Optional[str] = None,
    db: asyncpg.Connection = Depends(get_db),
):
    if not user_id:
        return {"unread": 0, "items": []}
    try:
        uid = uuid.UUID(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="user_id must be UUID") from e
    rows = await db.fetch(
        """SELECT * FROM score_alerts
           WHERE user_id = $1
           ORDER BY created_at DESC
           LIMIT 100""",
        uid,
    )
    unread = sum(1 for r in rows if not r["read"])
    return {"unread": unread, "items": [dict(r) for r in rows]}
