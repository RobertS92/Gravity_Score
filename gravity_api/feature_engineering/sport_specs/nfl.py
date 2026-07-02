"""NFL position proof composites — all positions (pro)."""

from __future__ import annotations

from gravity_api.feature_engineering.sport_specs.cfb import _FOOTBALL_POSITIONS
from gravity_api.feature_engineering.sport_specs._shared import (
    ACHIEVEMENT_WEIGHTS_PRO_FOOTBALL,
    BRAND_METRICS,
    PROXIMITY_PRO_METRICS,
    RISK_PRO_METRICS,
    VELOCITY_PRO_METRICS,
)
from gravity_api.feature_engineering.types import PositionProofSpec, SportFeatureSpec, StatWeight

# Pro football: same position groups; add EPA/advanced where available
_NFL_POSITIONS: tuple[PositionProofSpec, ...] = tuple(
    PositionProofSpec(
        pg.position_group,
        pg.aliases,
        tuple(StatWeight(s.stat_key, s.weight * 0.90, s.direction) for s in pg.performance_stats)
        + (
            StatWeight(
                "epa_per_play",
                0.08 if pg.position_group in ("QB", "RB", "WR", "TE") else 0.05,
            ),
            StatWeight("snap_count", 0.05),
        ),
        expected_games=17,
        achievement_weights={
            **ACHIEVEMENT_WEIGHTS_PRO_FOOTBALL,
        },
    )
    for pg in _FOOTBALL_POSITIONS
)

NFL_SPEC = SportFeatureSpec(
    sport="nfl",
    league="nfl",
    display_name="NFL",
    terminal_visible=False,
    position_groups=_NFL_POSITIONS,
    brand_metrics=BRAND_METRICS,
    proximity_metrics=PROXIMITY_PRO_METRICS,
    velocity_metrics=VELOCITY_PRO_METRICS,
    risk_metrics=RISK_PRO_METRICS,
    min_games_for_proof_pctile=4,
    college_pro_bridge=True,
)
