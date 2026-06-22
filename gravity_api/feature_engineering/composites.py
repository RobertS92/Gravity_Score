"""Proof performance index and achievement/recruiting composites."""

from __future__ import annotations

from typing import Any

from gravity_api.feature_engineering.sport_specs import get_position_spec
from gravity_api.feature_engineering.transforms import z_score
from gravity_api.feature_engineering.types import PositionProofSpec, StatWeight


def _stat_z(
    stats: dict[str, float],
    stat_key: str,
    cohort_means: dict[str, float],
    cohort_stds: dict[str, float],
    direction: str,
) -> float | None:
    raw = stats.get(stat_key)
    if raw is None:
        return None
    mean = cohort_means.get(stat_key)
    std = cohort_stds.get(stat_key)
    if mean is None or std is None:
        return None
    z = z_score(float(raw), float(mean), float(std))
    return -z if direction == "lower" else z


def compute_performance_index(
    *,
    sport: str,
    position_group: str,
    season_stats: dict[str, float],
    cohort_means: dict[str, float],
    cohort_stds: dict[str, float],
) -> float | None:
    """Weighted sum of cohort z-scores for position-native stats."""
    pos_spec = get_position_spec(sport, position_group)
    scores: list[tuple[float, float]] = []
    for sw in pos_spec.performance_stats:
        z = _stat_z(season_stats, sw.stat_key, cohort_means, cohort_stds, sw.direction)
        if z is not None:
            scores.append((z, sw.weight))
    if not scores:
        return None
    total_w = sum(w for _, w in scores)
    if total_w <= 0:
        return None
    return sum(s * w for s, w in scores) / total_w


def compute_recruiting_signal(
    raw: dict[str, Any],
    recruiting_keys: tuple[str, ...],
) -> float | None:
    stars = raw.get("recruiting_stars")
    rank_nat = raw.get("recruiting_rank_national")
    score = 0.0
    weight = 0.0
    if stars is not None:
        score += float(stars) * 20.0
        weight += 1.0
    if rank_nat is not None and float(rank_nat) > 0:
        score += max(0.0, 100.0 - min(100.0, float(rank_nat) / 50.0))
        weight += 1.0
    if weight == 0:
        return None
    return score / weight


def compute_achievement_density(
    achievements: list[dict[str, Any]],
    weights: dict[str, float],
    *,
    seasons_ago_decay: float = 0.85,
) -> float:
    total = 0.0
    for ach in achievements:
        kind = str(ach.get("type", "")).lower()
        w = weights.get(kind, 0.2)
        seasons_ago = int(ach.get("seasons_ago", 0))
        total += w * (seasons_ago_decay ** seasons_ago)
    return total


def blend_proof_with_recruiting_prior(
    perf_pctile: float | None,
    recruiting_pctile: float | None,
    games_played: int,
    expected_games: int,
) -> float | None:
    if perf_pctile is None and recruiting_pctile is None:
        return None
    if recruiting_pctile is None:
        return perf_pctile
    if perf_pctile is None:
        return recruiting_pctile
    w = min(1.0, games_played / max(expected_games, 1))
    return w * perf_pctile + (1.0 - w) * recruiting_pctile
