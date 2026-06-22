"""Feature vectorization for Gravity ML models."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

# Numeric keys extracted from raw_data / BPXVR flatten for ML
DEFAULT_NUMERIC_KEYS = [
    "instagram_followers",
    "tiktok_followers",
    "twitter_followers",
    "youtube_subscribers",
    "google_trends_score",
    "news_count_30d",
    "nil_valuation",
    "nil_deal_count",
    "data_quality_score",
    "partnership_brand_score",
    "partnership_proof_boost",
    "partnership_deal_count",
    "partnership_verified_count",
    "proof_composite_pctile",
    "proof_composite_index",
    "brand_composite_pctile",
    "proximity_composite_pctile",
    "velocity_composite_pctile",
    "proof_performance_index_pctile",
    "recruiting_stars",
    "recruiting_rank_national",
    "games_played_season",
    "roster_size",
    "roster_value",
    "roster_velocity",
    "roster_stability",
    "retention",
    "performance",
    "market_reach",
    "nil_collective_budget_est",
    "school_market_rank",
    "conference_media_index",
    "program_social_followers",
    "quality_score_prior",
    "gravity_score_prior",
]

OBJECTIVE_EXCLUDE: dict[str, set[str]] = {
    "quality": {
        "instagram_followers",
        "tiktok_followers",
        "twitter_followers",
        "google_trends_score",
        "partnership_brand_score",
        "nil_valuation",
        "program_social_followers",
    },
    "value": set(),
    "team_value": set(),
    "team_quality": {"partnership_brand_score", "nil_valuation"},
    "brand_sponsor": set(),
}


def build_feature_manifest(
    objective: str = "value",
    extra_keys: list[str] | None = None,
) -> list[str]:
    exclude = OBJECTIVE_EXCLUDE.get(objective, set())
    keys = [k for k in DEFAULT_NUMERIC_KEYS if k not in exclude]
    if extra_keys:
        keys.extend(extra_keys)
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
    if key in ("nil_valuation", "dollar_p50_usd") or "budget" in key:
        return math.log1p(max(0.0, val))
    return val


def stacked_features(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Concatenate values + mask for sklearn models."""
    return np.concatenate([values, mask], axis=0)
