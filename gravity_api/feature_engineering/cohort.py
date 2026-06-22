"""Cohort baseline resolution with fallback hierarchy."""

from __future__ import annotations

from typing import Sequence

from gravity_api.feature_engineering.constants import MIN_COHORT_SIZE
from gravity_api.feature_engineering.positions import cohort_key
from gravity_api.feature_engineering.transforms import baseline_distribution, percentile_rank
from gravity_api.feature_engineering.types import CohortBaseline


def resolve_cohort_values(
    *,
    metric_values_by_athlete: dict[str, float],
    position_group: str,
    filter_fn=None,
) -> list[float]:
    """Extract cohort value list for a position group."""
    out: list[float] = []
    for _aid, val in metric_values_by_athlete.items():
        if filter_fn and not filter_fn(_aid):
            continue
        out.append(float(val))
    return out


def build_cohort_baseline(
    *,
    league: str,
    sport: str,
    position_group: str,
    season_year: int | None,
    window_key: str,
    metric_key: str,
    values: Sequence[float],
    cohort_level: str = "primary",
) -> CohortBaseline:
    dist = baseline_distribution(values)
    return CohortBaseline(
        league=league,
        sport=sport,
        position_group=position_group,
        season_year=season_year,
        window_key=window_key,
        metric_key=metric_key,
        cohort_level=cohort_level,
        n=int(dist["n"] or 0),
        mean=dist["mean"],
        std=dist["std"],
        p50=dist["p50"],
        p75=dist["p75"],
        p80=dist["p80"],
        p90=dist["p90"],
        p95=dist["p95"],
        p99=dist["p99"],
    )


def lookup_baseline_with_fallback(
    baselines: dict[str, CohortBaseline],
    *,
    league: str,
    sport: str,
    position_group: str,
    season_year: int | None,
    window_key: str,
    metric_key: str,
) -> CohortBaseline | None:
    """Try primary → season → multi-year → sport-wide fallback keys."""
    candidates = [
        cohort_key(league=league, sport=sport, position_group=position_group, season_year=season_year, window=window_key),
        cohort_key(league=league, sport=sport, position_group=position_group, season_year=season_year, window="all"),
        cohort_key(league=league, sport=sport, position_group=position_group, season_year=None, window=window_key),
        cohort_key(league=league, sport=sport, position_group="ALL", season_year=season_year, window=window_key),
    ]
    for key in candidates:
        for level in ("primary", "fallback_season", "fallback_multi_year", "fallback_sport"):
            composite = f"{key}:{metric_key}:{level}"
            if composite in baselines:
                b = baselines[composite]
                if b.n >= MIN_COHORT_SIZE or level == "fallback_sport":
                    return b
    return None


def athlete_percentile_vs_baseline(value: float | None, baseline: CohortBaseline | None, cohort_values: Sequence[float]) -> float | None:
    if value is None:
        return None
    if cohort_values and len(cohort_values) >= MIN_COHORT_SIZE:
        return percentile_rank(cohort_values, value)
    if baseline and baseline.n >= MIN_COHORT_SIZE and baseline.p50 is not None and baseline.std and baseline.std > 0:
        # Approximate from stored distribution when raw list unavailable
        return percentile_rank(
            [baseline.p50, baseline.p75 or baseline.p50, baseline.p90 or baseline.p50, baseline.p95 or baseline.p50],
            value,
        )
    return None
