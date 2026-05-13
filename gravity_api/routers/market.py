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


def _canonical_team_sport(sport: object) -> str:
    s = str(sport or "").strip().lower()
    if s in {"mcbb", "ncaab", "ncaab_mens", "mens"}:
        return "ncaab_mens"
    if s in {"wcbb", "ncaaw", "ncaab_womens", "womens"}:
        return "ncaab_womens"
    return s


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
            p.school,
            p.conference,
            p.sport,
            p.nil_environment_score,
            p.collective_budget_usd,
            sub.avg_gravity_score,
            sub.top_athlete_name,
            sub.athlete_count,
        FROM programs p
        LEFT JOIN (
            SELECT
                a.school AS sch,
                a.sport  AS sprt,
                AVG(s.gravity_score)                                                      AS avg_gravity_score,
                COUNT(*)                                                                   AS athlete_count,
                (array_agg(a.name ORDER BY s.gravity_score DESC NULLS LAST))[1]           AS top_athlete_name
            FROM athletes a
            LEFT JOIN LATERAL (
                SELECT gravity_score
                FROM athlete_gravity_scores
                WHERE athlete_id = a.id
                ORDER BY calculated_at DESC
                LIMIT 1
            ) s ON true
            GROUP BY a.school, a.sport
        ) sub ON sub.sch = p.school AND sub.sprt = p.sport
        ORDER BY sub.avg_gravity_score DESC NULLS LAST
        LIMIT $1
        """,
        limit,
    )

    team_score_rows = await db.fetch(
        """
        SELECT DISTINCT ON (tgs.team_id)
            t.id AS team_id,
            t.school_name,
            t.sport,
            tgs.gravity_score,
            tgs.brand_score,
            tgs.proof_score,
            tgs.velocity_score,
            tgs.risk_score,
            tgs.scored_at
        FROM team_gravity_scores tgs
        JOIN teams t ON t.id = tgs.team_id
        ORDER BY tgs.team_id, tgs.scored_at DESC
        """
    )

    latest_team_by_program_key: dict[tuple[str, str], dict[str, Any]] = {}
    for tr in team_score_rows:
        key = (_school_key(tr["school_name"]), _canonical_team_sport(tr["sport"]))
        prev = latest_team_by_program_key.get(key)
        if prev is None or (tr["scored_at"] is not None and (prev["scored_at"] is None or tr["scored_at"] > prev["scored_at"])):
            latest_team_by_program_key[key] = dict(tr)

    schools = []
    for r in program_rows:
        avg_g = r["avg_gravity_score"]
        nil_env = r["nil_environment_score"]
        budget = r["collective_budget_usd"]
        team_score = latest_team_by_program_key.get((_school_key(r["school"]), _canonical_team_sport(r["sport"])))
        schools.append(
            {
                "team_id": str(team_score["team_id"]) if team_score and team_score.get("team_id") is not None else None,
                "school": r["school"],
                "conference": r["conference"],
                "sport": r["sport"],
                "avg_gravity_score": float(avg_g) if avg_g is not None else None,
                "program_gravity_score": _to_float(team_score.get("gravity_score")) if team_score else None,
                "program_brand_score": _to_float(team_score.get("brand_score")) if team_score else None,
                "program_proof_score": _to_float(team_score.get("proof_score")) if team_score else None,
                "program_velocity_score": _to_float(team_score.get("velocity_score")) if team_score else None,
                "program_risk_score": (100.0 - float(team_score["risk_score"])) if team_score and team_score.get("risk_score") is not None else None,
                "athlete_count": int(r["athlete_count"]) if r["athlete_count"] is not None else 0,
                "watchlisted_count": None,
                "top_athlete_name": r["top_athlete_name"],
                "nil_market_size_estimate": float(budget) if budget is not None else (float(nil_env) if nil_env is not None else None),
            }
        )
    schools.sort(
        key=lambda s: (
            s["program_gravity_score"] is None,
            -(s["program_gravity_score"] if s["program_gravity_score"] is not None else (s["avg_gravity_score"] or -1.0)),
        )
    )
    return {"schools": schools[:limit]}
