"""Numeric transforms for feature engineering."""

from __future__ import annotations

import math
from typing import Sequence

from gravity_api.feature_engineering.constants import PERCENTILE_CUTS
from gravity_api.feature_engineering.types import TierLabel


def log1p_safe(value: float | None) -> float | None:
    if value is None or value < 0:
        return None
    return math.log1p(value)


def winsorize(value: float, cap_low: float, cap_high: float) -> float:
    return max(cap_low, min(cap_high, value))


def z_score(value: float, mean: float, std: float) -> float:
    if std <= 0:
        return 0.0
    return (value - mean) / std


def quantile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    seq = sorted(float(v) for v in values)
    idx = (len(seq) - 1) * q
    lo = int(idx)
    hi = min(lo + 1, len(seq) - 1)
    frac = idx - lo
    return seq[lo] * (1 - frac) + seq[hi] * frac


def percentile_rank(values: Sequence[float], subject: float | None) -> float | None:
    if subject is None or not values:
        return None
    less_or_equal = sum(1 for v in values if v <= subject)
    return (less_or_equal / len(values)) * 100.0


def tier_from_percentile(pctile: float | None) -> TierLabel:
    if pctile is None:
        return TierLabel.UNKNOWN
    if pctile >= 95:
        return TierLabel.GENERATIONAL
    if pctile >= 90:
        return TierLabel.ELITE
    if pctile >= 80:
        return TierLabel.HIGH
    if pctile >= 75:
        return TierLabel.UPPER_MID
    if pctile >= 50:
        return TierLabel.MID
    if pctile >= 25:
        return TierLabel.LOWER_MID
    return TierLabel.LOW


def pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    denom = max(abs(previous), 1e-6)
    return (current - previous) / denom


def coefficient_of_variation(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    if abs(mean) < 1e-9:
        return None
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance) / abs(mean)


def baseline_distribution(values: Sequence[float]) -> dict[str, float | int | None]:
    if not values:
        return {"n": 0, "mean": None, "std": None, "p50": None, "p75": None, "p80": None, "p90": None, "p95": None, "p99": None}
    seq = [float(v) for v in values]
    n = len(seq)
    mean = sum(seq) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in seq) / n) if n > 1 else 0.0
    out: dict[str, float | int | None] = {"n": n, "mean": mean, "std": std}
    for label, q in zip(("p50", "p75", "p80", "p90", "p95", "p99"), (0.5, 0.75, 0.8, 0.9, 0.95, 0.99)):
        out[label] = quantile(seq, q)
    return out
