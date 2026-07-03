"""Tests for cohort-relative gravity display calibration."""

from __future__ import annotations

import numpy as np

from gravity_api.services.gravity_calibration import (
    calibrate_gravity_score,
    cohort_percentile,
    interpolate_calibration,
    load_calibration_knots,
)


def test_interpolate_calibration_monotonic():
    knots = load_calibration_knots()
    prev = -1.0
    for pct in range(0, 101):
        score = interpolate_calibration(float(pct), knots)
        assert score >= prev
        prev = score


def test_interpolate_calibration_endpoints():
    knots = load_calibration_knots()
    assert interpolate_calibration(0.0, knots) == knots[0]["score"]
    assert interpolate_calibration(100.0, knots) == knots[-1]["score"]


def test_cohort_percentile_uniform():
    latents = [float(x) for x in range(100)]
    assert cohort_percentile(0.0, latents) == 0.5
    assert cohort_percentile(99.0, latents) == 99.5
    assert cohort_percentile(50.0, latents) == 50.5


def test_uniform_latents_bucket_distribution():
    """Uniform latents → display buckets match knot design (IQR ~62-72, tail ~90+)."""
    rng = np.random.default_rng(42)
    n = 10_000
    latents = rng.uniform(20.0, 80.0, size=n).tolist()
    displays = [calibrate_gravity_score(g, latents, "cfb")[0] for g in latents]

    bucket_60_70 = sum(1 for d in displays if 60 <= d < 70)
    bucket_75_89 = sum(1 for d in displays if 75 <= d < 90)
    bucket_90_99 = sum(1 for d in displays if 90 <= d <= 99)

    pct_60_70 = 100.0 * bucket_60_70 / n
    pct_75_89 = 100.0 * bucket_75_89 / n
    pct_90_99 = 100.0 * bucket_90_99 / n

    # Uniform latents: p25-p75 → 62-72 (~50%), p85-p97 → 76-88 (~12%), p99+ → 93+ (~1%)
    assert 40 <= pct_60_70 <= 60, f"60-70 bucket {pct_60_70:.1f}%"
    assert 8 <= pct_75_89 <= 20, f"75-89 bucket {pct_75_89:.1f}%"
    assert 0.5 <= pct_90_99 <= 3.0, f"90-99 bucket {pct_90_99:.1f}%"


def test_calibrate_preserves_rank_order():
    latents = [30.0, 45.0, 60.0, 75.0, 90.0]
    cohort = latents * 20
    scores = [calibrate_gravity_score(g, cohort, "nfl")[0] for g in latents]
    assert scores == sorted(scores)


def test_nil_observed_floor_raises_display():
    cohort = [40.0] * 100 + [80.0]
    raw = {
        "nil_valuation_observed": 1,
        "nil_valuation": 15_000_000,
        "recruiting_stars": 5,
        "instagram_followers": 2_000_000,
        "google_trends_score": 85,
    }
    low_latent = 41.0
    display, _ = calibrate_gravity_score(low_latent, cohort, "cfb", raw=raw)
    without_nil, _ = calibrate_gravity_score(low_latent, cohort, "cfb", raw=None)
    assert display >= without_nil
    assert display >= 80.0
