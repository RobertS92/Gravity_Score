"""Tests for calibrated Gravity composite weights."""

from __future__ import annotations

import pytest

from gravity_composite.composite import (
    CompositeWeights,
    compute_gravity_raw,
    fit_weights_nonneg_least_squares,
    get_composite_weights,
    perf_index_to_score,
    shap_from_components,
)


def test_perf_index_to_score_bounds_and_monotonic():
    assert perf_index_to_score(None) is None
    assert perf_index_to_score(0.0) == pytest.approx(50.0, abs=0.01)
    # unbounded z-sum maps into (0, 100), monotonic increasing
    seq = [perf_index_to_score(z) for z in (-3, -1, 0, 1, 3)]
    assert all(0.0 < s < 100.0 for s in seq)
    assert seq == sorted(seq)
    # an elite z-sum must clearly outscore a poor one (the old code clamped both to ~5)
    assert perf_index_to_score(2.5) - perf_index_to_score(-2.5) > 60.0


def test_all_sport_weights_sum_to_one():
    for sport in (
        "cfb",
        "ncaab_mens",
        "ncaa_baseball",
        "nfl",
        "nba",
    ):
        w = get_composite_weights(sport)
        w.validate()


def test_cfb_weights_differ_from_global():
    global_w = get_composite_weights(None)
    cfb_w = get_composite_weights("cfb")
    assert cfb_w.brand > global_w.brand
    assert cfb_w.provenance == "sport_prior_v1"


def test_compute_gravity_raw_bounds():
    g = compute_gravity_raw(
        brand=100,
        proof=100,
        proximity=100,
        velocity=100,
        risk=0,
        sport="cfb",
    )
    assert g == pytest.approx(100.0, abs=0.01)

    g_bad = compute_gravity_raw(
        brand=0,
        proof=0,
        proximity=0,
        velocity=0,
        risk=100,
        sport="cfb",
    )
    assert g_bad == pytest.approx(0.0, abs=0.01)


def test_shap_matches_weighted_components():
    w = get_composite_weights("nba")
    shap = shap_from_components(
        brand=80,
        proof=70,
        proximity=60,
        velocity=50,
        risk=20,
        weights=w,
    )
    assert shap["brand"] == pytest.approx(w.brand * 80, abs=0.0001)
    assert shap["risk"] == pytest.approx(-w.risk * 20, abs=0.0001)


def test_fit_weights_from_synthetic_rows():
    rows = []
    for i in range(40):
        b, p, x, v, r = 50 + i * 0.5, 60, 55, 45, 30
        target = 0.3 * b + 0.25 * p + 0.15 * x + 0.2 * v + 0.1 * (100 - r)
        rows.append(
            {
                "brand": b,
                "proof": p,
                "proximity": x,
                "velocity": v,
                "risk": r,
                "target": target,
            }
        )
    fitted = fit_weights_nonneg_least_squares(rows)
    fitted.validate()
    assert fitted.provenance == "empirical_nnls_v1"


def test_fit_requires_minimum_rows():
    with pytest.raises(ValueError, match="30"):
        fit_weights_nonneg_least_squares([{"brand": 1, "proof": 1, "proximity": 1, "velocity": 1, "risk": 1, "target": 1}] * 10)
