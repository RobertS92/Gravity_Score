"""Cohort-fit classification and percentile cap tests."""

from __future__ import annotations

import pytest

from gravity_api.services.csc_report_builder import (
    cap_displayed_percentile,
    classify_cohort_fit,
)


def _stats(values: list[float]) -> dict:
    values = sorted(values)
    if not values:
        return {"size": 0}

    def _q(q: float) -> float:
        idx = (len(values) - 1) * q
        lo = int(idx)
        hi = min(lo + 1, len(values) - 1)
        frac = idx - lo
        return values[lo] * (1 - frac) + values[hi] * frac

    return {
        "size": len(values),
        "p10": _q(0.10),
        "p25": _q(0.25),
        "p50": _q(0.50),
        "p75": _q(0.75),
        "p90": _q(0.90),
        "benchmark_values": values,
    }


def test_classify_cohort_fit_returns_poor_for_small_cohort():
    assert classify_cohort_fit(50_000, _stats([10_000, 20_000])) == "poor"


def test_classify_cohort_fit_returns_good_in_middle():
    stats = _stats([10_000 * i for i in range(1, 21)])  # 10K..200K
    assert classify_cohort_fit(100_000, stats) == "good"


def test_classify_cohort_fit_returns_edge_just_above_p90():
    stats = _stats([10_000 * i for i in range(1, 21)])  # P90 ~= 190K
    # Just above P90 but not 2x.
    assert classify_cohort_fit(220_000, stats) == "edge"


def test_classify_cohort_fit_returns_poor_far_above_p90():
    stats = _stats([10_000 * i for i in range(1, 21)])
    assert classify_cohort_fit(4_500_000, stats) == "poor"


def test_classify_cohort_fit_returns_poor_far_below_p10():
    stats = _stats([10_000 * i for i in range(1, 21)])
    assert classify_cohort_fit(1_000, stats) == "poor"


def test_classify_cohort_fit_returns_good_when_benchmark_missing():
    stats = _stats([10_000 * i for i in range(1, 21)])
    assert classify_cohort_fit(None, stats) == "good"


def test_cap_displayed_percentile_passthrough():
    pct, override = cap_displayed_percentile(50.0, cohort_size=100)
    assert pct == 50.0
    assert override is None


def test_cap_displayed_percentile_floor_at_one():
    pct, override = cap_displayed_percentile(0.5, cohort_size=20)
    assert pct == 1.0
    assert override is None


@pytest.mark.parametrize("raw", [100.0, 105.0, 99.9999])
def test_cap_displayed_percentile_at_99_with_highest_text(raw):
    pct, override = cap_displayed_percentile(raw, cohort_size=317)
    if raw >= 100:
        assert pct == 99.0
        assert override == "Highest of 317 cohort athletes"
    else:
        assert pct == raw
        assert override is None


def test_cap_displayed_percentile_none_returns_none():
    pct, override = cap_displayed_percentile(None, cohort_size=10)
    assert pct is None
    assert override is None
