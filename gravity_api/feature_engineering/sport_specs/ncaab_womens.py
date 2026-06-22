"""Women's college basketball — all five positions."""

from __future__ import annotations

from gravity_api.feature_engineering.sport_specs.ncaab_mens import _BASKETBALL_POSITIONS
from gravity_api.feature_engineering.sport_specs._shared import (
    BRAND_METRICS,
    PROXIMITY_COLLEGE_METRICS,
    RISK_METRICS,
    VELOCITY_METRICS,
)
from gravity_api.feature_engineering.types import SportFeatureSpec

NCAAB_WOMENS_SPEC = SportFeatureSpec(
    sport="ncaab_womens",
    league="ncaa",
    display_name="Women's College Basketball",
    terminal_visible=True,
    position_groups=_BASKETBALL_POSITIONS,
    brand_metrics=BRAND_METRICS,
    proximity_metrics=PROXIMITY_COLLEGE_METRICS,
    velocity_metrics=VELOCITY_METRICS,
    risk_metrics=RISK_METRICS,
    min_games_for_proof_pctile=8,
)
