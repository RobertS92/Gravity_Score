"""Brand–athlete compatibility (mirrors gravity-ml/ml/compatibility.py for API-only deploys)."""

from __future__ import annotations

from typing import Any, Mapping


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compatibility_score(
    athlete: Mapping[str, Any],
    brand: Mapping[str, Any],
    brief: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    brief = brief or {}

    ab = float(athlete.get("brand_score") or 50)
    ap = float(athlete.get("proof_score") or 50)
    ax = float(athlete.get("proximity_score") or 50)
    av = float(athlete.get("velocity_score") or 50)
    ar = float(athlete.get("risk_score") or 50)

    comps = brand.get("components") if isinstance(brand.get("components"), dict) else None
    if comps:
        br = float(comps.get("reach", 50))
        ba = float(comps.get("authenticity", 50))
        bv = float(comps.get("value", 50))
        bf = float(comps.get("fit", 50))
        bs = float(comps.get("stability", 50))
    else:
        br = float(brand.get("reach_score") or brand.get("reach") or 50)
        ba = float(brand.get("authenticity_score") or brand.get("authenticity") or 50)
        bv = float(brand.get("value_score") or brand.get("value") or 50)
        bf = float(brand.get("fit_score") or brand.get("fit") or 50)
        bs = float(brand.get("stability_score") or brand.get("stability") or 50)

    align_brand = 1.0 - abs(ab - br) / 100.0
    align_proof = 1.0 - abs(ap - ba) / 100.0
    align_nil = 1.0 - abs(ax - bv) / 100.0
    align_momentum = 1.0 - abs(av - bf) / 100.0
    align_risk = 1.0 - abs((100.0 - ar) - bs) / 100.0

    w_brand, w_proof, w_nil, w_vel, w_risk = 0.22, 0.22, 0.22, 0.18, 0.16
    core = (
        w_brand * align_brand
        + w_proof * align_proof
        + w_nil * align_nil
        + w_vel * align_momentum
        + w_risk * align_risk
    )

    subscores: dict[str, float] = {
        "alignment_brand": round(align_brand, 4),
        "alignment_proof_authenticity": round(align_proof, 4),
        "alignment_proximity_value": round(align_nil, 4),
        "alignment_velocity_fit": round(align_momentum, 4),
        "alignment_risk_stability": round(align_risk, 4),
    }

    penalty = 0.0
    bmax = brief.get("budget_usd_max")
    p50 = athlete.get("dollar_p50_usd")
    if bmax is not None and p50 is not None:
        try:
            b = float(bmax)
            p = float(p50)
            if p > b * 1.15:
                penalty += 0.12
            elif p > b:
                penalty += 0.05
        except (TypeError, ValueError):
            pass

    cats = brief.get("target_categories")
    acat = athlete.get("primary_interest_category")
    if cats and acat and str(acat) not in [str(c) for c in cats]:
        penalty += 0.08

    states = brief.get("target_states")
    st = athlete.get("school_state") or athlete.get("home_state")
    if states and st and str(st).upper() not in {str(s).upper() for s in states}:
        penalty += 0.04

    score_100 = _clamp01(core - penalty) * 100.0
    subscores["penalty_total"] = round(penalty, 4)

    return {
        "compatibility_score": round(score_100, 2),
        "compatibility_core_0_1": round(core, 4),
        "subscores": subscores,
    }


__all__ = ["compatibility_score"]
