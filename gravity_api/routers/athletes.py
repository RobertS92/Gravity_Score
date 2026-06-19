from typing import List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from gravity_api.database import get_db
from gravity_api.services.athlete_feed import build_athlete_feed_events
from gravity_api.services.athlete_search import search_athletes as run_athlete_search
from gravity_api.services.nil_valuation import nil_from_row, sanitize_nil_valuation_usd
from gravity_api.services.sport_query import cap_prefs_to_db_slugs

router = APIRouter()
ROSTER_FRESHNESS_DAYS = 14


def _score_delta_30d(scores: list[asyncpg.Record]) -> float | None:
    if len(scores) < 2:
        return None
    latest = scores[0]
    latest_score = latest.get("gravity_score")
    latest_at = latest.get("calculated_at")
    if latest_score is None or latest_at is None:
        return None
    target_ts = latest_at.timestamp() - (30 * 24 * 60 * 60)
    best = None
    best_diff = None
    for row in scores[1:]:
        score = row.get("gravity_score")
        ts = row.get("calculated_at")
        if score is None or ts is None:
            continue
        diff = abs(ts.timestamp() - target_ts)
        if best is None or best_diff is None or diff < best_diff:
            best = score
            best_diff = diff
    if best is None:
        return None
    return round(float(latest_score) - float(best), 1)


def _invert_risk(v: object) -> float | None:
    if v is None:
        return None
    try:
        return max(0.0, min(100.0, 100.0 - float(v)))
    except (TypeError, ValueError):
        return None


