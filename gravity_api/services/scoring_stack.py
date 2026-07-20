"""Four-tier scoring stack orchestration and metadata."""

from __future__ import annotations

import os
from typing import Any

from gravity_api.feature_engineering.types import AthleteFeatureSnapshot
from gravity_api.services.commercial_viability import COLLEGE_COMMERCIAL_SPORTS
from gravity_api.services.global_scores import calibrate_global_commercial_score
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


def _uses_commercial_ml(score_data: dict[str, Any]) -> bool:
    """True when Gravity was produced by a non-rank-only commercial value ML bundle."""
    if score_data.get("fallback_used"):
        return False
    dc = score_data.get("dollar_confidence") or {}
    if str(dc.get("quality") or "") == "beta_rank_only":
        return False
    if str(score_data.get("gravity_source") or "") == "commercial_ml":
        return True
    mv = str(score_data.get("model_version") or "").lower()
    if "heuristic" in mv or "composite" in mv:
        return False
    # Champion commercial ML (NFL/NBA) sets fallback_used=False and emits dollar bands.
    return score_data.get("dollar_p50_usd") is not None and not score_data.get("fallback_used")


def overlay_commercial_viability(
    score_data: dict[str, Any],
    raw: dict[str, Any],
    commercial_viability: dict[str, Any] | None,
    sport: str,
) -> dict[str, Any]:
    """Attach CV fields; for college, promote CV → Gravity when commercial ML is unavailable.

    Gravity Score = commercial/market value. College sports without a production
    commercial champion use commercial_viability_score as G (not BPXVR blend).
    """
    if sport not in COLLEGE_COMMERCIAL_SPORTS or not commercial_viability:
        out = dict(score_data)
        dc = dict(out.get("dollar_confidence") or {})
        dc.setdefault("score_objective", "commercial")
        if not dc.get("gravity_source"):
            dc["gravity_source"] = (
                "commercial_ml" if _uses_commercial_ml(out) else "commercial_bpxvr"
            )
        out["dollar_confidence"] = dc
        out.setdefault("score_objective", "commercial")
        out.setdefault("gravity_source", dc["gravity_source"])
        return out

    out = dict(score_data)
    dc = dict(out.get("dollar_confidence") or {})
    cv_score = commercial_viability.get("commercial_viability_score")
    dc["commercial_viability_score"] = cv_score
    dc["commercial_viability_index"] = commercial_viability.get("commercial_viability_index")
    dc["commercial_viability_percentile"] = commercial_viability.get("commercial_viability_percentile")
    dc["commercial_nil_market_floor"] = commercial_viability.get("commercial_nil_market_floor")
    dc["nil_signal_source"] = commercial_viability.get("nil_signal_source")
    dc["score_objective"] = "commercial"

    if not _uses_commercial_ml(out) and cv_score is not None:
        # College commercial Gravity: CV percentile is the display score.
        out["gravity_score"] = float(cv_score)
        dc["gravity_source"] = "commercial_viability"
        out["gravity_source"] = "commercial_viability"
        out["score_tier"] = 2
        out["fallback_kind"] = "commercial_viability"
        # Prefer CV NIL bands when ML suppressed dollars (rank-only) or omitted them.
        if not out.get("dollar_p50_usd") or str(dc.get("quality") or "") == "beta_rank_only":
            out["dollar_p10_usd"] = commercial_viability.get("nil_dollar_p10")
            out["dollar_p50_usd"] = commercial_viability.get("nil_dollar_p50")
            out["dollar_p90_usd"] = commercial_viability.get("nil_dollar_p90")
            dc["quality"] = (
                "moderate"
                if commercial_viability.get("nil_signal_source") == "observed"
                else "low"
            )
            dc["source"] = commercial_viability.get("nil_signal_source") or "commercial_viability"
    else:
        dc["gravity_source"] = "commercial_ml" if _uses_commercial_ml(out) else dc.get(
            "gravity_source", "commercial_bpxvr"
        )
        out.setdefault("gravity_source", dc["gravity_source"])
        if not out.get("dollar_p50_usd"):
            out["dollar_p10_usd"] = commercial_viability.get("nil_dollar_p10")
            out["dollar_p50_usd"] = commercial_viability.get("nil_dollar_p50")
            out["dollar_p90_usd"] = commercial_viability.get("nil_dollar_p90")

    out["dollar_confidence"] = dc
    out.setdefault("score_objective", "commercial")
    return out


def finalize_score_metadata(
    score_data: dict[str, Any],
    *,
    raw: dict[str, Any] | None = None,
    sport: str | None = None,
) -> dict[str, Any]:
    out = dict(score_data)
    if raw is not None and sport and out.get("gravity_source") != "commercial_viability":
        global_score, calibration = calibrate_global_commercial_score(out, raw, sport)
        out["gravity_score"] = global_score
        out["global_commercial_calibration"] = calibration
    out["score_tier"] = classify_score_tier(out)
    out.setdefault("score_objective", "commercial")
    dc = dict(out.get("dollar_confidence") or {})
    dc.setdefault("score_objective", "commercial")
    if out.get("global_commercial_calibration"):
        dc["global_commercial_calibration"] = out["global_commercial_calibration"]
    if not out.get("gravity_source"):
        if _uses_commercial_ml(out):
            out["gravity_source"] = "commercial_ml"
        elif "heuristic" in str(out.get("model_version") or "").lower():
            out["gravity_source"] = "commercial_bpxvr"
        else:
            out["gravity_source"] = dc.get("gravity_source") or "commercial_bpxvr"
    dc.setdefault("gravity_source", out["gravity_source"])
    out["dollar_confidence"] = dc
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
