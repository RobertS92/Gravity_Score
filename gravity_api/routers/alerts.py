import uuid
from typing import Any, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from gravity_api.auth_deps import require_user_id
from gravity_api.database import get_db
from gravity_api.services.sport_query import cap_prefs_to_db_slugs

router = APIRouter()


async def _fetch_alerts(
    db: asyncpg.Connection,
    uid: uuid.UUID,
    sports_db: Optional[List[str]] = None,
) -> dict[str, Any]:
    sport_clause = ""
    params: List[Any] = [uid]
    if sports_db:
        sport_clause = " AND a.sport = ANY($2::text[])"
        params.append(sports_db)
    rows = await db.fetch(
        f"""SELECT sa.*, a.name AS athlete_name
           FROM score_alerts sa
           JOIN athletes a ON a.id = sa.athlete_id
           INNER JOIN watchlists w ON w.athlete_id = sa.athlete_id AND w.user_id = sa.user_id
           WHERE sa.user_id = $1 {sport_clause}
           ORDER BY sa.created_at DESC
           LIMIT 100""",
        *params,
    )
    unread = sum(1 for r in rows if not r["read"])
    return {"unread": unread, "items": [dict(r) for r in rows]}


@router.get("")
@router.get("/", include_in_schema=False)
async def get_alerts(
    db: asyncpg.Connection = Depends(get_db),
    effective_user: uuid.UUID = Depends(require_user_id),
    sports: str | None = Query(
        None,
        description="Comma-separated CFB,NCAAB,NCAAW — filter alerts to athletes in those sports",
    ),
):
    sports_db = None
    if sports and sports.strip():
        sports_db = cap_prefs_to_db_slugs([s.strip() for s in sports.split(",") if s.strip()])
    return await _fetch_alerts(db, effective_user, sports_db=sports_db)


@router.get("/{user_id}")
async def get_alerts_by_path(
    user_id: str,
    db: asyncpg.Connection = Depends(get_db),
    effective_user: uuid.UUID = Depends(require_user_id),
):
    """Path-style alias kept for legacy clients. Caller may only read their own alerts."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="user_id must be UUID") from e
    if uid != effective_user:
        raise HTTPException(status_code=403, detail="Cannot read alerts for another user")
    return await _fetch_alerts(db, uid, sports_db=None)
