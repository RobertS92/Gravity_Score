"""Feature vectorization for Gravity ML models."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from gravity_ml.features.manifest import is_banned_feature

PRO_SPORTS = frozenset({"nfl", "nba", "wnba"})

SHARED_NUMERIC_KEYS = [
    "instagram_followers",
    "tiktok_followers",
    "twitter_followers",
    "youtube_subscribers",
    "google_trends_score",
    "news_count_30d",
    "data_quality_score",
    "partnership_brand_score",
    "partnership_proof_boost",
    "partnership_deal_count",
    "partnership_verified_count",
    # Legacy composite / prior keys retained in the catalog for older bundles
    # but stripped by build_feature_manifest via BANNED_FEATURES (F2).
    "proof_composite_pctile",
    "proof_composite_index",
    "brand_composite_pctile",
    "proximity_composite_pctile",
    "velocity_composite_pctile",
    "proof_performance_index_pctile",
    "games_played_season",
    "conference_media_index",
    "program_social_followers",
    "quality_score_prior",
    "gravity_score_prior",
]

COLLEGE_NUMERIC_KEYS = [
    "nil_valuation",
    "nil_deal_count",
    "recruiting_stars",
    "recruiting_rank_national",
    "nil_collective_budget_est",
    "school_market_rank",
]

PRO_NUMERIC_KEYS = [
    "contract_total_usd",
    "contract_guaranteed_usd",
    "contract_aav_usd",
    "contract_aav",
    "endorsement_value_usd",
    "endorsement_earnings",
    "total_earnings_usd",
    "forbes_list_rank",
    "fantasy_adp",
]

IMPACT_NUMERIC_KEYS = [
    "games_played_season",
    "games_started",
    "gs_rate",
    "participation_index",
    "team_wins",
    "team_losses",
    "team_win_pct",
    "team_win_pct_percentile",
    "proof_performance_index_pctile",
    "proof_composite_pctile",
    "proof_composite_index",
    "proof_residual_team",
    "proof_x_participation",
    "proof_x_weak_team",
    "recruiting_stars",
    "recruiting_rank_national",
    "recruiting_outperformance",
    "velocity_composite_pctile",
    "velocity_proof_yoy",
    "data_quality_score",
    "external_quality_score",
    "all_american_count",
    "national_awards_count",
    "seasons_with_gp",
    "team_record_observed",
    "games_started_observed",
    "gp_observed",
    "impact_confidence",
]

# Legacy default — college-oriented training exports.
DEFAULT_NUMERIC_KEYS = SHARED_NUMERIC_KEYS + COLLEGE_NUMERIC_KEYS

# Banned for every objective (SCORING_ML_FIX_SPEC §3 F2). Enforced in
# build_feature_manifest in addition to the feature allow-list.
BANNED_FEATURES_EVERY_OBJECTIVE: frozenset[str] = frozenset(
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
        "proof_composite_pctile",
        "proof_composite_index",
        "brand_composite_pctile",
        "proximity_composite_pctile",
        "velocity_composite_pctile",
        "gravity_score",
        "brand_score",
        "proof_score",
        "proximity_score",
        "velocity_score",
        "risk_score",
        "raw_composite_score",
        "component_proxy_raw",
    }
)

OBJECTIVE_EXCLUDE: dict[str, set[str]] = {
    "quality": {
        "instagram_followers",
        "tiktok_followers",
        "twitter_followers",
        "google_trends_score",
        "partnership_brand_score",
        "nil_valuation",
        "program_social_followers",
        "endorsement_value_usd",
        "endorsement_earnings",
        "contract_aav_usd",
    },
    "impact": {
        "win_impact_score",
        "win_impact_score_v0",
        "target_impact_score",
        "nil_valuation",
        "nil_deal_count",
        "instagram_followers",
        "tiktok_followers",
        "twitter_followers",
        "external_quality_score",
    },
    "value": {
        "nil_valuation",
        "nil_deal_count",
        "nil_deal_count_verified",
        "nil_deal_max_usd",
        "nil_deal_sum_usd",
        "dollar_p50_usd",
        "dollar_p10_usd",
        "dollar_p90_usd",
    },
    "gravity": {
        "nil_deal_count",
        "nil_deal_count_verified",
        "nil_deal_max_usd",
        "nil_deal_sum_usd",
        "dollar_p50_usd",
        "dollar_p10_usd",
        "dollar_p90_usd",
    },
    "team_value": set(),
    "team_quality": {"partnership_brand_score", "nil_valuation", "contract_aav_usd"},
    "brand_sponsor": set(),
}


def league_for_sport(sport: str | None) -> str:
    if sport and sport.lower() in PRO_SPORTS:
        return "pro"
    return "ncaa"


def numeric_keys_for_league(league: str) -> list[str]:
    if league == "pro":
        return SHARED_NUMERIC_KEYS + PRO_NUMERIC_KEYS
    return SHARED_NUMERIC_KEYS + COLLEGE_NUMERIC_KEYS


def build_feature_manifest(
    objective: str = "value",
    extra_keys: list[str] | None = None,
    *,
    league: str | None = None,
    sport: str | None = None,
) -> list[str]:
    resolved_league = league or league_for_sport(sport)
    exclude = set(OBJECTIVE_EXCLUDE.get(objective, set())) | set(BANNED_FEATURES_EVERY_OBJECTIVE)
    if objective == "impact":
        keys = [k for k in IMPACT_NUMERIC_KEYS if k not in exclude and not is_banned_feature(k)]
        if extra_keys:
            keys.extend(k for k in extra_keys if k not in exclude and not is_banned_feature(k))
        return sorted(set(keys))
    if resolved_league == "pro":
        exclude = exclude | frozenset(COLLEGE_NUMERIC_KEYS)
    else:
        exclude = exclude | frozenset(PRO_NUMERIC_KEYS)
    keys = [
        k
        for k in numeric_keys_for_league(resolved_league)
        if k not in exclude and not is_banned_feature(k)
    ]
    if extra_keys:
        keys.extend(k for k in extra_keys if k not in exclude and not is_banned_feature(k))
    return sorted(set(keys))


class FeatureVectorizer:
    def __init__(self, feature_names: list[str]) -> None:
        self.feature_names = list(feature_names)
        self._index = {n: i for i, n in enumerate(self.feature_names)}

    @classmethod
    def from_manifest_path(cls, path: Path) -> FeatureVectorizer:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data["feature_names"])

    def vectorize(self, raw: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
        """Return (values, mask) where mask=1.0 if observed."""
        n = len(self.feature_names)
        values = np.zeros(n, dtype=np.float64)
        mask = np.zeros(n, dtype=np.float64)
        for i, key in enumerate(self.feature_names):
            val = raw.get(key)
            if val is None:
                continue
            try:
                f = float(val)
            except (TypeError, ValueError):
                continue
            if math.isnan(f) or math.isinf(f):
                continue
            values[i] = _transform(key, f)
            mask[i] = 1.0
        return values, mask

    def to_dict(self) -> dict[str, Any]:
        return {"feature_names": self.feature_names}


def _transform(key: str, val: float) -> float:
    if "followers" in key or "subscribers" in key or key.endswith("_reach"):
        return math.log1p(max(0.0, val))
    if key in (
        "nil_valuation",
        "dollar_p50_usd",
        "contract_total_usd",
        "contract_guaranteed_usd",
        "contract_aav_usd",
        "contract_aav",
        "endorsement_value_usd",
        "endorsement_earnings",
        "total_earnings_usd",
    ) or "budget" in key:
        return math.log1p(max(0.0, val))
    return val


def stacked_features(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Concatenate values + mask for sklearn models."""
    return np.concatenate([values, mask], axis=0)
