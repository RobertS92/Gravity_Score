from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends

from gravity_api.database import get_db

router = APIRouter()


@router.get("/")
async def list_programs(
    sport: Optional[str] = None,
    db: asyncpg.Connection = Depends(get_db),
):
    if sport:
        rows = await db.fetch(
            "SELECT * FROM programs WHERE sport = $1 ORDER BY school", sport
        )
    else:
        rows = await db.fetch("SELECT * FROM programs ORDER BY conference, school")
    return {"programs": [dict(r) for r in rows]}
