"""Scientific Gravity composite: G = wB·B + wP·P + wX·X + wV·V + wR·(100−R).

Weights are constrained (non-negative, sum to 1), sport-specific, and
calibratable from labeled outcomes (log NIL, CSC bands, rank targets).

See config/gravity_composite_weights.json and gravity_api/jobs/calibrate_composite_weights.py.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "gravity_composite_weights.json"


@dataclass(frozen=True)
class CompositeWeights:
    brand: float
    proof: float
    proximity: float
    velocity: float
    risk: float
    provenance: str = "global_default"
    rationale: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "brand": self.brand,
            "proof": self.proof,
            "proximity": self.proximity,
            "velocity": self.velocity,
            "risk": self.risk,
            "provenance": self.provenance,
            "rationale": self.rationale,
        }

    def validate(self, *, tol: float = 1e-5) -> None:
        for name, val in self.as_dict().items():
            if name in ("provenance", "rationale"):
                continue
            if val < -tol:
                raise ValueError(f"Weight {name} must be non-negative, got {val}")
        total = self.brand + self.proof + self.proximity + self.velocity + self.risk
        if abs(total - 1.0) > tol:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


def _load_config() -> dict[str, Any]:
    if not _CONFIG_PATH.exists():
        return {}
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


def get_composite_weights(sport: str | None = None) -> CompositeWeights:
    cfg = _load_config()
    key = (sport or "").strip().lower()
    block = (cfg.get("sports") or {}).get(key) or cfg.get("global_default") or {}
    w = CompositeWeights(
        brand=float(block.get("brand", 0.28)),
        proof=float(block.get("proof", 0.24)),
        proximity=float(block.get("proximity", 0.18)),
        velocity=float(block.get("velocity", 0.20)),
        risk=float(block.get("risk", 0.10)),
        provenance=str(block.get("provenance", "global_default")),
        rationale=str(block.get("rationale", "")),
    )
    w.validate()
    return w


def compute_gravity_raw(
    *,
    brand: float,
    proof: float,
    proximity: float,
    velocity: float,
    risk: float,
    weights: CompositeWeights | None = None,
    sport: str | None = None,
) -> float:
    """Linear composite with risk entered as downside 0–100 (higher = worse)."""
    w = weights or get_composite_weights(sport)
    g = (
        w.brand * brand
        + w.proof * proof
        + w.proximity * proximity
        + w.velocity * velocity
        + w.risk * (100.0 - risk)
    )
    return max(0.0, min(100.0, g))


def compute_gravity_confidence_weighted(
    *,
    brand: float,
    proof: float,
    proximity: float,
    velocity: float,
    risk: float,
    confidences: Mapping[str, float],
    weights: CompositeWeights | None = None,
    sport: str | None = None,
) -> float:
    """Confidence-weighted G — missing components down-weight their share."""
    w = weights or get_composite_weights(sport)
    c_b = float(confidences.get("brand", 1.0))
    c_p = float(confidences.get("proof", 1.0))
    c_x = float(confidences.get("proximity", 1.0))
    c_v = float(confidences.get("velocity", 1.0))
    c_r = float(confidences.get("risk", 1.0))

    numer = (
        w.brand * c_b * brand
        + w.proof * c_p * proof
        + w.proximity * c_x * proximity
        + w.velocity * c_v * velocity
        + w.risk * c_r * (100.0 - risk)
    )
    denom = (
        w.brand * c_b
        + w.proof * c_p
        + w.proximity * c_x
        + w.velocity * c_v
        + w.risk * c_r
    )
    if denom <= 0:
        return 0.0
    return max(0.0, min(100.0, numer / denom))


def component_confidences_from_raw(raw: dict[str, Any]) -> dict[str, float]:
    """Derive 0–1 confidences from BPXVR mask flags and data quality."""
    dqs = float(raw.get("data_quality_score") or 0.5)

    def _conf(prefix: str, fallback_keys: tuple[str, ...]) -> float:
        masked = raw.get(f"{prefix}_composite_masked")
        if masked is True:
            return 0.2
        for k in fallback_keys:
            if raw.get(k) is not None:
                return min(1.0, 0.4 + 0.6 * dqs)
        return max(0.25, 0.5 * dqs)

    return {
        "brand": _conf("brand", ("instagram_followers", "brand_social_reach_total_raw")),
        "proof": _conf(
            "proof",
            ("proof_performance_index_pctile", "proof_performance_index_raw"),
        ),
        "proximity": _conf("proximity", ("nil_valuation", "proximity_nil_valuation_raw")),
        "velocity": _conf("velocity", ("velocity_trajectory_class", "news_count_30d")),
        "risk": min(1.0, max(0.3, dqs)),
    }


def shap_from_components(
    *,
    brand: float,
    proof: float,
    proximity: float,
    velocity: float,
    risk: float,
    weights: CompositeWeights | None = None,
    sport: str | None = None,
) -> dict[str, float]:
    """Interpretable component attributions (exact linear SHAP for this composite)."""
    w = weights or get_composite_weights(sport)
    return {
        "brand": round(w.brand * brand, 4),
        "proof": round(w.proof * proof, 4),
        "proximity": round(w.proximity * proximity, 4),
        "velocity": round(w.velocity * velocity, 4),
        "risk": round(-w.risk * risk, 4),
    }


def fit_weights_nonneg_least_squares(
    rows: list[dict[str, float]],
    *,
    target_key: str = "target",
) -> CompositeWeights:
    """Fit weights via non-negative least squares then normalize to sum=1."""
    if len(rows) < 30:
        raise ValueError(f"Need at least 30 labeled rows to fit weights, got {len(rows)}")

    import numpy as np

    y = np.array([float(r[target_key]) for r in rows], dtype=float)
    X = np.array(
        [
            [
                float(r["brand"]),
                float(r["proof"]),
                float(r["proximity"]),
                float(r["velocity"]),
                100.0 - float(r["risk"]),
            ]
            for r in rows
        ],
        dtype=float,
    )
    col_mean = X.mean(axis=0)
    col_std = X.std(axis=0)
    col_std[col_std < 1e-6] = 1.0
    Xs = (X - col_mean) / col_std
    ys = (y - y.mean()) / (y.std() if y.std() > 1e-6 else 1.0)

    w_raw, _, _, _ = np.linalg.lstsq(Xs, ys, rcond=None)
    w_raw = np.maximum(w_raw, 0.0)
    if w_raw.sum() <= 0:
        w_raw = np.array([0.28, 0.24, 0.18, 0.20, 0.10])
    w_raw = w_raw / w_raw.sum()

    fitted = CompositeWeights(
        brand=float(w_raw[0]),
        proof=float(w_raw[1]),
        proximity=float(w_raw[2]),
        velocity=float(w_raw[3]),
        risk=float(w_raw[4]),
        provenance="empirical_nnls_v1",
        rationale=f"Fitted from {len(rows)} labeled rows (target={target_key})",
    )
    fitted.validate()
    return fitted


def save_sport_weights(sport: str, weights: CompositeWeights) -> None:
    cfg = _load_config()
    sports = cfg.setdefault("sports", {})
    sports[sport] = weights.as_dict()
    _CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    logger.info("Saved composite weights for %s to %s", sport, _CONFIG_PATH)
