"""WNBA — all five positions (pro)."""

from __future__ import annotations

from gravity_api.feature_engineering.sport_specs.ncaab_mens import _BASKETBALL_POSITIONS
from gravity_api.feature_engineering.sport_specs.nba import _NBA_POSITIONS
from gravity_api.feature_engineering.sport_specs._shared import (
    BRAND_METRICS,
    PROXIMITY_PRO_METRICS,
    RISK_PRO_METRICS,
    VELOCITY_PRO_METRICS,
)
from gravity_api.feature_engineering.types import SportFeatureSpec

WNBA_SPEC = SportFeatureSpec(
    sport="wnba",
    league="wnba",
    display_name="WNBA",
    terminal_visible=False,
    position_groups=_NBA_POSITIONS,
    brand_metrics=BRAND_METRICS,
    proximity_metrics=PROXIMITY_PRO_METRICS,
    velocity_metrics=VELOCITY_PRO_METRICS,
    risk_metrics=RISK_PRO_METRICS,
    min_games_for_proof_pctile=10,
    college_pro_bridge=True,
)
