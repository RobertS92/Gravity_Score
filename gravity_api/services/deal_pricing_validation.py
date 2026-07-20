"""Reproducible external stress-test metrics for deal-pricing outputs."""

from __future__ import annotations

from statistics import mean, median
from typing import Any, Mapping, Sequence

from gravity_api.services.deal_pricing import price_standard_activation


SIGNAL_PROFILES: dict[str, dict[str, float]] = {
    "baseline": {
        "brand_score": 70.0,
        "proof_score": 70.0,
        "exposure_score": 70.0,
        "velocity_score": 65.0,
        "risk_score": 20.0,
        "model_confidence": 0.60,
    },
    "aggressive": {
        "brand_score": 95.0,
        "proof_score": 95.0,
        "exposure_score": 95.0,
        "velocity_score": 95.0,
        "risk_score": 5.0,
        "model_confidence": 0.85,
    },
}


def evaluate_public_collective_panel(
    cases: Sequence[Mapping[str, Any]], *, profile: str = "baseline"
) -> dict[str, Any]:
    """Compare reported roster/collective packages with season guidance.

    This intentionally does not call the result a verified backtest. The public
    fixture contains media-reported estimates and current external valuations.
    Its purpose is to detect scope/calibration failures outside synthetic tests.
    """
    if profile not in SIGNAL_PROFILES:
        raise ValueError(f"unknown signal profile: {profile}")
    signals = SIGNAL_PROFILES[profile]
    rows: list[dict[str, Any]] = []

    for case in cases:
        result = price_standard_activation(
            annual_benchmark=float(case["annual_valuation_usd"]),
            model_p50=None,
            cohort_stats={},
            comparables=[],
            sport=str(case["sport"]),
            position_group=str(case["position_group"]),
            brand_score=signals["brand_score"],
            proof_score=signals["proof_score"],
            exposure_score=signals["exposure_score"],
            velocity_score=signals["velocity_score"],
            risk_score=signals["risk_score"],
            model_confidence=signals["model_confidence"],
            verified_deals_count=0,
            cohort_fit="poor",
            market_view="aggressive" if profile == "aggressive" else "balanced",
        )
        predicted_low = float(result.season_partnership_low or 0.0)
        predicted_high = float(result.season_partnership_high or 0.0)
        reported_low = float(case["reported_low_usd"])
        reported_high = float(case["reported_high_usd"])
        predicted_mid = (predicted_low + predicted_high) / 2.0
        reported_mid = (reported_low + reported_high) / 2.0
        overlaps = predicted_low <= reported_high and reported_low <= predicted_high
        signed_error = (predicted_mid - reported_mid) / reported_mid
        rows.append(
            {
                "athlete": str(case["athlete"]),
                "sport": str(case["sport"]),
                "position_group": str(case["position_group"]),
                "annual_valuation_usd": float(case["annual_valuation_usd"]),
                "reported_low_usd": reported_low,
                "reported_high_usd": reported_high,
                "predicted_low_usd": predicted_low,
                "predicted_high_usd": predicted_high,
                "overlaps": overlaps,
                "midpoint_absolute_percentage_error": abs(signed_error),
                "midpoint_signed_percentage_error": signed_error,
            }
        )

    qb_rows = [row for row in rows if row["position_group"] == "QB"]
    covered = sum(bool(row["overlaps"]) for row in rows)
    qb_covered = sum(bool(row["overlaps"]) for row in qb_rows)
    absolute_errors = [float(row["midpoint_absolute_percentage_error"]) for row in rows]
    signed_errors = [float(row["midpoint_signed_percentage_error"]) for row in rows]
    return {
        "profile": profile,
        "n": len(rows),
        "qb_n": len(qb_rows),
        "covered_n": covered,
        "coverage": covered / len(rows) if rows else 0.0,
        "qb_covered_n": qb_covered,
        "qb_coverage": qb_covered / len(qb_rows) if qb_rows else 0.0,
        "median_absolute_percentage_error": median(absolute_errors) if rows else None,
        "mean_absolute_percentage_error": mean(absolute_errors) if rows else None,
        "median_signed_percentage_error": median(signed_errors) if rows else None,
        "rows": rows,
    }
