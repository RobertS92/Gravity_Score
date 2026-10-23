"""Allow-listed feature names: raw observations + engineered transforms of raws.

SCORING_ML_FIX_SPEC §3 F2 — features must come from this manifest. Model outputs,
formula scores, and self-training priors are banned for every objective.
"""

from __future__ import annotations

from typing import Iterable

# Explicit banned names (SCORING_ML_FIX_SPEC §3 F2).
BANNED_FEATURE_NAMES: frozenset[str] = frozenset(
    {
        "gravity_score_prior",
        "brand_score_prior",
        "proof_score_prior",
        "quality_score_prior",
        "proximity_score_prior",
        "velocity_score_prior",
        "risk_score_prior",
        "dollar_p10_usd",
        "dollar_p50_usd",
        "dollar_p90_usd",
        "win_impact_score",
        "win_impact_score_v0",
        "target_impact_score",
        "gravity_score",
        "brand_score",
        "proof_score",
        "proximity_score",
        "velocity_score",
        "risk_score",
        # Model-output composites previously fed back as features (M3 leakage).
        "proof_composite_pctile",
        "proof_composite_index",
        "brand_composite_pctile",
        "proximity_composite_pctile",
        "velocity_composite_pctile",
        "raw_composite_score",
        "component_proxy_raw",
    }
)

BANNED_FEATURE_PREFIXES: tuple[str, ...] = (
    "target_",
    "dollar_p",
    "win_impact_score",
)

BANNED_FEATURE_SUBSTRINGS: tuple[str, ...] = (
    "_score_prior",
    "_proxy_raw",
)

# Raw observations + safe engineered transforms grouped by feature_set.
_SOCIAL_LEVELS = (
    "instagram_followers",
    "tiktok_followers",
    "twitter_followers",
    "youtube_subscribers",
)

_SOCIAL_DELTAS = (
    "instagram_followers_delta_30d",
    "instagram_followers_delta_90d",
    "tiktok_followers_delta_30d",
    "tiktok_followers_delta_90d",
    "twitter_followers_delta_30d",
    "twitter_followers_delta_90d",
    "trusted_social_reach",
    "trusted_social_reach_delta_30d",
    "trusted_social_reach_delta_90d",
)

_NEWS_TRENDS = (
    "news_count_7d",
    "news_count_30d",
    "news_count_90d",
    "google_trends_score",
    "wikipedia_views_30d",
)

_RECRUITING = (
    "recruiting_stars",
    "recruiting_rank_national",
)

_BOX_STATS = (
    "games_played_season",
    "games_started",
    "gs_rate",
    "participation_index",
    "points_per_game",
    "rebounds_per_game",
    "assists_per_game",
    "minutes_per_game",
    "passing_yards",
    "rushing_yards",
    "receiving_yards",
    "tackles_total",
    "sacks",
    "interceptions",
)

_TEAM_CONTEXT = (
    "team_wins",
    "team_losses",
    "team_win_pct",
    "conference_media_index",
    "program_social_followers",
    "school_market_rank",
    "nil_collective_budget_est",
)

_PARTNERSHIPS = (
    "partnership_deal_count",
    "partnership_verified_count",
    "partnership_brand_score",
    "partnership_proof_boost",
)

_DATA_QUALITY = (
    "data_quality_score",
    "feature_coverage",
)

_IMPACT_OUTPUTS_AS_FEATURES = (
    # Allowed as Gravity Proof-group inputs only after Impact gates pass.
    "impact_rate",
    "impact_wins_added",
    "impact_wins_added_career",
    "impact_wins_added_recency",
    "impact_rate_se",
)

_EXTERNAL_ESTIMATES = (
    # Features only — never labels / ground truth (spec §7).
    "nil_valuation",
)

FEATURE_SETS: dict[str, tuple[str, ...]] = {
    "impact_v1": (
        *_BOX_STATS,
        *_RECRUITING,
        *_TEAM_CONTEXT,
        *_DATA_QUALITY,
        "all_american_count",
        "national_awards_count",
        "seasons_with_gp",
        "height_in",
        "weight_lb",
        "class_year_num",
    ),
    "gravity_v1": (
        *_SOCIAL_LEVELS,
        *_SOCIAL_DELTAS,
        *_NEWS_TRENDS,
        *_RECRUITING,
        *_BOX_STATS,
        *_TEAM_CONTEXT,
        *_PARTNERSHIPS,
        *_DATA_QUALITY,
        *_IMPACT_OUTPUTS_AS_FEATURES,
        *_EXTERNAL_ESTIMATES,
        "transfer_count",
        "eligibility_remaining",
        "injury_days_365d",
    ),
    # Minimal set used by PIT unit tests / staging fixtures.
    "pit_core": (
        "instagram_followers",
        "tiktok_followers",
        "twitter_followers",
        "news_count_30d",
        "google_trends_score",
        "games_played_season",
        "points_per_game",
        "recruiting_stars",
        "data_quality_score",
    ),
}


def is_banned_feature(name: str) -> bool:
    if name in BANNED_FEATURE_NAMES:
        return True
    lower = name.lower()
    if any(lower.startswith(p) for p in BANNED_FEATURE_PREFIXES):
        return True
    if any(s in lower for s in BANNED_FEATURE_SUBSTRINGS):
        return True
    return False


def allowed_features(feature_set: str) -> list[str]:
    if feature_set not in FEATURE_SETS:
        known = ", ".join(sorted(FEATURE_SETS))
        raise KeyError(f"Unknown feature_set={feature_set!r}; expected one of: {known}")
    names = list(FEATURE_SETS[feature_set])
    banned = [n for n in names if is_banned_feature(n)]
    if banned:
        raise RuntimeError(f"feature_set {feature_set!r} contains banned names: {banned}")
    return names


def assert_features_allowed(names: Iterable[str]) -> None:
    bad = sorted({n for n in names if is_banned_feature(n)})
    if bad:
        raise ValueError(f"Banned features present: {bad}")
