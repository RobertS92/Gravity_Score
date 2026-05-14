"""Market scan + school index for the terminal."""

import re
from typing import Any, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, Query

from gravity_api.database import get_db
from gravity_api.services.athlete_search import search_athletes as run_athlete_search
from gravity_api.services.sport_query import cap_prefs_to_db_slugs

router = APIRouter()
ROSTER_FRESHNESS_DAYS = 14

_TEAM_SPORT_ALIASES = {
    "cfb": "cfb",
    "football": "cfb",
    "fbs": "cfb",
    "mcbb": "ncaab_mens",
    "ncaab": "ncaab_mens",
    "ncaab_mens": "ncaab_mens",
    "mens": "ncaab_mens",
    "mens_basketball": "ncaab_mens",
    "mbb": "ncaab_mens",
    "wcbb": "ncaab_womens",
    "ncaaw": "ncaab_womens",
    "ncaab_womens": "ncaab_womens",
    "womens": "ncaab_womens",
    "womens_basketball": "ncaab_womens",
    "wbb": "ncaab_womens",
}


def _canonical_team_sport(sport: object) -> str:
    s = str(sport or "").strip().lower()
    return _TEAM_SPORT_ALIASES.get(s, s)


def _school_key(name: object) -> str:
    # Normalize punctuation/spacing drift between programs.school and teams.school_name.
    return re.sub(r"[^a-z0-9]", "", str(name or "").strip().lower())


def _to_float(v: Any) -> float | None:
    return float(v) if v is not None else None


@router.get("/scan")
async def market_scan(
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
    limit: int = Query(default=500, le=1000),
    offset: int = Query(default=0, ge=0, le=500000),
    db: asyncpg.Connection = Depends(get_db),
):
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
        roster_verified_within_days=ROSTER_FRESHNESS_DAYS,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )


