from typing import List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from gravity_api.database import get_db
from gravity_api.services.athlete_feed import build_athlete_feed_events
from gravity_api.services.athlete_search import search_athletes as run_athlete_search
from gravity_api.services.sport_query import cap_prefs_to_db_slugs

router = APIRouter()


@router.get("/")
async def search_athletes(
    q: Optional[str] = None,
    sport: Optional[str] = None,
    sports: Optional[str] = Query(
        None,
        description="Comma-separated cap codes: CFB,NCAAB,NCAAW (overrides single sport when set)",
    ),
    conference: Optional[str] = None,
    position_group: Optional[str] = None,
    school: Optional[str] = None,
    min_gravity: Optional[float] = None,
    max_gravity: Optional[float] = None,
    min_brand: Optional[float] = None,
    max_risk: Optional[float] = None,
    exclude_inactive: bool = True,
    roster_verified_within_days: Optional[int] = None,
    sort_by: str = "gravity_score",
    sort_dir: str = "desc",
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: asyncpg.Connection = Depends(get_db),
):
    """Search athletes with filters — terminal search and leaderboards."""
    sports_db: Optional[List[str]] = None
    if sports and sports.strip():
        sports_db = cap_prefs_to_db_slugs([s.strip() for s in sports.split(",") if s.strip()])
    return await run_athlete_search(
        db,
        q=q,
        sport=sport if not sports_db else None,
        sports_db=sports_db,
        conference=conference,
        position_group=position_group,
        school=school,
        min_gravity=min_gravity,
        max_gravity=max_gravity,
        min_brand=min_brand,
        max_risk=max_risk,
        exclude_inactive=exclude_inactive,
        roster_verified_within_days=roster_verified_within_days,
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
    """Full athlete profile with score history, NIL deals, comparables, and social signals."""
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

    # Latest raw scraped signals — social, news, On3
    raw_row = await db.fetchrow(
        """SELECT raw_data FROM raw_athlete_data
           WHERE athlete_id = $1
           ORDER BY scraped_at DESC
           LIMIT 1""",
        athlete_id,
    )
    raw_signals: dict = {}
    if raw_row and raw_row["raw_data"]:
        rd = raw_row["raw_data"]
        if isinstance(rd, str):
            import json as _json
            try:
                raw_signals = _json.loads(rd)
            except Exception:
                raw_signals = {}
        elif isinstance(rd, dict):
            raw_signals = rd
        else:
            try:
                raw_signals = dict(rd)
            except Exception:
                raw_signals = {}

    # Compute gravity percentile vs all scored athletes
    gravity_score_val = scores[0]["gravity_score"] if scores else None
    percentile_row = None
    nil_percentile_row = None
    if gravity_score_val is not None:
        percentile_row = await db.fetchrow(
            """SELECT
                 ROUND(
                   100.0 * COUNT(*) FILTER (WHERE s.gravity_score <= $1)
                   / NULLIF(COUNT(*), 0)
                 ) AS pct
               FROM (
                 SELECT DISTINCT ON (athlete_id) gravity_score
                 FROM athlete_gravity_scores
                 ORDER BY athlete_id, calculated_at DESC
               ) s""",
            gravity_score_val,
        )

    # NIL valuation percentile — compare deal median vs all athletes with verified deals
    nil_consensus_val = raw_signals.get("nil_valuation") or raw_signals.get("verified_nil_amount_usd")
    if nil_consensus_val:
        nil_percentile_row = await db.fetchrow(
            """SELECT
                 ROUND(
                   100.0 * COUNT(*) FILTER (WHERE d.deal_value <= $1)
                   / NULLIF(COUNT(*), 0)
                 ) AS pct
               FROM (
                 SELECT athlete_id, AVG(deal_value) AS deal_value
                 FROM athlete_nil_deals
                 WHERE deal_value > 0
                 GROUP BY athlete_id
               ) d""",
            float(nil_consensus_val),
        )

    athlete_dict = dict(athlete)

    # Merge latest gravity_scores fields
    latest_score = dict(scores[0]) if scores else {}
    for score_field in (
        "gravity_score", "brand_score", "proof_score", "proximity_score",
        "velocity_score", "risk_score", "confidence", "model_version",
        "dollar_p10_usd", "dollar_p50_usd", "dollar_p90_usd",
        "dollar_confidence", "shap_values", "top_factors_up", "top_factors_down",
    ):
        if latest_score.get(score_field) is not None:
            athlete_dict[score_field] = latest_score[score_field]

    athlete_dict["score_date"] = latest_score.get("calculated_at")

    athlete_dict["company_gravity_score"] = (
        athlete_dict.get("program_gravity_score")
        or latest_score.get("company_gravity_score")
    )
    athlete_dict["brand_gravity_score"] = (
        athlete_dict.get("active_deal_brand_gravity")
        or latest_score.get("brand_gravity_score")
    )

    # Social signals from raw scrape data
    ig_followers  = raw_signals.get("instagram_followers")
    tw_followers  = raw_signals.get("twitter_followers")
    tt_followers  = raw_signals.get("tiktok_followers")
    on3_followers = raw_signals.get("on3_nil_followers")
    social_reach  = sum(
        v for v in [ig_followers, tw_followers, tt_followers] if v and isinstance(v, (int, float))
    ) or None

    athlete_dict["social_combined_reach"]      = social_reach
    athlete_dict["instagram_followers"]        = ig_followers
    athlete_dict["twitter_followers"]          = tw_followers
    athlete_dict["tiktok_followers"]           = tt_followers
    athlete_dict["news_mentions_30d"]          = raw_signals.get("news_count_30d")
    athlete_dict["on3_nil_rank"]               = raw_signals.get("nil_ranking")
    athlete_dict["google_trends_score"]        = raw_signals.get("google_trends_score")
    athlete_dict["wikipedia_page_views_30d"]   = raw_signals.get("wikipedia_page_views_30d")
    athlete_dict["nil_valuation_raw"]          = raw_signals.get("nil_valuation")
    athlete_dict["data_quality_score"]         = raw_signals.get("data_quality_score") or athlete_dict.get("data_quality_score")

    # Only surface engagement rate when it was actually scraped — never fabricate it.
    ig_eng = raw_signals.get("instagram_engagement_rate")
    athlete_dict["instagram_engagement_rate"] = ig_eng

    # Gravity percentile
    athlete_dict["gravity_percentile"] = (
        int(percentile_row["pct"]) if percentile_row and percentile_row["pct"] is not None else None
    )
    # NIL valuation percentile
    athlete_dict["nil_valuation_percentile"] = (
        int(nil_percentile_row["pct"]) if nil_percentile_row and nil_percentile_row["pct"] is not None else None
    )

    return {
        "athlete": athlete_dict,
        "score_history": [dict(s) for s in scores],
        "nil_deals": [dict(d) for d in deals],
        "comparables": [dict(c) for c in comparables],
    }
