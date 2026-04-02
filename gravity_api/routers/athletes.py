from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from gravity_api.database import get_db

router = APIRouter()

_VALID_SORTS = {
    "gravity_score": "s.gravity_score",
    "brand_score": "s.brand_score",
    "proof_score": "s.proof_score",
    "proximity_score": "s.proximity_score",
    "velocity_score": "s.velocity_score",
    "risk_score": "s.risk_score",
    "name": "a.name",
}


@router.get("/")
async def search_athletes(
    q: Optional[str] = None,
    sport: Optional[str] = None,
    conference: Optional[str] = None,
    position_group: Optional[str] = None,
    school: Optional[str] = None,
    min_gravity: Optional[float] = None,
    max_gravity: Optional[float] = None,
    min_brand: Optional[float] = None,
    max_risk: Optional[float] = None,
    sort_by: str = "gravity_score",
    sort_dir: str = "desc",
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: asyncpg.Connection = Depends(get_db),
):
    """Search athletes with filters — terminal search and leaderboards."""
    conditions: list[str] = []
    params: list = []
    idx = 1

    if q:
        conditions.append(f"a.name ILIKE ${idx}")
        params.append(f"%{q}%")
        idx += 1
    if sport:
        conditions.append(f"a.sport = ${idx}")
        params.append(sport)
        idx += 1
    if conference:
        conditions.append(f"a.conference = ${idx}")
        params.append(conference)
        idx += 1
    if position_group:
        conditions.append(f"a.position_group = ${idx}")
        params.append(position_group)
        idx += 1
    if school:
        conditions.append(f"a.school ILIKE ${idx}")
        params.append(f"%{school}%")
        idx += 1
    if min_gravity is not None:
        conditions.append(f"s.gravity_score >= ${idx}")
        params.append(min_gravity)
        idx += 1
    if max_gravity is not None:
        conditions.append(f"s.gravity_score <= ${idx}")
        params.append(max_gravity)
        idx += 1
    if min_brand is not None:
        conditions.append(f"s.brand_score >= ${idx}")
        params.append(min_brand)
        idx += 1
    if max_risk is not None:
        conditions.append(f"s.risk_score <= ${idx}")
        params.append(max_risk)
        idx += 1

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    sort_col = _VALID_SORTS.get(sort_by, "s.gravity_score")
    sort_direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
    nulls = "NULLS LAST"
    if sort_col == "a.name":
        nulls = "NULLS LAST"

    query = f"""
        SELECT
            a.*,
            s.gravity_score, s.brand_score, s.proof_score,
            s.proximity_score, s.velocity_score, s.risk_score,
            s.confidence, s.top_factors_up, s.top_factors_down,
            s.calculated_at as score_date
        FROM athletes a
        LEFT JOIN LATERAL (
            SELECT * FROM athlete_gravity_scores
            WHERE athlete_id = a.id
            ORDER BY calculated_at DESC
            LIMIT 1
        ) s ON true
        {where}
        ORDER BY {sort_col} {sort_direction} {nulls}
        LIMIT ${idx} OFFSET ${idx + 1}
    """
    params.extend([limit, offset])

    rows = await db.fetch(query, *params)
    count_sql = f"""
        SELECT COUNT(*) FROM (
            SELECT a.id
            FROM athletes a
            LEFT JOIN LATERAL (
                SELECT * FROM athlete_gravity_scores
                WHERE athlete_id = a.id
                ORDER BY calculated_at DESC
                LIMIT 1
            ) s ON true
            {where}
        ) c
    """
    total = await db.fetchval(count_sql, *params[:-2])
    return {"athletes": [dict(r) for r in rows], "total": total, "returned": len(rows)}


@router.get("/{athlete_id}/score-history")
async def get_score_history(
    athlete_id: str,
    weeks: int = Query(default=12, le=52),
    db: asyncpg.Connection = Depends(get_db),
):
    rows = await db.fetch(
        """SELECT gravity_score, brand_score, proof_score,
                  proximity_score, velocity_score, risk_score,
                  confidence, calculated_at
           FROM athlete_gravity_scores
           WHERE athlete_id = $1
           ORDER BY calculated_at DESC
           LIMIT $2""",
        athlete_id,
        weeks,
    )
    return {"history": [dict(r) for r in rows]}


@router.get("/{athlete_id}")
async def get_athlete(athlete_id: str, db: asyncpg.Connection = Depends(get_db)):
    """Full athlete profile with score history, NIL deals, comparables."""
    athlete = await db.fetchrow("SELECT * FROM athletes WHERE id = $1", athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    scores = await db.fetch(
        """SELECT * FROM athlete_gravity_scores
           WHERE athlete_id = $1
           ORDER BY calculated_at DESC
           LIMIT 52""",
        athlete_id,
    )
    deals = await db.fetch(
        """SELECT * FROM athlete_nil_deals
           WHERE athlete_id = $1
           ORDER BY deal_date DESC NULLS LAST""",
        athlete_id,
    )
    comparables = await db.fetch(
        """SELECT a.*, s.gravity_score, s.brand_score, s.proof_score,
                  s.proximity_score, s.velocity_score, s.risk_score,
                  cs.similarity_score
           FROM comparable_sets cs
           JOIN athletes a ON a.id = cs.comparable_athlete_id
           LEFT JOIN LATERAL (
               SELECT * FROM athlete_gravity_scores
               WHERE athlete_id = a.id
               ORDER BY calculated_at DESC LIMIT 1
           ) s ON true
           WHERE cs.subject_athlete_id = $1
           ORDER BY cs.similarity_score DESC
           LIMIT 15""",
        athlete_id,
    )

    return {
        "athlete": dict(athlete),
        "score_history": [dict(s) for s in scores],
        "nil_deals": [dict(d) for d in deals],
        "comparables": [dict(c) for c in comparables],
    }
