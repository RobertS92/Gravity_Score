"""College commercial viability index and NIL dollar band heuristics."""

from __future__ import annotations

import json
import math
from typing import Any

import asyncpg

from gravity_api.feature_engineering.transforms import percentile_rank
from gravity_api.scrapers.parsers.stat_normalizer import flatten_raw_for_stats
from gravity_api.services.csc_report_builder import cap_displayed_percentile
from gravity_api.services.nil_valuation import nil_from_row, sanitize_nil_valuation_usd

COLLEGE_COMMERCIAL_SPORTS = frozenset({"cfb", "ncaab_mens", "ncaab_womens"})
COLLEGE_BASKETBALL_SPORTS = frozenset({"ncaab_mens", "ncaab_womens"})
_COHORT_INDEX_CACHE: dict[str, list[float]] = {}
_COHORT_PROMINENCE_CACHE: dict[str, list[float]] = {}


def _parse_raw_data(raw_data: Any) -> dict[str, Any]:
    if raw_data is None:
        return {}
    if isinstance(raw_data, dict):
        return raw_data
    if isinstance(raw_data, str):
        try:
            parsed = json.loads(raw_data)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


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
    """0–100 composite from social reach, recruiting, proof stats, and observed NIL.

    Tuned so typical roster depth stays mid-pack and only true commercial
    standouts (stars + reach + NIL) approach the top of the scale. The previous
    weights put almost every Power-5 athlete near the cohort ceiling, so the
    displayed percentile saturated at 99.
    """
    ig = _coerce_float(raw.get("instagram_followers"))
    tt = _coerce_float(raw.get("tiktok_followers"))
    tw = _coerce_float(raw.get("twitter_followers"))
    social_reach = ig + tt + tw
    # ~500k followers → ~18; 2M → ~25; 5M → ~30 (cap 32)
    social_score = min(32.0, 32.0 * math.log1p(social_reach) / math.log1p(5_000_000))

    stars = _coerce_float(raw.get("recruiting_stars"))
    # 3★ → 9, 4★ → 14, 5★ → 20 (was stars*5 which gave every 5★ a free 25)
    recruiting_score = min(20.0, stars * 4.0)

    proof_pctile = _coerce_float(raw.get("proof_performance_index_pctile"))
    if proof_pctile <= 0:
        proof_pctile = _coerce_float(raw.get("proof_composite_pctile"))
    proof_score = min(28.0, proof_pctile * 0.28 if proof_pctile > 0 else 0.0)
    if proof_score <= 0:
        sport = str(raw.get("sport") or "")
        stat_count = len(flatten_raw_for_stats(raw, sport)) if sport else 0
        # Sparse stats should not mint a high commercial floor.
        proof_score = min(8.0, stat_count * 0.8)

    nil_score = 0.0
    if _observed_nil(raw):
        nil_usd = sanitize_nil_valuation_usd(raw.get("nil_valuation"), raw) or 0.0
        if nil_usd > 0:
            # Observed NIL is direct market evidence. Keep it bounded inside the
            # index, then apply a dollar-calibrated floor at display time.
            nil_score = min(26.0, 26.0 * math.log1p(nil_usd) / math.log1p(20_000_000))

    return round(min(100.0, social_score + recruiting_score + proof_score + nil_score), 4)


def basketball_production_prominence(raw: dict[str, Any], sport: str) -> float:
    """Return a bounded per-game prominence signal for college basketball.

    This is intentionally not a general player-quality score. It only separates
    the small number of high-usage, highly visible players when NIL and social
    feeds are sparse. Games-played gating prevents tiny samples from minting a
    commercial-star signal.
    """
    if sport not in COLLEGE_BASKETBALL_SPORTS:
        return 0.0
    stats = flatten_raw_for_stats({**raw, "sport": sport}, sport)
    games = _coerce_float(stats.get("gp") or stats.get("games_played_season"))
    if games < 5:
        return 0.0

    def per_game(key: str) -> float:
        return max(0.0, _coerce_float(stats.get(key))) / games

    prominence = (
        min(per_game("pts"), 30.0) * 0.58
        + min(per_game("reb"), 12.0) * 0.28
        + min(per_game("ast"), 8.0) * 0.48
        + min(per_game("stl"), 4.0) * 0.55
        + min(per_game("blk"), 4.0) * 0.45
    )
    return round(min(28.0, prominence), 4)


