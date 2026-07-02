"""College commercial viability index and NIL dollar band heuristics."""

from __future__ import annotations

import math
from typing import Any

import asyncpg

from gravity_api.feature_engineering.transforms import percentile_rank
from gravity_api.scrapers.parsers.stat_normalizer import flatten_raw_for_stats
from gravity_api.services.csc_report_builder import cap_displayed_percentile
from gravity_api.services.nil_valuation import nil_from_row, sanitize_nil_valuation_usd

COLLEGE_COMMERCIAL_SPORTS = frozenset({"cfb", "ncaab_mens", "ncaab_womens"})


def _coerce_float(val: Any) -> float:
    if val is None or val == "":
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _observed_nil(raw: dict[str, Any]) -> bool:
    flag = raw.get("nil_valuation_observed")
    if flag is None:
        return False
    try:
        return int(float(flag)) == 1
    except (TypeError, ValueError):
        return bool(flag)


def compute_commercial_viability_index(raw: dict[str, Any]) -> float:
    """0–100 composite from social reach, recruiting, proof stats, and observed NIL."""
    ig = _coerce_float(raw.get("instagram_followers"))
    tt = _coerce_float(raw.get("tiktok_followers"))
    tw = _coerce_float(raw.get("twitter_followers"))
    social_reach = ig + tt + tw
    social_score = min(35.0, 35.0 * math.log1p(social_reach) / math.log1p(2_000_000))

    stars = _coerce_float(raw.get("recruiting_stars"))
    recruiting_score = min(25.0, stars * 5.0)

    proof_pctile = _coerce_float(raw.get("proof_performance_index_pctile"))
    if proof_pctile <= 0:
        proof_pctile = _coerce_float(raw.get("proof_composite_pctile"))
    proof_score = min(25.0, proof_pctile * 0.25 if proof_pctile > 0 else 0.0)
    if proof_score <= 0:
        sport = str(raw.get("sport") or "")
        stat_count = len(flatten_raw_for_stats(raw, sport)) if sport else 0
        proof_score = min(15.0, stat_count * 1.5)

    nil_score = 0.0
    if _observed_nil(raw):
        nil_usd = sanitize_nil_valuation_usd(raw.get("nil_valuation"), raw) or 0.0
        if nil_usd > 0:
            nil_score = min(15.0, 15.0 * math.log1p(nil_usd) / math.log1p(10_000_000))

    return round(min(100.0, social_score + recruiting_score + proof_score + nil_score), 4)


def _estimate_nil_bands_from_index(index: float) -> tuple[float, float, float]:
    """Heuristic P10/P50/P90 from commercial viability index when NIL is unobserved."""
    p50 = 25_000.0 + (index / 100.0) ** 2 * 8_000_000.0
    p50 = max(25_000.0, min(50_000_000.0, p50))
    return p50 * 0.6, p50, p50 * 1.8


async def compute_college_commercial_viability(
    conn: asyncpg.Connection,
    athlete_id: str,
    sport: str,
    raw: dict[str, Any],
) -> dict[str, Any]:
    """Percentile-ranked commercial viability and NIL dollar bands for college athletes."""
    index = compute_commercial_viability_index({**raw, "sport": sport})

    cohort_rows = await conn.fetch(
        """SELECT r.raw_data
           FROM raw_athlete_data r
           INNER JOIN athletes a ON a.id = r.athlete_id
           WHERE a.sport = $1
             AND r.id = (
               SELECT id FROM raw_athlete_data
               WHERE athlete_id = a.id
               ORDER BY scraped_at DESC NULLS LAST
               LIMIT 1
             )""",
        sport,
    )
    cohort_indices = [
        compute_commercial_viability_index({**dict(row["raw_data"] or {}), "sport": sport})
        for row in cohort_rows
    ]
    raw_pctile = percentile_rank(cohort_indices, index)
    displayed_pctile, _ = cap_displayed_percentile(
        raw_pctile,
        cohort_size=max(len(cohort_indices), 1),
    )
    if displayed_pctile is None:
        displayed_pctile = 50.0
    displayed_pctile = max(1.0, min(99.0, displayed_pctile))

    observed_nil = _observed_nil(raw)
    nil_usd = nil_from_row(raw) if observed_nil else None
    if nil_usd and nil_usd > 0:
        p10, p50, p90 = nil_usd * 0.6, nil_usd, nil_usd * 1.8
        nil_signal_source = "observed"
    else:
        p10, p50, p90 = _estimate_nil_bands_from_index(index)
        nil_signal_source = "estimated"

    return {
        "commercial_viability_index": index,
        "commercial_viability_score": displayed_pctile,
        "nil_dollar_p10": round(p10, 2),
        "nil_dollar_p50": round(p50, 2),
        "nil_dollar_p90": round(p90, 2),
        "nil_signal_source": nil_signal_source,
    }


__all__ = [
    "COLLEGE_COMMERCIAL_SPORTS",
    "compute_college_commercial_viability",
    "compute_commercial_viability_index",
]
