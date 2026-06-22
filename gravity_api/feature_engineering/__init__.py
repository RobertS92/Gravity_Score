"""BPXVR feature engineering — baselines, percentiles, trajectories."""

from gravity_api.feature_engineering.constants import FEATURE_SCHEMA_VERSION, MIN_COHORT_SIZE
from gravity_api.feature_engineering.engine import FeatureEngineeringEngine
from gravity_api.feature_engineering.materialize import materialize_bpxvr_snapshot
from gravity_api.feature_engineering.sport_specs import (
    ALL_SPORT_SPECS,
    SPECS_BY_SPORT,
    all_position_groups,
    export_specs_json,
    get_sport_spec,
)
from gravity_api.feature_engineering.types import (
    AthleteFeatureSnapshot,
    ProfileCard,
    TierLabel,
    TrajectoryClass,
)

__all__ = [
    "ALL_SPORT_SPECS",
    "AthleteFeatureSnapshot",
    "FEATURE_SCHEMA_VERSION",
    "FeatureEngineeringEngine",
    "MIN_COHORT_SIZE",
    "ProfileCard",
    "SPECS_BY_SPORT",
    "TierLabel",
    "TrajectoryClass",
    "all_position_groups",
    "export_specs_json",
    "get_sport_spec",
    "materialize_bpxvr_snapshot",
]