def basketball_star_separation_bonus(
    prominence_percentile: float,
    commercial_index: float,
    prominence: float = 1.0,
) -> float:
    """Conservative upper-tail lift from elite production plus market evidence."""
    if prominence <= 0:
        return 0.0
    pct = max(0.0, min(100.0, float(prominence_percentile)))
    idx = max(0.0, min(100.0, float(commercial_index)))
    return round(
        max(0.0, pct - 95.0) * 0.60
        + max(0.0, pct - 99.0) * 10.00
        + max(0.0, idx - 45.0) * 0.25,
        4,
    )


def _estimate_nil_bands_from_index(index: float) -> tuple[float, float, float]:
    """Heuristic P10/P50/P90 from commercial viability index when NIL is unobserved."""
    p50 = 25_000.0 + (index / 100.0) ** 2 * 8_000_000.0
    p50 = max(25_000.0, min(50_000_000.0, p50))
    return p50 * 0.6, p50, p50 * 1.8


def _score_from_index_and_percentile(index: float, percentile: float, sport: str) -> float:
    """Blend absolute commercial index with cohort percentile for display G.

    Pure percentile ranking collapses when the cohort index distribution is
    left-skewed (most athletes share a similar low-signal prior) — everyone
    with any recruiting/social signal lands at 95–99. Mixing in the absolute
    index restores spread while still rewarding relative standing.
    """
    # College active rosters should have a broad 50-65 commercial middle. The
    # rare tail should ramp gradually through 66-75 and 75-80 instead of jumping
    # directly into 80+ on a single noisy market signal.
    knots = (
        (0.0, 50.0),
        (5.0, 52.0),
        (10.0, 54.0),
        (15.0, 56.0),
        (25.0, 58.0),
        (35.0, 61.0),
        (45.0, 64.0),
        (55.0, 68.0),
        (65.0, 73.0),
        (75.0, 79.0),
        (85.0, 86.0),
        (95.0, 92.0),
        (100.0, 94.0),
    )
    x = max(0.0, min(100.0, float(index)))
    abs_score = knots[-1][1]
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if x <= x1:
            t = (x - x0) / max(x1 - x0, 1e-9)
            abs_score = y0 + t * (y1 - y0)
            break

    pct = float(percentile)
    # Full active-sport rank is mostly a tie-breaker. Large tie clusters are
    # common in college feeds; percentile must not become the display score.
    rank_lift = max(0.0, pct - 90.0) * 0.18 + max(0.0, pct - 97.0) * 0.40
    if sport in {"ncaab_mens", "ncaab_womens"}:
        # Basketball has much sparser NIL/social evidence in the current feed.
        # Let only the very top of each active cohort surface as rare/very-rare
        # instead of leaving the sport with no meaningful upper tail.
        rank_lift += max(0.0, pct - 95.0) * 0.15
        rank_lift += max(0.0, pct - 99.0) * 2.50
        rank_lift += max(0.0, pct - 99.7) * 3.00

    blended = 0.90 * abs_score + 0.10 * pct + rank_lift
    return round(max(45.0, min(94.0, blended)), 4)


def _observed_nil_display_floor(nil_usd: float | None) -> float | None:
    """Map verified NIL dollars to a conservative commercial Gravity floor."""
    if nil_usd is None or nil_usd <= 0:
        return None
    knots = (
        (25_000.0, 50.0),
        (100_000.0, 54.0),
        (250_000.0, 58.0),
        (500_000.0, 62.0),
        (1_000_000.0, 66.0),
        (2_500_000.0, 71.0),
        (5_000_000.0, 75.0),
        (10_000_000.0, 78.0),
        (15_000_000.0, 80.0),
        (20_000_000.0, 82.0),
        (25_000_000.0, 84.0),
        (50_000_000.0, 90.0),
    )
    x = max(25_000.0, float(nil_usd))
    if x <= knots[0][0]:
        return knots[0][1]
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if x <= x1:
            t = (x - x0) / max(x1 - x0, 1e-9)
            return round(y0 + t * (y1 - y0), 4)
    return knots[-1][1]


