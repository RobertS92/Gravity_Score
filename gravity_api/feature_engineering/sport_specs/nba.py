"""NBA — all five positions (pro)."""

from __future__ import annotations

from gravity_api.feature_engineering.sport_specs.ncaab_mens import _BASKETBALL_POSITIONS
from gravity_api.feature_engineering.sport_specs._shared import (
    ACHIEVEMENT_WEIGHTS_PRO_BASKETBALL,
    BRAND_METRICS,
    PROXIMITY_PRO_METRICS,
    RISK_PRO_METRICS,
    VELOCITY_PRO_METRICS,
)
from gravity_api.feature_engineering.types import PositionProofSpec, SportFeatureSpec, StatWeight

_NBA_POSITIONS: tuple[PositionProofSpec, ...] = tuple(
    PositionProofSpec(
        pg.position_group,
        pg.aliases,
        tuple(
            StatWeight(s.stat_key, s.weight * 0.82, s.direction)
            for s in pg.performance_stats
        )
        + (
            StatWeight("per", 0.06),
            StatWeight("bpm", 0.06),
            StatWeight("usage", 0.06),
        ),
        expected_games=82,
        achievement_weights={**ACHIEVEMENT_WEIGHTS_PRO_BASKETBALL},
    )
    for pg in _BASKETBALL_POSITIONS
)

NBA_SPEC = SportFeatureSpec(
    sport="nba",
    league="nba",
    display_name="NBA",
    terminal_visible=False,
    position_groups=_NBA_POSITIONS,
    brand_metrics=BRAND_METRICS,
    proximity_metrics=PROXIMITY_PRO_METRICS,
    velocity_metrics=VELOCITY_PRO_METRICS,
    risk_metrics=RISK_PRO_METRICS,
    min_games_for_proof_pctile=10,
    college_pro_bridge=True,
)
