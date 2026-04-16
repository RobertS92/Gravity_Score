import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException

from gravity_api.config import get_settings
from gravity_api.database import get_db
from gravity_api.services.athlete_score_sync import sync_athlete_score_from_ml

router = APIRouter()


def _require_internal_key(x_gravity_internal_key: str | None = Header(None)) -> None:
    settings = get_settings()
    expected = settings.internal_api_key
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Set GRAVITY_INTERNAL_API_KEY to enable score sync",
        )
    if not x_gravity_internal_key or x_gravity_internal_key != expected:
        raise HTTPException(status_code=403, detail="Invalid X-Gravity-Internal-Key")


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


@router.post("/athletes/{athlete_id}/sync-from-ml")
async def sync_score_from_ml(
    athlete_id: str,
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(_require_internal_key),
):
    """Append a score row from gravity-ml (athlete + optional program/company gravity)."""
    try:
        return await sync_athlete_score_from_ml(db, athlete_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
