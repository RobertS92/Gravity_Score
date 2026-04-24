import asyncpg
from fastapi import APIRouter, Depends, Query

from gravity_api.database import get_db

router = APIRouter()


@router.get("")
@router.get("/", include_in_schema=False)
async def list_deals(
    athlete_id: str | None = None,
    limit: int = Query(50, le=200),
    db: asyncpg.Connection = Depends(get_db),
):
    if athlete_id:
        rows = await db.fetch(
            """SELECT * FROM athlete_nil_deals
               WHERE athlete_id = $1
               ORDER BY ingested_at DESC LIMIT $2""",
            athlete_id,
            limit,
        )
    else:
        rows = await db.fetch(
            """SELECT * FROM athlete_nil_deals
               ORDER BY ingested_at DESC LIMIT $1""",
            limit,
        )
    return {"deals": [dict(r) for r in rows]}
