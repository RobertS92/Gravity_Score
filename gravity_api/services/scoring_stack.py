"""Four-tier scoring stack orchestration and metadata."""

from __future__ import annotations

import os
from typing import Any

from gravity_api.feature_engineering.types import AthleteFeatureSnapshot
from gravity_api.services.commercial_viability import COLLEGE_COMMERCIAL_SPORTS
from gravity_api.services.heuristic_gravity import compute_heuristic_gravity_v1

FLAT_CLUSTER_LO = 76.85
FLAT_CLUSTER_HI = 77.35


def fallback_scorer_name() -> str:
    return (os.environ.get("FALLBACK_SCORER") or "heuristic_gravity_v1").strip().lower()


def is_weak_ml_score(score_data: dict[str, Any]) -> bool:
    """Detect flat composite / low-confidence ML outputs worth replacing."""
    if score_data.get("fallback_used"):
        mv = str(score_data.get("model_version") or "").lower()
        if "heuristic_gravity_v1" in mv:
            return False
        return True
    mv = str(score_data.get("model_version") or "").lower()
    if "composite" in mv or "fallback" in mv:
        return True
    gs = float(score_data.get("gravity_score") or 0)
    conf = float(score_data.get("confidence") or 1.0)
    if FLAT_CLUSTER_LO <= gs <= FLAT_CLUSTER_HI and conf <= 0.75:
        return True
    return False


def classify_score_tier(score_data: dict[str, Any]) -> int:
    if score_data.get("score_tier"):
        return int(score_data["score_tier"])
    if score_data.get("fallback_used"):
        return 2
    mv = str(score_data.get("model_version") or "").lower()
    if "heuristic" in mv or "composite" in mv or "fallback" in mv:
        return 2
    return 1


def apply_tier2_fallback_if_needed(
    score_data: dict[str, Any],
    raw: dict[str, Any],
    sport: str,
    *,
    snapshot: AthleteFeatureSnapshot | None = None,
    cohort_latent_scores: list[float] | None = None,
) -> dict[str, Any]:
    """Replace weak ML composite scores with heuristic_gravity_v1."""
    if fallback_scorer_name() != "heuristic_gravity_v1":
        return score_data
    if not is_weak_ml_score(score_data):
        out = dict(score_data)
        out["score_tier"] = classify_score_tier(out)
        out.setdefault("fallback_kind", None if out["score_tier"] == 1 else "ml_composite")
        return out
    heuristic = compute_heuristic_gravity_v1(
        raw, sport, snapshot=snapshot, cohort_latent_scores=cohort_latent_scores
    )
    heuristic["model_key"] = score_data.get("model_key")
    heuristic["replaced_model_version"] = score_data.get("model_version")
    return heuristic


def overlay_commercial_viability(
    score_data: dict[str, Any],
    raw: dict[str, Any],
    commercial_viability: dict[str, Any] | None,
    sport: str,
) -> dict[str, Any]:
    """Tier 3: attach CV fields; backfill dollar bands when ML/heuristic omitted them."""
    if sport not in COLLEGE_COMMERCIAL_SPORTS or not commercial_viability:
        return score_data
    out = dict(score_data)
    dc = dict(out.get("dollar_confidence") or {})
    dc["commercial_viability_score"] = commercial_viability.get("commercial_viability_score")
    dc["commercial_viability_index"] = commercial_viability.get("commercial_viability_index")
    dc["nil_signal_source"] = commercial_viability.get("nil_signal_source")
    out["dollar_confidence"] = dc
    if not out.get("dollar_p50_usd"):
        out["dollar_p10_usd"] = commercial_viability.get("nil_dollar_p10")
        out["dollar_p50_usd"] = commercial_viability.get("nil_dollar_p50")
        out["dollar_p90_usd"] = commercial_viability.get("nil_dollar_p90")
        out.setdefault(
            "dollar_confidence",
            {
                "source": commercial_viability.get("nil_signal_source"),
                "quality": "moderate"
                if commercial_viability.get("nil_signal_source") == "observed"
                else "low",
            },
        )
    return out


def finalize_score_metadata(score_data: dict[str, Any]) -> dict[str, Any]:
    out = dict(score_data)
    out["score_tier"] = classify_score_tier(out)
    if out["score_tier"] == 1:
        out.setdefault("fallback_used", False)
        out.setdefault("fallback_kind", None)
    elif not out.get("fallback_kind"):
        out["fallback_kind"] = "heuristic_gravity_v1" if "heuristic_gravity_v1" in str(
            out.get("model_version", "")
        ) else "ml_composite"
    return out


__all__ = [
    "apply_tier2_fallback_if_needed",
    "classify_score_tier",
    "fallback_scorer_name",
    "finalize_score_metadata",
    "is_weak_ml_score",
    "overlay_commercial_viability",
]
