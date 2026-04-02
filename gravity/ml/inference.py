"""Load trained artifacts and score one athlete (+ SHAP + optional LLM copy)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import torch

from gravity.ml.feature_engineer import (
    CohortStats,
    N_FEATURE_COLUMNS,
    build_cohort_stats,
    engineer_row,
)
from gravity.ml.network import GravityNet
from gravity.ml.normalizer import GravityNormalizer
from gravity.ml.shap_scorer import (
    ComponentName,
    component_scores_0_100,
    deep_shap_values,
    group_shap_by_component,
    top_shap_features,
    _route_feature,
)

HeadName = Literal["default", "nil", "insurance", "agent"]


@dataclass
class GravityResult:
    gravity_score: float
    """Neural network output (0–100), primary Stage 1 ranking score."""
    component_scores: dict[ComponentName, float]
    component_shap_raw: dict[ComponentName, float]
    blended_score: float
    """Weighted sum of component display scores (explainability check)."""
    top_shap_features: list[tuple[str, float]]
    top_features_by_component: dict[ComponentName, list[str]]
    explanation: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


_HEAD_WEIGHTS: dict[HeadName, dict[str, float]] = {
    "default": {"brand": 0.25, "proof": 0.25, "proximity": 0.20, "velocity": 0.15, "risk": -0.15},
    "nil": {"brand": 0.35, "proof": 0.20, "proximity": 0.15, "velocity": 0.25, "risk": -0.15},
    "insurance": {"brand": 0.05, "proof": 0.15, "proximity": 0.15, "velocity": 0.10, "risk": -0.55},
    "agent": {"brand": 0.25, "proof": 0.25, "proximity": 0.22, "velocity": 0.18, "risk": -0.15},
}


def _head_blend(comp: dict[ComponentName, float], head: HeadName) -> float:
    w = _HEAD_WEIGHTS[head]
    s = (
        w["brand"] * comp["brand"]
        + w["proof"] * comp["proof"]
        + w["proximity"] * comp["proximity"]
        + w["velocity"] * comp["velocity"]
        + w["risk"] * comp["risk"]
    )
    return float(max(0.0, min(100.0, s)))


class GravityInference:
    def __init__(
        self,
        bundle_dir: str | Path,
        device: str | None = None,
    ) -> None:
        self.bundle_dir = Path(bundle_dir)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        ckpt = torch.load(self.bundle_dir / "gravity_v1.pt", map_location=self.device)
        self.model = GravityNet(N_FEATURE_COLUMNS).to(self.device)
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()
        self.normalizer = GravityNormalizer.load(self.bundle_dir / "normalizer_v1.pkl")
        cohort_path = self.bundle_dir / "cohort_v1.pkl"
        self.cohort: CohortStats | None
        if cohort_path.exists():
            self.cohort = joblib.load(cohort_path)
        else:
            self.cohort = None
        self._background: np.ndarray | None = None

    def set_background(self, X_norm: np.ndarray) -> None:
        """Optional: training-normalized matrix for SHAP (use ~100 rows)."""
        self._background = np.asarray(X_norm, dtype=np.float32)

    def score_athlete(
        self,
        player_dict: dict[str, Any],
        *,
        compute_shap: bool = True,
        head: HeadName = "default",
    ) -> GravityResult:
        cohort = self.cohort
        if cohort is None:
            cohort = build_cohort_stats([player_dict])

        x = engineer_row(player_dict, cohort).reshape(1, -1)
        xn = self.normalizer.transform(x)

        with torch.no_grad():
            xt = torch.tensor(xn, dtype=torch.float32, device=self.device)
            gravity = float(self.model(xt).cpu().item())

        shap_vec = np.zeros(N_FEATURE_COLUMNS, dtype=np.float64)
        if compute_shap:
            if self._background is not None:
                bg = self._background
                if len(bg) > 128:
                    idx = np.random.choice(len(bg), size=128, replace=False)
                    bg = bg[idx]
                shap_vec = deep_shap_values(self.model, bg, xn, device=self.device)[0]
            else:
                shap_vec = deep_shap_values(
                    self.model, xn, xn, device=self.device
                )[0]

        sums = group_shap_by_component(shap_vec)
        comp_display = component_scores_0_100(sums)
        blended = _head_blend(comp_display, head)
        tops = top_shap_features(shap_vec, k=8)
        by_c = self._top_names_per_component(shap_vec)

        return GravityResult(
            gravity_score=gravity,
            component_scores=comp_display,
            component_shap_raw=sums,
            blended_score=blended,
            top_shap_features=tops,
            top_features_by_component=by_c,
            meta={"head": head},
        )

    def _top_names_per_component(
        self, shap_vec: np.ndarray
    ) -> dict[ComponentName, list[str]]:
        from gravity.ml.feature_engineer import FEATURE_NAMES as FN

        buckets: dict[ComponentName, list[tuple[str, float]]] = {
            "brand": [],
            "proof": [],
            "proximity": [],
            "velocity": [],
            "risk": [],
        }
        for i, name in enumerate(FN):
            buckets[_route_feature(name)].append((name, float(shap_vec[i])))
        out: dict[ComponentName, list[str]] = {}
        for k, pairs in buckets.items():
            pairs.sort(key=lambda t: abs(t[1]), reverse=True)
            out[k] = [p[0] for p in pairs[:3]]
        return out


def score_athlete(
    player_dict: dict[str, Any],
    bundle_dir: str | Path = Path("gravity/models"),
    *,
    with_llm: bool = False,
    head: HeadName = "default",
) -> GravityResult:
    """Convenience one-shot for notebooks — loads model disk on every call."""
    g = GravityInference(bundle_dir)
    res = g.score_athlete(player_dict, head=head)
    if with_llm:
        from gravity.ml.explainer import generate_gravity_explanation

        res.explanation = generate_gravity_explanation(
            athlete_name=str(player_dict.get("player_name", "Unknown")),
            sport=str(player_dict.get("sport", "cfb")),
            team=str(player_dict.get("team", "")),
            gravity_score=res.gravity_score,
            components=res.component_scores,
            top_features_by_component=res.top_features_by_component,
        )
    return res
</think>


<｜tool▁calls▁begin｜><｜tool▁call▁begin｜>
StrReplace