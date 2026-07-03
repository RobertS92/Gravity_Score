"""Cohort-relative gravity display calibration (latent → consumer score)."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from gravity_composite.calibration import (
    calibrate_display_score,
    cohort_percentile,
    interpolate_calibration,
    load_calibration_config,
    load_calibration_knots,
)
from gravity_composite.composite import compute_gravity_raw
from gravity_api.services.nil_valuation import elite_signal_strength, nil_from_row

COLLEGE_SPORTS = frozenset(
    {"cfb", "ncaab_mens", "ncaab_womens", "ncaa_baseball", "ncaa_volleyball"}
)


def compute_latent_gravity(
    brand: float,
    proof: float,
    proximity: float,
    velocity: float,
    risk: float,
    sport: str | None,
) -> float:
    """Rank-preserving raw BPXVR composite; not displayed directly."""
    return compute_gravity_raw(
        brand=brand,
        proof=proof,
        proximity=proximity,
        velocity=velocity,
        risk=risk,
        sport=sport,
    )


def _interpolate_log_nil_floor(log1p_usd: float, knots: Sequence[Mapping[str, float]]) -> float:
    x = float(log1p_usd)
    sorted_knots = sorted(knots, key=lambda k: float(k["log1p_usd"]))
    if x <= float(sorted_knots[0]["log1p_usd"]):
        return float(sorted_knots[0]["score"])
    if x >= float(sorted_knots[-1]["log1p_usd"]):
        return float(sorted_knots[-1]["score"])
    for i in range(len(sorted_knots) - 1):
        k0, k1 = sorted_knots[i], sorted_knots[i + 1]
        x0, x1 = float(k0["log1p_usd"]), float(k1["log1p_usd"])
        if x <= x1:
            if x1 <= x0:
                return float(k1["score"])
            t = (x - x0) / (x1 - x0)
            return float(k0["score"]) + t * (float(k1["score"]) - float(k0["score"]))
    return float(sorted_knots[-1]["score"])


def _nil_display_floor(raw: Mapping[str, Any] | None, sport: str) -> float | None:
    if raw is None:
        return None
    sport_key = sport.lower()
    cfg = load_calibration_config().get("nil_anchor") or {}
    college = set(cfg.get("college_sports") or COLLEGE_SPORTS)
    if sport_key not in college:
        return None
    if int(float(raw.get("nil_valuation_observed") or 0)) != 1:
        return None
    nil_usd = nil_from_row(raw) or raw.get("nil_valuation")
    if nil_usd is None:
        return None
    try:
        nil_val = float(nil_usd)
    except (TypeError, ValueError):
        return None
    if nil_val <= 0:
        return None
    log_knots = cfg.get("log_nil_knots") or []
    if not log_knots:
        return None
    nil_floor = _interpolate_log_nil_floor(math.log1p(nil_val), log_knots)
    elite = elite_signal_strength(raw)
    w_min = float(cfg.get("elite_weight_min", 0.55))
    w_max = float(cfg.get("elite_weight_max", 1.0))
    elite_weight = w_min + (w_max - w_min) * elite
    return nil_floor * elite_weight


def calibrate_gravity_score(
    latent: float,
    cohort_latents: Sequence[float] | None,
    sport: str,
    raw: Mapping[str, Any] | None = None,
) -> tuple[float, float]:
    """Map latent G to display gravity via cohort percentile calibration."""
    calibrated, pctile = calibrate_display_score(latent, cohort_latents)
    nil_floor = _nil_display_floor(raw, sport)
    if nil_floor is not None:
        display = max(calibrated, nil_floor)
    else:
        display = calibrated
    return round(max(0.0, min(99.0, display)), 4), pctile


def apply_calibration_to_score(
    score_data: dict[str, Any],
    *,
    sport: str,
    cohort_latents: Sequence[float] | None,
    raw: Mapping[str, Any] | None = None,
    latent: float | None = None,
) -> dict[str, Any]:
    """Overlay calibrated display score onto an existing score payload."""
    out = dict(score_data)
    g_latent = latent
    if g_latent is None:
        g_latent = out.get("gravity_score_latent")
    if g_latent is None:
        g_latent = compute_latent_gravity(
            float(out.get("brand_score") or 0),
            float(out.get("proof_score") or 0),
            float(out.get("proximity_score") or 0),
            float(out.get("velocity_score") or 0),
            float(out.get("risk_score") or 0),
            sport,
        )

    display, pctile = calibrate_gravity_score(g_latent, cohort_latents, sport, raw=raw)
    out["gravity_score_latent"] = round(float(g_latent), 4)
    out["gravity_score"] = display
    out["gravity_cohort_percentile"] = pctile

    dc = dict(out.get("dollar_confidence") or {})
    dc["gravity_score_latent"] = out["gravity_score_latent"]
    dc["gravity_cohort_percentile"] = pctile
    dc["calibration_version"] = str(load_calibration_config().get("version", "1.0.0"))
    out["dollar_confidence"] = dc
    return out


__all__ = [
    "apply_calibration_to_score",
    "calibrate_gravity_score",
    "cohort_percentile",
    "compute_latent_gravity",
    "interpolate_calibration",
    "load_calibration_knots",
]
