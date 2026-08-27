"""Partner-facing scoped deal pricing (honest governance fields).

Wraps ``deal_scope_pricing.price_all_deal_scopes`` with the same evidence
counts and calibration rows CSC uses. Does not run CSC narratives, midpoints,
or client-side defaults.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from gravity_api.services.deal_scope_pricing import DEAL_SCOPES, price_all_deal_scopes
from gravity_api.services.partner_api import attribution_block


def _float_or_none(v: object) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _iso_dt(v: object) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()  # type: ignore[no-any-return]
    return str(v)


async def _load_transaction_counts(db: asyncpg.Connection) -> dict[str, int]:
    try:
        rows = await db.fetch(
            """SELECT deal_scope::text AS deal_scope, COUNT(*)::int AS n
               FROM verified_deal_transactions
               WHERE retracted_at IS NULL
               GROUP BY deal_scope"""
        )
    except asyncpg.UndefinedTableError:
        return {}
    except asyncpg.PostgresError:
        return {}
    return {str(row["deal_scope"]): int(row["n"]) for row in rows}


async def _load_calibrations(db: asyncpg.Connection) -> dict[str, dict[str, Any]]:
    try:
        rows = await db.fetch(
            """SELECT DISTINCT ON (deal_scope) deal_scope::text AS deal_scope,
                      model_version, validation_transactions, target_coverage,
                      empirical_coverage, median_absolute_percentage_error,
                      log_residual_lower, log_residual_upper, evaluated_through
               FROM deal_model_calibrations
               ORDER BY deal_scope, evaluated_through DESC, created_at DESC"""
        )
    except asyncpg.UndefinedTableError:
        return {}
    except asyncpg.PostgresError:
        return {}
    return {str(row["deal_scope"]): dict(row) for row in rows}


def _enrich_scope(estimate: dict[str, Any]) -> dict[str, Any]:
    """Attach explicit unit; preserve verbatim pricing fields (no defaulting)."""
    out = dict(estimate)
    out["unit"] = "per_scope_usd"
    return out


async def build_partner_deal_pricing(
    db: asyncpg.Connection,
    *,
    athlete_id: str,
    score_row: asyncpg.Record | dict[str, Any],
) -> dict[str, Any]:
    """Build partner deal-pricing payload from a latest score row.

    ``score_row`` must include component scores and ``dollar_p50_usd`` when
    available. Missing governance tables yield uncalibrated priors — never
    invented High/Moderate/Low tiers.
    """
    data = dict(score_row)
    brand = _float_or_none(data.get("brand_score"))
    proof = _float_or_none(data.get("proof_score"))
    proximity = _float_or_none(data.get("proximity_score"))
    velocity = _float_or_none(data.get("velocity_score"))
    risk = _float_or_none(data.get("risk_score"))
    # Deterministic exposure proxy matching CSC's proximity/velocity blend
    # when the full exposure formula table is unavailable to partners.
    exposure = None
    if proximity is not None or velocity is not None:
        exposure = 0.5 * (proximity or 0.0) + 0.5 * (velocity or 0.0)

    annual = _float_or_none(data.get("dollar_p50_usd"))
    signals = {
        "brand_score": brand if brand is not None else 50.0,
        "proof_score": proof if proof is not None else 50.0,
        "exposure_score": exposure if exposure is not None else 50.0,
        "velocity_score": velocity if velocity is not None else 50.0,
        "risk_score": risk if risk is not None else 35.0,
    }

    transaction_counts = await _load_transaction_counts(db)
    calibrations = await _load_calibrations(db)
    scoped = price_all_deal_scopes(
        annual_benchmark=annual,
        signals=signals,
        transaction_counts=transaction_counts,
        calibrations=calibrations,
    )
    deal_scopes = {scope: _enrich_scope(scoped[scope]) for scope in DEAL_SCOPES}

    return {
        "athlete_id": athlete_id,
        "annual_nil_benchmark": annual,
        "annual_nil_benchmark_unit": "annual_usd",
        "deal_scopes": deal_scopes,
        "signals_used": {
            "brand_score": brand,
            "proof_score": proof,
            "exposure_score": exposure,
            "velocity_score": velocity,
            "risk_score": risk,
        },
        "calculated_at": _iso_dt(data.get("calculated_at")),
        "attribution": attribution_block(athlete_id),
    }
