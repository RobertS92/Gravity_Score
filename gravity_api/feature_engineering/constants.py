"""Thresholds and defaults for feature engineering."""

from __future__ import annotations

MIN_COHORT_SIZE = 30
MIN_COHORT_SIZE_DISPLAY = 5
PERCENTILE_CUTS = (75, 80, 90, 95, 99)

# YoY short-term trend bands
YOY_INCREASING_THRESHOLD = 0.10
YOY_DECLINING_THRESHOLD = -0.10

# Multi-year career slope bands (fraction per year)
SLOPE_ASCENDING = 0.05
SLOPE_IMPROVING = 0.02
SLOPE_DECLINING = -0.02
SLOPE_DESCENDING = -0.05

# Volatility: coefficient of variation above this → unstable
VOLATILITY_UNSTABLE_COV = 0.35
REGIME_CHANGE_THRESHOLD = 2

DEFAULT_PLATFORM_WEIGHTS: dict[str, float] = {
    "instagram": 0.45,
    "tiktok": 0.30,
    "twitter": 0.15,
    "youtube": 0.10,
}

FEATURE_SCHEMA_VERSION = "gravity_features_bpxvr_v1"
