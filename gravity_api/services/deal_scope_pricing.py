"""Scope-specific NIL pricing with evidence-gated uncertainty.

The functions in this module are intentionally deterministic priors until a
scope has a sufficiently large, out-of-time calibration record.  A prior may
be useful planning guidance; it must never be presented as calibrated.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping

DealScope = Literal[
    "standard_activation",
    "season_partnership",
    "collective_package",
    "group_licensing",
    "revenue_sharing",
]

DEAL_SCOPES: tuple[DealScope, ...] = (
    "standard_activation",
    "season_partnership",
    "collective_package",
    "group_licensing",
    "revenue_sharing",
)

SCOPE_LABELS: dict[DealScope, str] = {
    "standard_activation": "Standard activation",
    "season_partnership": "Season partnership",
    "collective_package": "Collective package",
    "group_licensing": "Group licensing",
    "revenue_sharing": "Revenue sharing",
}


@dataclass(frozen=True)
class ScopePrior:
    model_version: str
    annual_share: float
    floor_usd: float
    prior_low_multiplier: float
    prior_high_multiplier: float
    description: str


# Separate, versioned models. These are not aliases for the activation model.
# Each has its own commercial unit, annual share, floor, and uncertainty prior.
SCOPE_MODELS: dict[DealScope, ScopePrior] = {
    "standard_activation": ScopePrior(
        "activation_prior_v2", 0.016, 500, 0.48, 1.75,
        "one 4-6 week activation with a modest deliverable bundle",
    ),
    "season_partnership": ScopePrior(
        "season_prior_v1", 0.135, 2_500, 0.52, 1.70,
        "multi-month individual partnership across one college season",
    ),
    "collective_package": ScopePrior(
        "collective_prior_v1", 0.42, 5_000, 0.42, 1.95,
        "collective or roster-support package; not a brand activation",
    ),
    "group_licensing": ScopePrior(
        "group_license_prior_v1", 0.055, 750, 0.35, 2.10,
        "athlete allocation from a multi-athlete licensing program",
    ),
    "revenue_sharing": ScopePrior(
        "revenue_share_prior_v1", 0.30, 5_000, 0.45, 1.90,
        "athlete allocation from institutional revenue sharing",
    ),
}


@dataclass(frozen=True)
class ScopedDealEstimate:
    scope: DealScope
    label: str
    low: float | None
    mid: float | None
    high: float | None
    model_version: str
    calibrated: bool
    confidence: str
    basis: str
    qualified_transactions: int
    validation_transactions: int
    empirical_coverage: float | None
    target_coverage: float | None
    median_absolute_percentage_error: float | None
    evaluated_through: str | None
    readiness: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result > 0 else None


def _metric(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _commercial_multiplier(signals: Mapping[str, Any]) -> float:
    brand = min(1.0, max(0.0, float(signals.get("brand_score") or 50) / 100))
    proof = min(1.0, max(0.0, float(signals.get("proof_score") or 50) / 100))
    exposure = min(1.0, max(0.0, float(signals.get("exposure_score") or 50) / 100))
    velocity = min(1.0, max(0.0, float(signals.get("velocity_score") or 50) / 100))
    risk = min(1.0, max(0.0, float(signals.get("risk_score") or 35) / 100))
    return min(1.55, max(0.45, 0.55 + .34 * brand + .23 * proof + .23 * exposure + .20 * velocity - .35 * risk))


def _confidence_from_error(mape: float | None, coverage: float | None, target: float | None) -> str:
    """Confidence is exclusively a summary of held-out historical error."""
    if mape is None or coverage is None or target is None:
        return "Uncalibrated"
    coverage_gap = max(0.0, target - coverage)
    if mape <= 0.25 and coverage_gap <= 0.03:
        return "High"
    if mape <= 0.50 and coverage_gap <= 0.08:
        return "Moderate"
    return "Low"


def price_deal_scope(
    scope: DealScope,
    *,
    annual_benchmark: float | None,
    signals: Mapping[str, Any],
    qualified_transactions: int = 0,
    calibration: Mapping[str, Any] | None = None,
) -> ScopedDealEstimate:
    prior = SCOPE_MODELS[scope]
    annual = _number(annual_benchmark)
    calibration = calibration or {}
    validation_n = int(calibration.get("validation_transactions") or 0)
    # 100 qualified labels is the minimum pilot gate. 300 is the preferred
    # production evidence level. Calibration also needs >=20 out-of-time rows.
    calibrated = bool(qualified_transactions >= 100 and validation_n >= 20)
    readiness = "production" if qualified_transactions >= 300 and calibrated else "pilot" if calibrated else "insufficient_data"

    if annual is None:
        low = mid = high = None
    else:
        mid = max(prior.floor_usd, annual * prior.annual_share * _commercial_multiplier(signals))
        if calibrated:
            # Residuals are observed log(actual / predicted) quantiles from an
            # out-of-time, athlete-purged calibration set.
            low = mid * math.exp(float(calibration["log_residual_lower"]))
            high = mid * math.exp(float(calibration["log_residual_upper"]))
        else:
            low = mid * prior.prior_low_multiplier
            high = mid * prior.prior_high_multiplier
        low, mid, high = round(low, 2), round(mid, 2), round(high, 2)

    empirical = _metric(calibration.get("empirical_coverage"))
    target = _metric(calibration.get("target_coverage"))
    mape = _metric(calibration.get("median_absolute_percentage_error"))
    confidence = _confidence_from_error(mape, empirical, target) if calibrated else "Uncalibrated"
    basis = (
        f"{prior.description}; {qualified_transactions} qualified {scope.replace('_', ' ')} transactions. "
        + (
            f"Interval calibrated on {validation_n} later transactions with {empirical:.0%} measured coverage."
            if calibrated and empirical is not None
            else "Prior interval only; measured confidence is withheld until at least 100 qualified transactions and 20 out-of-time validation outcomes exist."
        )
    )
    return ScopedDealEstimate(
        scope=scope,
        label=SCOPE_LABELS[scope],
        low=low,
        mid=mid,
        high=high,
        model_version=prior.model_version,
        calibrated=calibrated,
        confidence=confidence,
        basis=basis,
        qualified_transactions=qualified_transactions,
        validation_transactions=validation_n,
        empirical_coverage=empirical,
        target_coverage=target,
        median_absolute_percentage_error=mape,
        evaluated_through=str(calibration.get("evaluated_through")) if calibration.get("evaluated_through") else None,
        readiness=readiness,
    )


def price_all_deal_scopes(
    *,
    annual_benchmark: float | None,
    signals: Mapping[str, Any],
    transaction_counts: Mapping[str, int] | None = None,
    calibrations: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    counts = transaction_counts or {}
    calibration_map = calibrations or {}
    return {
        scope: price_deal_scope(
            scope,
            annual_benchmark=annual_benchmark,
            signals=signals,
            qualified_transactions=int(counts.get(scope) or 0),
            calibration=calibration_map.get(scope),
        ).to_dict()
        for scope in DEAL_SCOPES
    }