@router.get("")
@router.get("/", include_in_schema=False)
async def search_athletes(
    q: Optional[str] = None,
    sport: Optional[str] = None,
    sports: Optional[str] = Query(
        None,
        description="Comma-separated cap codes: CFB,NCAAB,NCAAW (used when sport is not set)",
    ),
    conference: Optional[str] = None,
    position_group: Optional[str] = None,
    school: Optional[str] = None,
    min_gravity: Optional[float] = None,
    max_gravity: Optional[float] = None,
    min_brand: Optional[float] = None,
    max_risk: Optional[float] = None,
    sort_by: str = "gravity_score",
    sort_dir: str = "desc",
    include_stale_roster: bool = Query(
        False,
        description="Include active athletes whose roster verification is older than the leaderboard window",
    ),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: asyncpg.Connection = Depends(get_db),
):
    """Search athletes with filters — terminal search and leaderboards."""
    sports_db: Optional[List[str]] = None
    if not sport and sports and sports.strip():
        sports_db = cap_prefs_to_db_slugs([s.strip() for s in sports.split(",") if s.strip()])
    return await run_athlete_search(
        db,
        q=q,
        sport=sport,
        sports_db=sports_db,
        conference=conference,
        position_group=position_group,
        school=school,
        min_gravity=min_gravity,
        max_gravity=max_gravity,
        min_brand=min_brand,
        max_risk=max_risk,
        exclude_inactive=True,
        # Direct name lookup is a discovery action, not a current-roster
        # leaderboard. Keep active athletes searchable even when roster
        # verification is older than the leaderboard freshness window.
        roster_verified_within_days=(
            None if (q and q.strip()) or include_stale_roster else ROSTER_FRESHNESS_DAYS
        ),
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
                  proximity_score, velocity_score, (100.0 - risk_score) AS risk_score,
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
                  s.proximity_score, s.velocity_score, (100.0 - s.risk_score) AS risk_score,
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


@router.get("/{athlete_id}/deal-action")
async def get_deal_action(athlete_id: str, db: asyncpg.Connection = Depends(get_db)):
    athlete = await db.fetchrow("SELECT id, name FROM athletes WHERE id = $1", athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    latest = await db.fetchrow(
        """SELECT gravity_score, dollar_p50_usd, confidence
           FROM athlete_gravity_scores
           WHERE athlete_id = $1
           ORDER BY calculated_at DESC
           LIMIT 1""",
        athlete_id,
    )
    nil_p50 = float(latest["dollar_p50_usd"]) if latest and latest["dollar_p50_usd"] is not None else 150000.0
    gs = float(latest["gravity_score"]) if latest and latest["gravity_score"] is not None else 60.0
    recommendation = "HOLD"
    urgency = "MEDIUM"
    if gs >= 80:
        recommendation = "RAISE"
        urgency = "HIGH"
    elif gs < 55:
        recommendation = "WALK"
        urgency = "LOW"
    return {
        "recommendation": recommendation,
        "urgency": urgency,
        "current_range_low": round(nil_p50 * 0.85, 2),
        "current_range_high": round(nil_p50 * 1.15, 2),
        "walk_away_price": round(nil_p50 * 1.25, 2),
        "structure": {
            "type": "HYBRID" if gs >= 70 else "FIXED",
            "guaranteed_amount": round(nil_p50 * 0.65, 2),
            "performance_bonus": round(nil_p50 * 0.35, 2),
            "term_months": 12,
        },
        "rationale": f"{athlete['name']} projects as a {gs:.1f} GS athlete with current model range centered at ${nil_p50:,.0f}.",
    }


@router.get("/{athlete_id}/confidence")
async def get_confidence(athlete_id: str, db: asyncpg.Connection = Depends(get_db)):
    athlete = await db.fetchrow("SELECT id FROM athletes WHERE id = $1", athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    latest = await db.fetchrow(
        """SELECT confidence, dollar_confidence
           FROM athlete_gravity_scores
           WHERE athlete_id = $1
           ORDER BY calculated_at DESC
           LIMIT 1""",
        athlete_id,
    )
    conf = float(latest["confidence"]) if latest and latest["confidence"] is not None else 0.55
    label = "LOW"
    if conf >= 0.75:
        label = "HIGH"
    elif conf >= 0.6:
        label = "MEDIUM"
    return {
        "score": round(conf, 3),
        "level": label,
        "factors": [
            {"name": "Data recency", "impact": "positive" if conf >= 0.6 else "neutral"},
            {"name": "Comparable depth", "impact": "positive" if conf >= 0.7 else "neutral"},
            {"name": "Verified deals", "impact": "positive" if conf >= 0.75 else "mixed"},
        ],
        "caveats": [] if conf >= 0.6 else ["Low-confidence projection: limited recent verified deal evidence."],
    }


@router.get("/{athlete_id}/alternatives")
async def get_alternatives(athlete_id: str, db: asyncpg.Connection = Depends(get_db)):
    subject = await db.fetchrow("SELECT id, sport, position FROM athletes WHERE id = $1", athlete_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Athlete not found")
    rows = await db.fetch(
        """SELECT a.id, a.name, a.school, s.gravity_score, s.dollar_p50_usd
           FROM athletes a
           LEFT JOIN LATERAL (
              SELECT gravity_score, dollar_p50_usd
              FROM athlete_gravity_scores
              WHERE athlete_id = a.id
              ORDER BY calculated_at DESC
              LIMIT 1
           ) s ON true
           WHERE a.id != $1 AND a.sport = $2 AND (a.position = $3 OR $3 IS NULL)
           ORDER BY s.gravity_score DESC NULLS LAST
           LIMIT 5""",
        athlete_id,
        subject["sport"],
        subject["position"],
    )
    candidates = []
    for r in rows:
        gs = float(r["gravity_score"]) if r["gravity_score"] is not None else 55.0
        p50 = float(r["dollar_p50_usd"]) if r["dollar_p50_usd"] is not None else 120000.0
        candidates.append(
            {
                "athlete_id": str(r["id"]),
                "name": r["name"],
                "school": r["school"],
                "fit_score": round(min(99.0, max(50.0, gs)), 1),
                "nil_estimate": round(p50, 2),
                "why_better": "Higher projected gravity profile with similar positional fit.",
            }
        )
    return {"candidates": candidates}


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

    # Resolve the team_id for the athlete's school+sport so the FE can
    # offer a "favorite this program" toggle on the profile.
    school_name = athlete_dict.get("school")
    sport_slug = athlete_dict.get("sport")
    if school_name and sport_slug:
        team_row = await db.fetchrow(
            "SELECT id FROM teams WHERE school_name = $1 AND sport = $2 LIMIT 1",
            school_name,
            sport_slug,
        )
        athlete_dict["team_id"] = str(team_row["id"]) if team_row else None
    else:
        athlete_dict["team_id"] = None

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
    if athlete_dict.get("risk_score") is not None:
        athlete_dict["risk_score"] = _invert_risk(athlete_dict.get("risk_score"))

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

    # Unified NIL valuation: merge raw_data + athlete row signals so the
    # sanitizer can rescale Arch-Manning-style compact integers using the
    # most complete context available. nil_valuation_display_usd is the
    # value the terminal must show; nil_valuation_source explains where it
    # came from.
    merged_for_nil = {
        **(raw_signals or {}),
        "recruiting_stars": athlete_dict.get("recruiting_stars") or raw_signals.get("recruiting_stars"),
        "recruiting_rank_national": (
            athlete_dict.get("recruiting_rank_national")
            or raw_signals.get("recruiting_rank_national")
        ),
        "instagram_followers": ig_followers,
        "twitter_followers": tw_followers,
        "tiktok_followers": tt_followers,
        "google_trends_score": raw_signals.get("google_trends_score"),
        "verified_nil_amount_usd": athlete_dict.get("verified_nil_amount_usd"),
    }
    nil_display = nil_from_row(merged_for_nil)
    nil_raw_val = raw_signals.get("nil_valuation")
    athlete_dict["nil_valuation_display_usd"] = nil_display
    athlete_dict["nil_valuation_source"] = (
        raw_signals.get("nil_valuation_source")
        or ("rescaled" if nil_display and nil_raw_val and nil_display != nil_raw_val else "raw")
    )
    athlete_dict["nil_valuation_sanitized"] = bool(
        nil_display and nil_raw_val and nil_display != nil_raw_val
    )

    # Roster lifecycle banner — surface inactive state so the FE can dim
    # the profile and gate CSC generation.
    is_active = athlete_dict.get("is_active")
    athlete_dict["roster_inactive"] = bool(is_active is False)
    athlete_dict["roster_status"] = athlete_dict.get("roster_status")

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
    athlete_dict["gravity_delta_30d"] = _score_delta_30d(scores)

    score_history = [dict(s) for s in scores]
    for row in score_history:
        if row.get("risk_score") is not None:
            row["risk_score"] = _invert_risk(row.get("risk_score"))

    return {
        "athlete": athlete_dict,
        "score_history": score_history,
        "nil_deals": [dict(d) for d in deals],
        "comparables": [dict(c) for c in comparables],
    }
