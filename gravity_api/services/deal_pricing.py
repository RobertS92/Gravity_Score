"""Scientific deal-pricing guidance for NIL activations.

This module intentionally separates an athlete's annual NIL market benchmark
from transaction-level deal guidance. Public/annual NIL valuations are useful
anchors, but a brand should not treat them as the price for a single campaign.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median
from typing import Any, Mapping, Sequence


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out > 0 else None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _position_activation_share(sport: str | None, position_group: str | None) -> float:
    """Base share of annual NIL benchmark for a standard 4-6 week campaign."""
    sport_u = (sport or "").upper()
    pos_u = (position_group or "").upper()
    if sport_u == "CFB" and pos_u == "QB":
        return 0.020
    if sport_u == "CFB" and pos_u in {"WR", "RB", "TE"}:
        return 0.015
    if sport_u == "CFB":
        return 0.010
    if sport_u in {"MBB", "NCAAB"} and pos_u in {"GUARD", "G", "WING"}:
        return 0.016
    if sport_u in {"WBB", "NCAAW"}:
        return 0.017
    return 0.012


def _signal_multiplier(
    *,
    brand_score: float | None,
    proof_score: float | None,
    exposure_score: float | None,
    velocity_score: float | None,
    risk_score: float | None,
) -> float:
    """Commercial-strength multiplier centered around 1.0.

    Scores are expected on a 0-100 scale. Risk is inverted: high risk reduces
    executable deal price even when audience value is high.
    """
    brand = _clamp((brand_score or 50.0) / 100.0, 0.0, 1.0)
    proof = _clamp((proof_score or 50.0) / 100.0, 0.0, 1.0)
    exposure = _clamp((exposure_score or 50.0) / 100.0, 0.0, 1.0)
    velocity = _clamp((velocity_score or 50.0) / 100.0, 0.0, 1.0)
    risk = _clamp((risk_score or 35.0) / 100.0, 0.0, 1.0)
    commercial = 0.34 * brand + 0.23 * proof + 0.23 * exposure + 0.20 * velocity
    return _clamp(0.55 + commercial - 0.35 * risk, 0.45, 1.55)


def _uncertainty_width(
    *,
    model_confidence: float | None,
    comparable_count: int,
    verified_deal_count: int,
    cohort_size: int,
    cohort_fit: str | None,
) -> tuple[float, str]:
    confidence = _clamp(model_confidence if model_confidence is not None else 0.5, 0.0, 1.0)
    evidence = 0.38 * confidence
    evidence += min(0.24, comparable_count * 0.03)
    evidence += min(0.22, verified_deal_count * 0.07)
    evidence += min(0.16, cohort_size * 0.01)
    if cohort_fit == "poor":
        evidence *= 0.72
    elif cohort_fit == "edge":
        evidence *= 0.86
    evidence = _clamp(evidence, 0.05, 0.95)
    width = _clamp(0.85 - 0.48 * evidence, 0.25, 0.80)
    if evidence >= 0.70:
        return width, "High"
    if evidence >= 0.42:
        return width, "Moderate"
    return width, "Low"


def _cohort_prior(
    annual_benchmark: float | None,
    annual_values: Sequence[float],
    base_share: float,
) -> float | None:
    values = [v for v in annual_values if v > 0]
    if not values:
        return None
    cohort_mid = median(values) * base_share
    if annual_benchmark and annual_benchmark > 0:
        athlete_anchor = annual_benchmark * base_share
        # Keep the prior informative without letting a weak cohort crush an
        # elite outlier or inflate a developing player unrealistically.
        return _clamp(cohort_mid, athlete_anchor * 0.35, athlete_anchor * 1.45)
    return cohort_mid


@dataclass(frozen=True)
class DealPricingResult:
    annual_nil_benchmark: float | None
    activation_deal_low: float | None
    activation_deal_mid: float | None
    activation_deal_high: float | None
    season_partnership_low: float | None
    season_partnership_high: float | None
    confidence: str
    uncertainty: str
    method: str
    basis: str
    comparable_deal_count: int
    cohort_size: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def price_standard_activation(
    *,
    annual_benchmark: float | None,
    model_p50: float | None,
    cohort_stats: Mapping[str, Any],
    comparables: Sequence[Mapping[str, Any]],
    sport: str | None,
    position_group: str | None,
    brand_score: float | None,
    proof_score: float | None,
    exposure_score: float | None,
    velocity_score: float | None,
    risk_score: float | None,
    model_confidence: float | None,
    verified_deals_count: int | None,
    cohort_fit: str | None,
    market_view: str = "balanced",
) -> DealPricingResult:
    """Return campaign-level deal guidance.

    The output is for a standard 4-6 week brand activation with a modest
    deliverable bundle. It is not a full annual valuation and not a season-long
    exclusive unless the caller uses the season partnership fields.
    """
    annual = _num(annual_benchmark) or _num(model_p50)
    if annual is None:
        return DealPricingResult(
            annual_nil_benchmark=None,
            activation_deal_low=None,
            activation_deal_mid=None,
            activation_deal_high=None,
            season_partnership_low=None,
            season_partnership_high=None,
            confidence="Low",
            uncertainty="No annual benchmark available",
            method="activation_v1_log_anchor",
            basis="No usable annual NIL benchmark or model point estimate was available.",
            comparable_deal_count=0,
            cohort_size=int(cohort_stats.get("size") or 0),
        )

    base_share = _position_activation_share(sport, position_group)
    if market_view == "conservative":
        base_share *= 0.82
    elif market_view == "aggressive":
        base_share *= 1.18

    signal_mult = _signal_multiplier(
        brand_score=brand_score,
        proof_score=proof_score,
        exposure_score=exposure_score,
        velocity_score=velocity_score,
        risk_score=risk_score,
    )
    athlete_anchor = annual * base_share * signal_mult

    actual_deals = [
        _num(c.get("deal_value"))
        for c in comparables
        if c.get("deal_value") is not None
    ]
    actual_deals = [v for v in actual_deals if v is not None]
    comparable_annuals = [
        _num(c.get("dollar_p50_usd") or c.get("nil_valuation_consensus"))
        for c in comparables
    ]
    comparable_annuals = [v for v in comparable_annuals if v is not None]
    cohort_values = cohort_stats.get("benchmark_values") or []
    cohort_annuals = [_num(v) for v in cohort_values]
    cohort_annuals = [v for v in cohort_annuals if v is not None]

    comparable_count = len(comparables)
    verified_count = int(verified_deals_count or 0) + len(actual_deals)
    cohort_size = int(cohort_stats.get("size") or 0)
    width, confidence = _uncertainty_width(
        model_confidence=model_confidence,
        comparable_count=comparable_count,
        verified_deal_count=verified_count,
        cohort_size=cohort_size,
        cohort_fit=cohort_fit,
    )

    priors: list[float] = []
    if actual_deals:
        priors.append(median(actual_deals))
    annual_prior = _cohort_prior(annual, comparable_annuals or cohort_annuals, base_share)
    if annual_prior is not None:
        priors.append(annual_prior)
    prior_mid = median(priors) if priors else None

    evidence_weight = _clamp(
        0.28 + 0.035 * comparable_count + 0.07 * verified_count + 0.18 * (model_confidence or 0.0),
        0.25,
        0.82,
    )
    if prior_mid is None:
        mid = athlete_anchor
    else:
        mid = evidence_weight * athlete_anchor + (1.0 - evidence_weight) * prior_mid

    # Activation guidance should remain a transaction price. Cap the standard
    # activation at a sensible share of annual market value while preserving
    # a meaningful floor for developing athletes.
    max_activation = annual * (0.060 if (position_group or "").upper() == "QB" else 0.045)
    mid = _clamp(mid, 750.0, max(1_000.0, max_activation))
    low = max(500.0, mid * (1.0 - width))
    high = min(max_activation, mid * (1.0 + width * 1.15))
    if high <= low:
        high = low * 1.35

    season_low = annual * 0.070 * signal_mult
    season_high = annual * (0.220 if (position_group or "").upper() == "QB" else 0.180) * signal_mult
    season_low = max(season_low, high * 1.4)
    season_high = max(season_high, season_low * 1.35)

    basis_bits = [
        "standard 4-6 week activation",
        f"{base_share:.1%} annual-value inventory share",
        f"{confidence.lower()} confidence",
    ]
    if actual_deals:
        basis_bits.append(f"{len(actual_deals)} comparable verified deal values")
    elif comparable_count:
        basis_bits.append(f"{comparable_count} comparable annual-value proxies")
    else:
        basis_bits.append("cohort/model prior only")

    return DealPricingResult(
        annual_nil_benchmark=round(annual, 2),
        activation_deal_low=round(low, 2),
        activation_deal_mid=round(mid, 2),
        activation_deal_high=round(high, 2),
        season_partnership_low=round(season_low, 2),
        season_partnership_high=round(season_high, 2),
        confidence=confidence,
        uncertainty=f"{confidence} confidence; interval width reflects comparable depth, verified deals, cohort fit, and model confidence.",
        method="activation_v1_log_anchor_bayesian_shrinkage",
        basis="; ".join(basis_bits),
        comparable_deal_count=len(actual_deals),
        cohort_size=cohort_size,
    )
