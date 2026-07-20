"""Leakage-resistant temporal evaluation for scope-specific deal models."""

from __future__ import annotations

import math
from statistics import median
from typing import Any, Callable, Sequence


def temporal_athlete_purged_split(
    rows: Sequence[dict[str, Any]],
    *,
    test_fraction: float = 0.20,
    date_key: str = "available_at",
    athlete_key: str = "athlete_id",
    transaction_key: str = "transaction_id",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split by time, then purge identities and transactions from training.

    Every test outcome is later than the initial training window. If an athlete
    occurs in test, all of that athlete's rows are removed from train, making
    memorization of athlete identity impossible. Duplicate transaction IDs are
    rejected because they can otherwise straddle partitions under bad imports.
    """
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between 0 and 1")
    ordered = sorted((dict(row) for row in rows), key=lambda row: str(row.get(date_key) or ""))
    seen_transactions: set[str] = set()
    for row in ordered:
        transaction_id = str(row.get(transaction_key) or "").strip()
        if not transaction_id:
            raise ValueError("every row requires a transaction_id")
        if transaction_id in seen_transactions:
            raise ValueError(f"duplicate transaction_id: {transaction_id}")
        seen_transactions.add(transaction_id)
    cut = max(1, min(len(ordered) - 1, int(len(ordered) * (1 - test_fraction))))
    initial_train, test = ordered[:cut], ordered[cut:]
    test_athletes = {str(row.get(athlete_key)) for row in test}
    train = [row for row in initial_train if str(row.get(athlete_key)) not in test_athletes]
    if not train or not test:
        raise ValueError("split has no rows after athlete purge")
    if {str(r.get(athlete_key)) for r in train} & test_athletes:
        raise AssertionError("athlete leakage detected")
    return train, test


def calibrate_log_intervals(
    validation_rows: Sequence[dict[str, Any]],
    predict: Callable[[dict[str, Any]], float],
    *,
    target_coverage: float = 0.80,
    amount_key: str = "amount_usd",
) -> dict[str, float | int]:
    """Measure error and return empirical log-residual interval quantiles."""
    if not 0 < target_coverage < 1:
        raise ValueError("target_coverage must be between 0 and 1")
    residuals: list[float] = []
    apes: list[float] = []
    signed: list[float] = []
    for row in validation_rows:
        actual = float(row[amount_key])
        predicted = float(predict(dict(row)))
        if actual <= 0 or predicted <= 0 or not math.isfinite(actual + predicted):
            raise ValueError("actual and predicted values must be positive and finite")
        residuals.append(math.log(actual / predicted))
        signed_error = (predicted - actual) / actual
        signed.append(signed_error)
        apes.append(abs(signed_error))
    if len(residuals) < 20:
        raise ValueError("at least 20 out-of-time outcomes are required for calibration")
    residuals.sort()

    def quantile(q: float) -> float:
        index = (len(residuals) - 1) * q
        lo = int(index)
        hi = min(lo + 1, len(residuals) - 1)
        weight = index - lo
        return residuals[lo] * (1 - weight) + residuals[hi] * weight

    alpha = 1 - target_coverage
    lower, upper = quantile(alpha / 2), quantile(1 - alpha / 2)
    covered = sum(lower <= residual <= upper for residual in residuals)
    return {
        "validation_transactions": len(residuals),
        "target_coverage": target_coverage,
        "empirical_coverage": covered / len(residuals),
        "median_absolute_percentage_error": median(apes),
        "median_signed_percentage_error": median(signed),
        "log_residual_lower": lower,
        "log_residual_upper": upper,
    }
