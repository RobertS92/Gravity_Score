"""Aggregates for CapIQ compare / outlook."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import asyncpg


async def latest_scores_for_athletes(
    conn: asyncpg.Connection, athlete_ids: List[str]
) -> Dict[str, asyncpg.Record]:
    if not athlete_ids:
        return {}
    rows = await conn.fetch(
        """SELECT DISTINCT ON (athlete_id)
               athlete_id, gravity_score, brand_score, proof_score, proximity_score,
               velocity_score, risk_score, calculated_at
           FROM athlete_gravity_scores
           WHERE athlete_id = ANY($1::uuid[])
           ORDER BY athlete_id, calculated_at DESC NULLS LAST""",
        athlete_ids,
    )
    return {str(r["athlete_id"]): r for r in rows}


def weighted_aggregate_gravity(
    rows: List[Tuple[asyncpg.Record | None, int]],
) -> Tuple[float, float]:
    """(aggregate_gravity, avg_risk) weighted by base_comp cents."""
    num_g = 0.0
    num_r = 0.0
    den = 0
    for rec, cents in rows:
        w = max(int(cents), 1)
        den += w
        if rec:
            num_g += float(rec["gravity_score"] or 0) * w
            num_r += float(rec["risk_score"] or 0) * w
        else:
            num_g += 50.0 * w
            num_r += 30.0 * w
    if den == 0:
        return 0.0, 0.0
    return round(num_g / den, 4), round(num_r / den, 4)


def gravity_per_dollar_line(agg: float, total_cents: int) -> str:
    if agg <= 0 or total_cents <= 0:
        return "n/a"
    dollars = total_cents / 100.0
    per_pt = dollars / agg
    return f"${per_pt / 1000.0:.1f}K per gravity point"


def incentive_exposure_cents(incentives: Any) -> int:
    """Sum incentive amounts at 100% likelihood (JSON array)."""
    if not isinstance(incentives, list):
        return 0
    total = 0
    for item in incentives:
        if not isinstance(item, dict):
            continue
        try:
            amt = int(item.get("amount") or 0)
        except (TypeError, ValueError):
            amt = 0
        total += max(amt, 0)
    return total
