import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from gravity_api.database import get_db

router = APIRouter()


@router.get("/{athlete_id}/latest")
async def latest_score(athlete_id: str, db: asyncpg.Connection = Depends(get_db)):
    row = await db.fetchrow(
        """SELECT * FROM athlete_gravity_scores
           WHERE athlete_id = $1
           ORDER BY calculated_at DESC LIMIT 1""",
        athlete_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No score for athlete")
    return dict(row)