@router.get("/schools")
async def market_schools(
    limit: int = Query(default=400, le=500),
    db: asyncpg.Connection = Depends(get_db),
):
    program_rows = await db.fetch(
        """
        SELECT
            p.id AS program_id,
            p.school,
            p.conference,
            p.sport,
            p.nil_environment_score,
            p.collective_budget_usd
        FROM programs p
        """,
    )

    athlete_agg_rows = await db.fetch(
        """
        SELECT
            a.school AS school,
            a.sport AS sport,
            AVG(s.gravity_score) AS avg_gravity_score,
            AVG(a.program_gravity_score) AS avg_program_gravity_score,
            COUNT(*) AS athlete_count,
            (
                array_agg(
                    a.name
                    ORDER BY COALESCE(s.gravity_score, a.program_gravity_score) DESC NULLS LAST
                )
            )[1] AS top_athlete_name,
            SUM(
                COALESCE(
                    s.dollar_p50_usd,
                    CASE
                        WHEN s.dollar_p10_usd IS NOT NULL AND s.dollar_p90_usd IS NOT NULL
                        THEN (s.dollar_p10_usd + s.dollar_p90_usd) / 2.0
                        ELSE NULL
                    END,
                    a.nil_valuation_raw
                )
            ) AS athlete_nil_market_estimate
        FROM athletes a
        LEFT JOIN LATERAL (
            SELECT gravity_score, dollar_p10_usd, dollar_p50_usd, dollar_p90_usd
            FROM athlete_gravity_scores
            WHERE athlete_id = a.id
            ORDER BY calculated_at DESC
            LIMIT 1
        ) s ON true
        GROUP BY a.school, a.sport
        """
    )

    athlete_agg_by_program_key: dict[tuple[str, str], dict[str, Any]] = {}
    for ar in athlete_agg_rows:
        athlete_agg_by_program_key[(_school_key(ar["school"]), _canonical_team_sport(ar["sport"]))] = dict(ar)

    team_score_rows = await db.fetch(
        """
        SELECT DISTINCT ON (tgs.team_id)
            tgs.team_id,
            t.id AS matched_team_id,
            t.school_name,
            t.sport,
            tgs.gravity_score,
            tgs.brand_score,
            tgs.proof_score,
            tgs.velocity_score,
            tgs.risk_score,
            tgs.scored_at
        FROM team_gravity_scores tgs
        LEFT JOIN teams t ON t.id = tgs.team_id
        ORDER BY tgs.team_id, tgs.scored_at DESC
        """
    )

    latest_team_by_program_key: dict[tuple[str, str], dict[str, Any]] = {}
    latest_team_by_id: dict[str, dict[str, Any]] = {}
    for tr in team_score_rows:
        row = dict(tr)
        team_id = row.get("team_id")
        if team_id is not None:
            latest_team_by_id[str(team_id)] = row
        school_name = row.get("school_name")
        sport = row.get("sport")
        if not school_name or not sport:
            continue
        key = (_school_key(school_name), _canonical_team_sport(sport))
        prev = latest_team_by_program_key.get(key)
        if prev is None or (row["scored_at"] is not None and (prev["scored_at"] is None or row["scored_at"] > prev["scored_at"])):
            latest_team_by_program_key[key] = row

    schools = []
    for r in program_rows:
        program = dict(r)
        athlete_agg = athlete_agg_by_program_key.get(
            (_school_key(program["school"]), _canonical_team_sport(program["sport"]))
        )
        avg_g = athlete_agg.get("avg_gravity_score") if athlete_agg else None
        avg_program_g = athlete_agg.get("avg_program_gravity_score") if athlete_agg else None
        nil_env = program["nil_environment_score"]
        budget = program["collective_budget_usd"]
        athlete_nil_market_estimate = athlete_agg.get("athlete_nil_market_estimate") if athlete_agg else None
        program_id = program.get("program_id")
        team_score = (
            latest_team_by_id.get(str(program_id))
            if program_id is not None
            else None
        )
        if team_score is None:
            team_score = latest_team_by_program_key.get(
                (_school_key(program["school"]), _canonical_team_sport(program["sport"]))
            )
        team_gravity = _to_float(team_score.get("gravity_score")) if team_score else None
        resolved_avg_g = _to_float(avg_g) if avg_g is not None else _to_float(avg_program_g)
        schools.append(
            {
                "team_id": (
                    str(team_score["matched_team_id"])
                    if team_score and team_score.get("matched_team_id") is not None
                    else None
                ),
                "school": program["school"],
                "conference": program["conference"],
                "sport": program["sport"],
                "avg_gravity_score": resolved_avg_g,
                "program_gravity_score": team_gravity if team_gravity is not None else resolved_avg_g,
                "program_brand_score": _to_float(team_score.get("brand_score")) if team_score else None,
                "program_proof_score": _to_float(team_score.get("proof_score")) if team_score else None,
                "program_velocity_score": _to_float(team_score.get("velocity_score")) if team_score else None,
                "program_risk_score": (100.0 - float(team_score["risk_score"])) if team_score and team_score.get("risk_score") is not None else None,
                "athlete_count": int(athlete_agg["athlete_count"]) if athlete_agg and athlete_agg.get("athlete_count") is not None else 0,
                "watchlisted_count": None,
                "top_athlete_name": athlete_agg.get("top_athlete_name") if athlete_agg else None,
                "nil_market_size_estimate": (
                    float(budget)
                    if budget is not None
                    else (
                        float(athlete_nil_market_estimate)
                        if athlete_nil_market_estimate is not None
                        else (
                            float(nil_env)
                            if nil_env is not None and float(nil_env) >= 1000
                            else None
                        )
                    )
                ),
            }
        )
    schools.sort(
        key=lambda s: (
            s["program_gravity_score"] is None,
            -(s["program_gravity_score"] if s["program_gravity_score"] is not None else (s["avg_gravity_score"] or -1.0)),
        )
    )
    return {"schools": schools[:limit]}
