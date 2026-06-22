"""Trajectory classification from YoY and multi-period history."""

from __future__ import annotations

from typing import Sequence

from gravity_api.feature_engineering.constants import (
    REGIME_CHANGE_THRESHOLD,
    SLOPE_ASCENDING,
    SLOPE_DECLINING,
    SLOPE_DESCENDING,
    SLOPE_IMPROVING,
    VOLATILITY_UNSTABLE_COV,
    YOY_DECLINING_THRESHOLD,
    YOY_INCREASING_THRESHOLD,
)
from gravity_api.feature_engineering.transforms import coefficient_of_variation, pct_change
from gravity_api.feature_engineering.types import TierLabel, TrajectoryClass


def linear_slope_pct_per_year(values: Sequence[float]) -> float | None:
    """Simple OLS slope normalized by mean → % change per period (season/year)."""
    n = len(values)
    if n < 2:
        return None
    mean_y = sum(values) / n
    if abs(mean_y) < 1e-9:
        return None
    x_mean = (n - 1) / 2.0
    num = sum((i - x_mean) * (values[i] - mean_y) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    if den <= 0:
        return None
    slope = num / den
    return slope / abs(mean_y)


def count_regime_changes(yoy_values: Sequence[float | None]) -> int:
    signs: list[int] = []
    for v in yoy_values:
        if v is None:
            continue
        if v >= YOY_INCREASING_THRESHOLD:
            signs.append(1)
        elif v <= YOY_DECLINING_THRESHOLD:
            signs.append(-1)
        else:
            signs.append(0)
    if len(signs) < 2:
        return 0
    changes = 0
    prev = signs[0]
    for s in signs[1:]:
        if s != 0 and prev != 0 and s != prev:
            changes += 1
        if s != 0:
            prev = s
    return changes


def stability_score(values: Sequence[float]) -> float | None:
    """1 - normalized CoV; higher = more stable."""
    cov = coefficient_of_variation(values)
    if cov is None:
        return None
    return max(0.0, min(1.0, 1.0 - cov))


def classify_yoy_trend(yoy_pct: float | None) -> str:
    if yoy_pct is None:
        return "unknown"
    if yoy_pct >= YOY_INCREASING_THRESHOLD:
        return "increasing"
    if yoy_pct <= YOY_DECLINING_THRESHOLD:
        return "declining"
    return "stable"


def classify_trajectory(
    *,
    yoy_pct: float | None,
    history: Sequence[float],
    prior_tier: TierLabel | None = None,
    current_tier: TierLabel | None = None,
    risk_mode: bool = False,
) -> TrajectoryClass:
    if len(history) < 2:
        return TrajectoryClass.INSUFFICIENT_DATA

    cov = coefficient_of_variation(history)
    unstable = cov is not None and cov > VOLATILITY_UNSTABLE_COV
    regime_changes = count_regime_changes(
        [pct_change(history[i], history[i - 1]) for i in range(1, len(history))]
    )

    slope = linear_slope_pct_per_year(history)
    yoy = yoy_pct

    # Tier jump breakout / cooldown
    if prior_tier and current_tier:
        tier_order = [
            TierLabel.LOW,
            TierLabel.LOWER_MID,
            TierLabel.MID,
            TierLabel.UPPER_MID,
            TierLabel.HIGH,
            TierLabel.ELITE,
            TierLabel.GENERATIONAL,
        ]
        try:
            prior_i = tier_order.index(prior_tier)
            curr_i = tier_order.index(current_tier)
            if curr_i - prior_i >= 2:
                return TrajectoryClass.BREAKOUT
            if prior_i >= tier_order.index(TierLabel.ELITE) and curr_i <= tier_order.index(TierLabel.UPPER_MID):
                return TrajectoryClass.DECLINING_FROM_ELITE
        except ValueError:
            pass

    if unstable or regime_changes >= REGIME_CHANGE_THRESHOLD:
        if yoy is not None and yoy >= YOY_INCREASING_THRESHOLD:
            return TrajectoryClass.IMPROVING_UNSTABLE if not risk_mode else TrajectoryClass.UNSTABLE
        return TrajectoryClass.UNSTABLE

    if risk_mode:
        if yoy is not None and yoy >= YOY_INCREASING_THRESHOLD:
            return TrajectoryClass.WORSENING
        if yoy is not None and yoy <= YOY_DECLINING_THRESHOLD:
            return TrajectoryClass.IMPROVING
        return TrajectoryClass.STABLE

    ascending = (
        yoy is not None
        and yoy >= YOY_INCREASING_THRESHOLD
        and slope is not None
        and slope >= SLOPE_ASCENDING
    )
    if ascending:
        return TrajectoryClass.ASCENDING

    if yoy is not None and yoy >= YOY_INCREASING_THRESHOLD:
        return TrajectoryClass.IMPROVING_STABLE if (slope or 0) >= 0 else TrajectoryClass.IMPROVING

    if slope is not None and slope >= SLOPE_IMPROVING and (yoy is None or abs(yoy) < YOY_INCREASING_THRESHOLD):
        return TrajectoryClass.LATE_BLOOMER

    descending = (
        yoy is not None
        and yoy <= YOY_DECLINING_THRESHOLD
        and slope is not None
        and slope <= SLOPE_DESCENDING
    )
    if descending:
        return TrajectoryClass.DESCENDING

    if yoy is not None and yoy <= YOY_DECLINING_THRESHOLD:
        return TrajectoryClass.DECLINING

    if slope is not None and slope <= SLOPE_DECLINING:
        return TrajectoryClass.DECLINING

    return TrajectoryClass.STABLE
