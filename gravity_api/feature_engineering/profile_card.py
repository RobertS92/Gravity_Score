"""Build profile cards (level, percentile, tier, YoY, trajectory)."""

from __future__ import annotations

from typing import Sequence

from gravity_api.feature_engineering.constants import MIN_COHORT_SIZE
from gravity_api.feature_engineering.trajectory import classify_trajectory, stability_score
from gravity_api.feature_engineering.transforms import pct_change, percentile_rank, tier_from_percentile
from gravity_api.feature_engineering.types import (
    CohortBaseline,
    CohortConfidence,
    MetricProfileSpec,
    ProfileCard,
    TierLabel,
    TrajectoryClass,
)


def cohort_confidence_from_n(n: int) -> CohortConfidence:
    if n >= MIN_COHORT_SIZE:
        return CohortConfidence.HIGH
    if n >= MIN_COHORT_SIZE // 2:
        return CohortConfidence.MEDIUM
    return CohortConfidence.LOW


def build_profile_card(
    *,
    spec: MetricProfileSpec,
    current_value: float | None,
    history: Sequence[float],
    baseline: CohortBaseline | None,
    cohort_values: Sequence[float] | None = None,
    prior_pctile: float | None = None,
    confidence: float = 1.0,
    risk_mode: bool = False,
) -> ProfileCard:
    masked = current_value is None or confidence < spec.mask_below_confidence
    card = ProfileCard(metric_key=spec.metric_key)

    if masked:
        card.masked = True
        card.trajectory_class = TrajectoryClass.INSUFFICIENT_DATA
        return card

    card.level_raw = current_value
    values = list(cohort_values) if cohort_values else []
    n = len(values)

    if baseline and baseline.n >= MIN_COHORT_SIZE:
        card.level_pctile = percentile_rank(values, current_value) if values else None
        card.cohort_confidence = cohort_confidence_from_n(baseline.n)
    elif n >= MIN_COHORT_SIZE:
        card.level_pctile = percentile_rank(values, current_value)
        card.cohort_confidence = cohort_confidence_from_n(n)
    else:
        card.cohort_confidence = CohortConfidence.LOW
        card.masked = True

    card.level_tier = tier_from_percentile(card.level_pctile)

    if len(history) >= 2:
        card.delta_yoy_pct = pct_change(history[-1], history[-2])
        card.stability_score = stability_score(history)
        prior_tier = tier_from_percentile(prior_pctile) if prior_pctile else None
        card.trajectory_class = classify_trajectory(
            yoy_pct=card.delta_yoy_pct,
            history=history,
            prior_tier=prior_tier,
            current_tier=card.level_tier,
            risk_mode=risk_mode or spec.invert_for_risk,
        )
        if prior_pctile is not None and card.level_pctile is not None:
            card.yoy_percentile_change = card.level_pctile - prior_pctile

    if len(history) >= 2 and spec.deltas:
        if "7d" in spec.deltas and len(history) >= 2:
            card.delta_7d_pct = pct_change(history[-1], history[-2])
        if "30d" in spec.deltas and len(history) >= 2:
            card.delta_30d_pct = pct_change(history[-1], history[-2])
        if "90d" in spec.deltas and len(history) >= 4:
            card.delta_90d_pct = pct_change(history[-1], history[-4])

    return card


def build_proof_profile_card(
    *,
    performance_index: float | None,
    index_history: Sequence[float],
    cohort_index_values: Sequence[float],
    prior_index_pctile: float | None = None,
    games_played: int = 0,
    min_games: int = 4,
) -> ProfileCard:
    card = ProfileCard(metric_key="proof.performance_index")
    if performance_index is None:
        card.masked = True
        return card
    if games_played < min_games:
        card.masked = True
        card.level_raw = performance_index
        return card

    card.level_raw = performance_index
    if len(cohort_index_values) >= MIN_COHORT_SIZE:
        card.level_pctile = percentile_rank(cohort_index_values, performance_index)
        card.cohort_confidence = cohort_confidence_from_n(len(cohort_index_values))
    else:
        card.masked = True

    card.level_tier = tier_from_percentile(card.level_pctile)

    if len(index_history) >= 2:
        card.delta_yoy_pct = pct_change(index_history[-1], index_history[-2])
        card.stability_score = stability_score(index_history)
        card.trajectory_class = classify_trajectory(
            yoy_pct=card.delta_yoy_pct,
            history=list(index_history),
            prior_tier=tier_from_percentile(prior_index_pctile),
            current_tier=card.level_tier,
        )
        if prior_index_pctile is not None and card.level_pctile is not None:
            card.yoy_percentile_change = card.level_pctile - prior_index_pctile
    else:
        card.trajectory_class = TrajectoryClass.INSUFFICIENT_DATA

    return card
