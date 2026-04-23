"""Shared athlete search query for `/athletes` and `/market/scan`."""

from typing import Any, List, Optional

import asyncpg

from gravity_api.services.position_group_match import position_group_sql_predicate

_VALID_SORTS = {
    "gravity_score": "s.gravity_score",
    "brand_score": "s.brand_score",
    "proof_score": "s.proof_score",
    "proximity_score": "s.proximity_score",
    "velocity_score": "s.velocity_score",
    "risk_score": "s.risk_score",
    "name": "a.name",
}


async def search_athletes(
    db: asyncpg.Connection,
    *,
    q: Optional[str] = None,
    sport: Optional[str] = None,
    sports_db: Optional[List[str]] = None,
    conference: Optional[str] = None,
    position_group: Optional[str] = None,
    school: Optional[str] = None,
    min_gravity: Optional[float] = None,
    max_gravity: Optional[float] = None,
    min_brand: Optional[float] = None,
    max_risk: Optional[float] = None,
    exclude_inactive: bool = False,
    roster_verified_within_days: Optional[int] = None,
    sort_by: str = "gravity_score",
    sort_dir: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    conditions: List[str] = []
    params: List[Any] = []
    idx = 1

    if q:
        conditions.append(f"a.name ILIKE ${idx}")
        params.append(f"%{q}%")
        idx += 1
    if sports_db:
        conditions.append(f"a.sport = ANY(${idx}::text[])")
        params.append(sports_db)
        idx += 1
    elif sport:
        conditions.append(f"a.sport = ${idx}")
        params.append(sport)
        idx += 1
    if conference:
        # Substring match so UI labels like "SEC" match stored names (e.g. "Southeastern Conference")
        conditions.append(f"a.conference ILIKE ${idx}")
        params.append(f"%{conference}%")
        idx += 1
    if position_group:
        frag, extra, idx = position_group_sql_predicate(position_group, idx)
        conditions.append(frag)
        params.extend(extra)
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
    if exclude_inactive:
        # NULL or TRUE = include; explicit FALSE = departed / hidden
        conditions.append("(a.is_active IS DISTINCT FROM FALSE)")
    if roster_verified_within_days is not None:
        # NULL = not yet verified by roster job — still show until scraper sets timestamps
        conditions.append(
            f"(a.roster_verified_at IS NULL OR a.roster_verified_at >= "
            f"NOW() - (${idx}::int * INTERVAL '1 day'))"
        )
        params.append(roster_verified_within_days)
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
            s.company_gravity_score, s.brand_gravity_score,
            s.dollar_p10_usd, s.dollar_p50_usd, s.dollar_p90_usd,
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
