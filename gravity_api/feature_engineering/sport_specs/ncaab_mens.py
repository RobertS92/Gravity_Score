"""Men's college basketball — all five positions."""

from __future__ import annotations

from gravity_api.feature_engineering.sport_specs._shared import (
    ACHIEVEMENT_WEIGHTS,
    BRAND_METRICS,
    COLLEGE_RECRUITING_KEYS,
    PROXIMITY_COLLEGE_METRICS,
    RISK_METRICS,
    VELOCITY_METRICS,
)
from gravity_api.feature_engineering.types import PositionProofSpec, SportFeatureSpec, StatWeight

_BASKETBALL_POSITIONS: tuple[PositionProofSpec, ...] = (
    PositionProofSpec(
        "PG",
        ("PG", "G", "POINT GUARD"),
        (
            StatWeight("pts", 0.20),
            StatWeight("ast", 0.30),
            StatWeight("stl", 0.15),
            StatWeight("ts_pct", 0.15),
            StatWeight("three_pct", 0.10),
            StatWeight("to", 0.10, "lower"),
        ),
        expected_games=30,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "SG",
        ("SG", "G", "SHOOTING GUARD"),
        (
            StatWeight("pts", 0.35),
            StatWeight("three_pct", 0.25),
            StatWeight("ts_pct", 0.20),
            StatWeight("stl", 0.12),
            StatWeight("ast", 0.08),
        ),
        expected_games=30,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "SF",
        ("SF", "SMALL FORWARD"),
        (
            StatWeight("pts", 0.30),
            StatWeight("reb", 0.25),
            StatWeight("ast", 0.15),
            StatWeight("ts_pct", 0.20),
            StatWeight("stl", 0.10),
        ),
        expected_games=30,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "PF",
        ("PF", "POWER FORWARD"),
        (
            StatWeight("reb", 0.30),
            StatWeight("pts", 0.28),
            StatWeight("blk", 0.17),
            StatWeight("ts_pct", 0.15),
            StatWeight("ast", 0.10),
        ),
        expected_games=30,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "C",
        ("C", "CENTER"),
        (
            StatWeight("reb", 0.30),
            StatWeight("blk", 0.25),
            StatWeight("pts", 0.25),
            StatWeight("fg_pct", 0.12),
            StatWeight("double_doubles", 0.08),
        ),
        expected_games=30,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
)

NCAAB_MENS_SPEC = SportFeatureSpec(
    sport="ncaab_mens",
    league="ncaa",
    display_name="Men's College Basketball",
    terminal_visible=True,
    position_groups=_BASKETBALL_POSITIONS,
    brand_metrics=BRAND_METRICS,
    proximity_metrics=PROXIMITY_COLLEGE_METRICS,
    velocity_metrics=VELOCITY_METRICS,
    risk_metrics=RISK_METRICS,
    min_games_for_proof_pctile=8,
)