async def compute_college_commercial_viability(
    conn: asyncpg.Connection,
    athlete_id: str,
    sport: str,
    raw: dict[str, Any],
) -> dict[str, Any]:
    """Commercial viability score and NIL dollar bands for college athletes."""
    index = compute_commercial_viability_index({**raw, "sport": sport})

    cohort_indices = _COHORT_INDEX_CACHE.get(sport)
    if cohort_indices is None:
        cohort_rows = await conn.fetch(
            """SELECT r.raw_data
               FROM raw_athlete_data r
               INNER JOIN athletes a ON a.id = r.athlete_id
               WHERE a.sport = $1
                 AND COALESCE(a.is_active, TRUE) = TRUE
                 AND r.id = (
                   SELECT id FROM raw_athlete_data
                   WHERE athlete_id = a.id
                   ORDER BY scraped_at DESC NULLS LAST
                   LIMIT 1
                 )""",
            sport,
        )
        cohort_indices = [
            compute_commercial_viability_index({**_parse_raw_data(row["raw_data"]), "sport": sport})
            for row in cohort_rows
        ]
        _COHORT_INDEX_CACHE[sport] = cohort_indices
    raw_pctile = percentile_rank(cohort_indices, index) if cohort_indices else 50.0
    displayed_pctile, _ = cap_displayed_percentile(
        raw_pctile,
        cohort_size=max(len(cohort_indices), 1),
    )
    if displayed_pctile is None:
        displayed_pctile = 50.0
    displayed_pctile = max(1.0, min(99.0, displayed_pctile))
    # Display Gravity = absolute index + cohort rank (not raw percentile alone).
    commercial_score = _score_from_index_and_percentile(index, displayed_pctile, sport)

    observed_nil = _observed_nil(raw)
    nil_usd = nil_from_row(raw) if observed_nil else None
    nil_floor = _observed_nil_display_floor(nil_usd)
    if nil_floor is not None:
        commercial_score = max(commercial_score, nil_floor)

    prominence = basketball_production_prominence(raw, sport)
    prominence_pctile: float | None = None
    star_separation_bonus = 0.0
    if sport in COLLEGE_BASKETBALL_SPORTS:
        cohort_prominence = _COHORT_PROMINENCE_CACHE.get(sport)
        if cohort_prominence is None:
            prominence_rows = await conn.fetch(
                """SELECT r.raw_data
                   FROM raw_athlete_data r
                   INNER JOIN athletes a ON a.id = r.athlete_id
                   WHERE a.sport = $1
                     AND COALESCE(a.is_active, TRUE) = TRUE
                     AND r.id = (
                       SELECT id FROM raw_athlete_data
                       WHERE athlete_id = a.id
                       ORDER BY scraped_at DESC NULLS LAST
                       LIMIT 1
                     )""",
                sport,
            )
            cohort_prominence = [
                basketball_production_prominence(_parse_raw_data(row["raw_data"]), sport)
                for row in prominence_rows
            ]
            _COHORT_PROMINENCE_CACHE[sport] = cohort_prominence
        prominence_pctile = (
            percentile_rank(cohort_prominence, prominence) if cohort_prominence else 50.0
        )
        star_separation_bonus = basketball_star_separation_bonus(
            prominence_pctile,
            index,
            prominence,
        )
        commercial_score = round(min(94.0, commercial_score + star_separation_bonus), 4)

    if nil_usd and nil_usd > 0:
        p10, p50, p90 = nil_usd * 0.6, nil_usd, nil_usd * 1.8
        nil_signal_source = "observed"
    else:
        p10, p50, p90 = _estimate_nil_bands_from_index(index)
        nil_signal_source = "estimated"

    return {
        "commercial_viability_index": index,
        "commercial_viability_score": commercial_score,
        "commercial_viability_percentile": displayed_pctile,
        "commercial_nil_market_floor": nil_floor,
        "basketball_production_prominence": prominence,
        "basketball_production_prominence_percentile": prominence_pctile,
        "basketball_star_separation_bonus": star_separation_bonus,
        "nil_dollar_p10": round(p10, 2),
        "nil_dollar_p50": round(p50, 2),
        "nil_dollar_p90": round(p90, 2),
        "nil_signal_source": nil_signal_source,
    }


__all__ = [
    "COLLEGE_COMMERCIAL_SPORTS",
    "basketball_production_prominence",
    "basketball_star_separation_bonus",
    "compute_college_commercial_viability",
    "compute_commercial_viability_index",
]
