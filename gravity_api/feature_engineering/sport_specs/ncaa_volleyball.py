"""NCAA volleyball (women's) — all positions."""

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

_VOLLEYBALL_POSITIONS: tuple[PositionProofSpec, ...] = (
    PositionProofSpec(
        "OH",
        ("OH", "OUTSIDE HITTER", "OUTSIDE"),
        (
            StatWeight("kills", 0.28),
            StatWeight("kills_per_set", 0.25),
            StatWeight("hitting_pct", 0.22),
            StatWeight("aces", 0.10),
            StatWeight("digs", 0.15),
        ),
        expected_games=30,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "MB",
        ("MB", "MIDDLE", "MIDDLE BLOCKER"),
        (
            StatWeight("kills", 0.22),
            StatWeight("blocks", 0.28),
            StatWeight("blocks_per_set", 0.25),
            StatWeight("hitting_pct", 0.15),
            StatWeight("aces", 0.10),
        ),
        expected_games=30,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "S",
        ("S", "SETTER"),
        (
            StatWeight("assists", 0.35),
            StatWeight("assists_per_set", 0.25),
            StatWeight("aces", 0.15),
            StatWeight("digs", 0.15),
            StatWeight("setting_efficiency", 0.10),
        ),
        expected_games=30,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "LIB",
        ("LIB", "L", "LIBERO", "DS", "DEFENSIVE SPECIALIST"),
        (
            StatWeight("digs", 0.35),
            StatWeight("digs_per_set", 0.30),
            StatWeight("receive_rating", 0.25),
            StatWeight("aces", 0.10),
        ),
        expected_games=30,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "OPP",
        ("OPP", "OPPOSITE", "RIGHT SIDE", "RS"),
        (
            StatWeight("kills", 0.30),
            StatWeight("kills_per_set", 0.25),
            StatWeight("hitting_pct", 0.20),
            StatWeight("blocks", 0.15),
            StatWeight("aces", 0.10),
        ),
        expected_games=30,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
)

NCAA_VOLLEYBALL_SPEC = SportFeatureSpec(
    sport="ncaa_volleyball",
    league="ncaa",
    display_name="College Volleyball",
    terminal_visible=True,
    position_groups=_VOLLEYBALL_POSITIONS,
    brand_metrics=BRAND_METRICS,
    proximity_metrics=PROXIMITY_COLLEGE_METRICS,
    velocity_metrics=VELOCITY_METRICS,
    risk_metrics=RISK_METRICS,
    min_games_for_proof_pctile=8,
)
