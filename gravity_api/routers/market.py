"""Market scan + school index for the terminal."""

from typing import List, Optional

import asyncpg
from fastapi import APIRouter, Depends, Query

from gravity_api.database import get_db
from gravity_api.services.athlete_search import search_athletes as run_athlete_search
from gravity_api.services.sport_query import cap_prefs_to_db_slugs

router = APIRouter()


@router.get("/scan")
async def market_scan(
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
    sort_by: str = "gravity_score",
    sort_dir: str = "desc",
    limit: int = Query(default=500, le=1000),
    offset: int = Query(default=0, ge=0, le=500000),
    exclude_inactive: bool = Query(
        default=True,
        description="Hide athletes with is_active=false (departed). Requires migration 005.",
    ),
    roster_verified_within_days: Optional[int] = Query(
        default=180,
        ge=1,
        le=3650,
        description="Hide rows with roster_verified_at older than N days (NULL still shown).",
    ),
    include_stale_roster: bool = Query(
        default=False,
        description="If true, ignore roster age filter (still respects exclude_inactive).",
    ),
    db: asyncpg.Connection = Depends(get_db),
):
    roster_days = None if include_stale_roster else roster_verified_within_days
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
        roster_verified_within_days=roster_days,
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
    rows = await db.fetch(
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
            tg.gravity_score        AS program_gravity_score,
            tg.brand_score          AS program_brand_score,
            tg.proof_score          AS program_proof_score,
            tg.velocity_score       AS program_velocity_score,
            tg.risk_score           AS program_risk_score,
            tg.scored_at            AS program_scored_at,
            tm.id                   AS team_id
        FROM programs p
        LEFT JOIN teams tm ON tm.school_name = p.school AND tm.sport = p.sport
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
        LEFT JOIN LATERAL (
            SELECT tgs.gravity_score, tgs.brand_score, tgs.proof_score,
                   tgs.velocity_score, tgs.risk_score, tgs.scored_at
            FROM team_gravity_scores tgs
            JOIN teams t ON t.id = tgs.team_id
            WHERE t.school_name = p.school AND t.sport = p.sport
            ORDER BY tgs.scored_at DESC
            LIMIT 1
        ) tg ON true
        ORDER BY COALESCE(tg.gravity_score, sub.avg_gravity_score) DESC NULLS LAST
        LIMIT $1
        """,
        limit,
    )
    schools = []
    for r in rows:
        avg_g = r["avg_gravity_score"]
        nil_env = r["nil_environment_score"]
        budget = r["collective_budget_usd"]
        prog_g = r["program_gravity_score"]
        schools.append(
            {
                "team_id": str(r["team_id"]) if r["team_id"] is not None else None,
                "school": r["school"],
                "conference": r["conference"],
                "sport": r["sport"],
                "avg_gravity_score": float(avg_g) if avg_g is not None else None,
                "program_gravity_score": float(prog_g) if prog_g is not None else None,
                "program_brand_score": float(r["program_brand_score"]) if r["program_brand_score"] is not None else None,
                "program_proof_score": float(r["program_proof_score"]) if r["program_proof_score"] is not None else None,
                "program_velocity_score": float(r["program_velocity_score"]) if r["program_velocity_score"] is not None else None,
                "program_risk_score": float(r["program_risk_score"]) if r["program_risk_score"] is not None else None,
                "athlete_count": int(r["athlete_count"]) if r["athlete_count"] is not None else 0,
                "watchlisted_count": None,
                "top_athlete_name": r["top_athlete_name"],
                "nil_market_size_estimate": float(budget) if budget is not None else (float(nil_env) if nil_env is not None else None),
            }
        )
    return {"schools": schools}
