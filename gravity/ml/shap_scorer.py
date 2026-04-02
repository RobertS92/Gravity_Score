"""SHAP attributions → five Gravity components + top drivers."""

from __future__ import annotations

from typing import Literal

import numpy as np
import torch

from gravity.ml.feature_engineer import FEATURE_NAMES, N_FEATURE_COLUMNS
from gravity.ml.network import GravityNet

ComponentName = Literal["brand", "proof", "proximity", "velocity", "risk"]


def _route_feature(fname: str) -> ComponentName:
    fn = fname.lower()
    if any(
        k in fn
        for k in (
            "injury",
            "has_current_injury",
            "transfer",
            "is_transfer",
        )
    ):
        return "risk"
    if any(
        k in fn
        for k in (
            "instagram",
            "twitter",
            "news",
            "google_trends",
            "nil_deals",
            "combined_social",
        )
    ):
        return "brand"
    if any(
        k in fn
        for k in (
            "ppg",
            "rpg",
            "apg",
            "fg_pct",
            "three_pt",
            "ft_pct",
            "career_points",
            "career_reb",
            "career_ass",
            "recruiting",
            "all_american",
            "heisman",
            "conference_awards",
            "wooden",
            "naismith",
            "draft_rank",
        )
    ):
        return "proof"
    if any(
        k in fn
        for k in (
            "nil_valuation",
            "nil_log",
            "vs_team",
            "vs_global",
            "vs_conf",
            "conf_bucket",
            "conference_ordinal",
            "team_hash",
            "height",
            "weight",
        )
    ):
        return "proximity"
    if any(
        k in fn
        for k in (
            "per_year",
            "growth",
            "nil_log_x",
            "trends_vs",
            "followers_per",
            "news_per",
        )
    ):
        return "velocity"
    return "proof"


def _shap_to_display(x: float, scale: float = 2.5) -> float:
    return float(max(0.0, min(100.0, 50.0 + 50.0 * np.tanh(x / scale))))


def group_shap_by_component(shap_vec: np.ndarray) -> dict[ComponentName, float]:
    if shap_vec.shape[-1] != N_FEATURE_COLUMNS:
        raise ValueError(f"Expected {N_FEATURE_COLUMNS} SHAP dims")
    sums: dict[ComponentName, float] = {
        "brand": 0.0,
        "proof": 0.0,
        "proximity": 0.0,
        "velocity": 0.0,
        "risk": 0.0,
    }
    for i, name in enumerate(FEATURE_NAMES):
        sums[_route_feature(name)] += float(shap_vec[i])
    return sums


def component_scores_0_100(sums: dict[ComponentName, float]) -> dict[ComponentName, float]:
    return {k: _shap_to_display(v) for k, v in sums.items()}


def weighted_gravity_from_components(
    comp: dict[ComponentName, float],
) -> float:
    """Interpretability blend (not necessarily equal to network forward pass)."""
    b = comp["brand"]
    p = comp["proof"]
    x = comp["proximity"]
    v = comp["velocity"]
    r = comp["risk"]
    raw = 0.25 * b + 0.25 * p + 0.20 * x + 0.15 * v - 0.15 * r
    return float(max(0.0, min(100.0, raw)))


def top_shap_features(
    shap_vec: np.ndarray,
    k: int = 6,
) -> list[tuple[str, float]]:
    idx = np.argsort(-np.abs(shap_vec))[:k]
    return [(FEATURE_NAMES[int(i)], float(shap_vec[int(i)])) for i in idx]


def deep_shap_values(
    model: GravityNet,
    X_background: np.ndarray,
    X_explain: np.ndarray,
    device: str = "cpu",
) -> np.ndarray:
    """DeepSHAP-style attributions via SHAP GradientExplainer."""
    import shap  # lazy: heavy import

    model = model.to(device)
    model.eval()
    bg = torch.tensor(X_background, dtype=torch.float32, device=device)
    ex = torch.tensor(X_explain, dtype=torch.float32, device=device)

    explainer = shap.GradientExplainer(model, bg)
    sv = explainer.shap_values(ex)
    if isinstance(sv, list):
        sv = sv[0]
    return np.asarray(sv, dtype=np.float64).reshape(X_explain.shape[0], N_FEATURE_COLUMNS)


__all__ = [
    "ComponentName",
    "component_scores_0_100",
    "deep_shap_values",
    "group_shap_by_component",
    "top_shap_features",
    "weighted_gravity_from_components",
    "_route_feature",
]
