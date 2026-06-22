"""NCAA baseball — all positions (SP, RP, C, IF, OF, UT)."""

from __future__ import annotations

from gravity_api.feature_engineering.sport_specs._shared import (
    ACHIEVEMENT_WEIGHTS,
    BRAND_METRICS,
    COLLEGE_RECRUITING_KEYS,
    PROXIMITY_BASEBALL_METRICS,
    RISK_METRICS,
    VELOCITY_METRICS,
)
from gravity_api.feature_engineering.types import PositionProofSpec, SportFeatureSpec, StatWeight

_BASEBALL_POSITIONS: tuple[PositionProofSpec, ...] = (
    PositionProofSpec(
        "SP",
        ("SP", "STARTER", "STARTING PITCHER"),
        (
            StatWeight("era", 0.30, "lower"),
            StatWeight("whip", 0.25, "lower"),
            StatWeight("k9", 0.20),
            StatWeight("ip", 0.15),
            StatWeight("wins", 0.10),
        ),
        expected_games=15,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "RP",
        ("RP", "MR", "SU", "CL", "CLOSER", "RELIEVER"),
        (
            StatWeight("era", 0.28, "lower"),
            StatWeight("whip", 0.22, "lower"),
            StatWeight("k9", 0.20),
            StatWeight("saves", 0.18),
            StatWeight("ip", 0.12),
        ),
        expected_games=25,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "C",
        ("C", "CATCHER"),
        (
            StatWeight("ops", 0.25),
            StatWeight("avg", 0.20),
            StatWeight("obp", 0.15),
            StatWeight("slg", 0.15),
            StatWeight("cs_pct", 0.15),
            StatWeight("fielding_pct", 0.10),
        ),
        expected_games=50,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "IF",
        ("IF", "1B", "2B", "3B", "SS", "INF", "INFIELD"),
        (
            StatWeight("ops", 0.30),
            StatWeight("avg", 0.20),
            StatWeight("obp", 0.15),
            StatWeight("slg", 0.15),
            StatWeight("fielding_pct", 0.10),
            StatWeight("sb", 0.10),
        ),
        expected_games=50,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "OF",
        ("OF", "LF", "CF", "RF", "OUTFIELD"),
        (
            StatWeight("ops", 0.30),
            StatWeight("avg", 0.18),
            StatWeight("obp", 0.15),
            StatWeight("slg", 0.17),
            StatWeight("sb", 0.12),
            StatWeight("rf_assists", 0.08),
        ),
        expected_games=50,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "UT",
        ("UT", "UTIL", "DH", "DESIGNATED HITTER"),
        (
            StatWeight("ops", 0.35),
            StatWeight("avg", 0.20),
            StatWeight("obp", 0.15),
            StatWeight("slg", 0.18),
            StatWeight("sb", 0.12),
        ),
        expected_games=45,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
)

NCAA_BASEBALL_SPEC = SportFeatureSpec(
    sport="ncaa_baseball",
    league="ncaa",
    display_name="College Baseball",
    terminal_visible=True,
    position_groups=_BASEBALL_POSITIONS,
    brand_metrics=BRAND_METRICS,
    proximity_metrics=PROXIMITY_BASEBALL_METRICS,
    velocity_metrics=VELOCITY_METRICS,
    risk_metrics=RISK_METRICS,
    min_games_for_proof_pctile=10,
)
