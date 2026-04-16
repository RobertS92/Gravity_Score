"""
Roster Builder — economic value scoring.

Given a set of athletes (with proof scores and NIL costs), compute:
  - Talent Grade  (A–F) from average proof score
  - Efficiency Score (0–100) — proof per dollar
  - Per-athlete Value Label (DEAL / FAIR / PREMIUM)
"""

from __future__ import annotations

from typing import Any

import asyncpg

# Proof score tier boundaries for peer-comparison
_TIER_BOUNDS = [(85, "elite"), (70, "high"), (55, "mid"), (0, "low")]

GRADE_THRESHOLDS = [
    (85, "A+"),
    (80, "A"),
    (75, "A-"),
    (70, "B+"),
    (65, "B"),
    (60, "B-"),
    (55, "C+"),
    (50, "C"),
    (45, "C-"),
    (40, "D"),
    (0,  "F"),
]


def talent_grade(avg_proof: float) -> str:
    for threshold, grade in GRADE_THRESHOLDS:
        if avg_proof >= threshold:
            return grade
    return "F"


def _tier(proof: float) -> str:
    for bound, name in _TIER_BOUNDS:
        if proof >= bound:
            return name
    return "low"


def efficiency_score(total_proof: float, total_spend_usd: float) -> float:
    """
    Score 0–100 measuring proof-per-dollar efficiency.
    Calibrated: spending $1M for avg proof=70 → ~65 efficiency.
    """
    if total_spend_usd <= 0:
        return 0.0
    ratio = total_proof / (total_spend_usd / 100_000)
    # Clamp to 0–100 using a soft scale (ratio of ~10 = score 80)
    score = min(100.0, max(0.0, ratio * 8.0))
    return round(score, 1)


async def peer_value_ratios(db: asyncpg.Connection) -> dict[str, float]:
    """
    Fetch median proof/dollar_p50 ratio for each tier from the live DB.
    Returns {tier_name: median_ratio}.
    """
    rows = await db.fetch(
        """
        SELECT
            s.proof_score,
            s.dollar_p50_usd
        FROM athlete_gravity_scores s
        WHERE s.proof_score IS NOT NULL
          AND s.dollar_p50_usd IS NOT NULL
          AND s.dollar_p50_usd > 10000
        ORDER BY s.proof_score
        """
    )
    buckets: dict[str, list[float]] = {"elite": [], "high": [], "mid": [], "low": []}
    for r in rows:
        proof = float(r["proof_score"])
        cost = float(r["dollar_p50_usd"])
        if cost > 0:
            buckets[_tier(proof)].append(proof / cost * 100_000)

    result: dict[str, float] = {}
    for tier, vals in buckets.items():
        if vals:
            vals.sort()
            mid = len(vals) // 2
            result[tier] = vals[mid]
        else:
            result[tier] = 5.0  # fallback median
    return result


def value_label(
    proof: float,
    nil_cost: float,
    peer_medians: dict[str, float],
) -> str:
    """DEAL / FAIR / PREMIUM based on proof/cost vs peer median."""
    if nil_cost <= 0:
        return "UNPRICED"
    tier = _tier(proof)
    ratio = proof / nil_cost * 100_000
    median = peer_medians.get(tier, 5.0)
    if median <= 0:
        return "FAIR"
    rel = ratio / median
    if rel >= 1.3:
        return "DEAL"
    if rel >= 0.7:
        return "FAIR"
    return "PREMIUM"


async def score_roster(
    db: asyncpg.Connection,
    slots: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Given a list of slots [{athlete_id, nil_cost_override}],
    return full scoring: per-athlete rows + team summary.
    """
    if not slots:
        return {
            "athletes": [],
            "talent_grade": "N/A",
            "avg_proof": 0.0,
            "total_spend": 0.0,
            "efficiency_score": 0.0,
            "position_depth": {},
        }

    athlete_ids = [s["athlete_id"] for s in slots]
    overrides = {s["athlete_id"]: s.get("nil_cost_override") for s in slots}

    # Fetch athlete + latest score data
    placeholders = ", ".join(f"${i+1}" for i in range(len(athlete_ids)))
    rows = await db.fetch(
        f"""
        SELECT
            a.id::text AS athlete_id,
            a.name,
            a.school,
            a.position,
            a.conference,
            a.sport,
            s.proof_score,
            s.brand_score,
            s.gravity_score,
            s.dollar_p50_usd,
            s.dollar_p10_usd,
            s.dollar_p90_usd
        FROM athletes a
        LEFT JOIN LATERAL (
            SELECT proof_score, brand_score, gravity_score,
                   dollar_p50_usd, dollar_p10_usd, dollar_p90_usd
            FROM athlete_gravity_scores
            WHERE athlete_id = a.id
            ORDER BY calculated_at DESC LIMIT 1
        ) s ON true
        WHERE a.id = ANY(ARRAY[{placeholders}]::uuid[])
        """,
        *athlete_ids,
    )

    peer_medians = await peer_value_ratios(db)

    athlete_rows = []
    total_proof = 0.0
    total_spend = 0.0
    position_depth: dict[str, int] = {}

    for r in rows:
        aid = r["athlete_id"]
        proof = float(r["proof_score"] or 0)
        base_cost = float(r["dollar_p50_usd"] or 0)
        cost = float(overrides.get(aid) or base_cost or 0)
        label = value_label(proof, cost, peer_medians)

        pos = (r["position"] or "OTHER").upper()
        position_depth[pos] = position_depth.get(pos, 0) + 1

        total_proof += proof
        total_spend += cost

        athlete_rows.append({
            "athlete_id": aid,
            "name": r["name"],
            "school": r["school"],
            "position": r["position"],
            "conference": r["conference"],
            "sport": r["sport"],
            "proof_score": round(proof, 1),
            "brand_score": round(float(r["brand_score"] or 0), 1),
            "gravity_score": round(float(r["gravity_score"] or 0), 1),
            "nil_cost": round(cost, 0),
            "nil_cost_p10": round(float(r["dollar_p10_usd"] or 0), 0),
            "nil_cost_p90": round(float(r["dollar_p90_usd"] or 0), 0),
            "value_label": label,
            "nil_cost_override": overrides.get(aid),
        })

    n = len(athlete_rows)
    avg_proof = total_proof / n if n else 0.0

    return {
        "athletes": athlete_rows,
        "talent_grade": talent_grade(avg_proof),
        "avg_proof": round(avg_proof, 1),
        "total_spend": round(total_spend, 0),
        "efficiency_score": efficiency_score(total_proof, total_spend),
        "position_depth": position_depth,
    }
