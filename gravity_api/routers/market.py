"""Market scan + school index for the terminal."""

from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, Query

from gravity_api.database import get_db
from gravity_api.services.athlete_search import search_athletes as run_athlete_search

router = APIRouter()


@router.get("/scan")
async def market_scan(
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
    limit: int = Query(default=100, le=200),
    db: asyncpg.Connection = Depends(get_db),
):
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
        offset=0,
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
            tg.scored_at            AS program_scored_at
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
        LEFT JOIN LATERAL (
            SELECT tgs.gravity_score, tgs.brand_score, tgs.proof_score,
                   tgs.velocity_score, tgs.risk_score, tgs.scored_at
            FROM team_gravity_scores tgs
            JOIN teams t ON t.id = tgs.team_id
            WHERE t.school = p.school AND t.sport = p.sport
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
