from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from gravity_api.database import get_db
from gravity_api.services.athlete_feed import build_athlete_feed_events
from gravity_api.services.athlete_search import search_athletes as run_athlete_search

router = APIRouter()


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
    return await run_athlete_search(
        db,
        q=q,
        sport=sport,
        conference=conference,
        position_group=position_group,
        school=school,
        min_gravity=min_gravity,
        max_gravity=max_gravity,
        min_brand=min_brand,
        max_risk=max_risk,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )


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


async def _fetch_comparables(db: asyncpg.Connection, athlete_id: str):
    return await db.fetch(
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


@router.get("/{athlete_id}/comparables")
async def get_comparables(athlete_id: str, db: asyncpg.Connection = Depends(get_db)):
    exists = await db.fetchval("SELECT 1 FROM athletes WHERE id = $1", athlete_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Athlete not found")
    comparables = await _fetch_comparables(db, athlete_id)
    return {"comparables": [dict(c) for c in comparables]}


@router.get("/{athlete_id}/feed")
async def get_athlete_feed(athlete_id: str, db: asyncpg.Connection = Depends(get_db)):
    athlete = await db.fetchrow("SELECT id, name FROM athletes WHERE id = $1", athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    events = await build_athlete_feed_events(
        db,
        str(athlete["id"]),
        str(athlete["name"]),
    )
    return {"events": events}


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
    comparables = await _fetch_comparables(db, athlete_id)

    athlete_dict = dict(athlete)

    # Resolve latest component scores for display (first history row has the freshest values)
    latest_score = dict(scores[0]) if scores else {}

    # Merge the latest gravity_scores row fields into the athlete dict for easy frontend access
    for score_field in (
        "gravity_score", "brand_score", "proof_score", "proximity_score",
        "velocity_score", "risk_score", "confidence", "model_version",
        "dollar_p10_usd", "dollar_p50_usd", "dollar_p90_usd",
        "dollar_confidence", "shap_values", "top_factors_up", "top_factors_down",
    ):
        if latest_score.get(score_field) is not None:
            athlete_dict[score_field] = latest_score[score_field]

    athlete_dict["score_date"] = latest_score.get("calculated_at")

    # Map program_gravity_score / active_deal_brand_gravity through to the
    # frontend's company_gravity_score / brand_gravity_score field names.
    athlete_dict["company_gravity_score"] = (
        athlete_dict.get("program_gravity_score")
        or latest_score.get("company_gravity_score")
    )
    athlete_dict["brand_gravity_score"] = (
        athlete_dict.get("active_deal_brand_gravity")
        or latest_score.get("brand_gravity_score")
    )

    return {
        "athlete": athlete_dict,
        "score_history": [dict(s) for s in scores],
        "nil_deals": [dict(d) for d in deals],
        "comparables": [dict(c) for c in comparables],
    }
