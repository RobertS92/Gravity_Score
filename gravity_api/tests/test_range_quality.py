"""Range-quality sanity checks for the CSC report builder."""

from __future__ import annotations

from gravity_api.services.csc_report_builder import validate_range


def test_validate_range_passthrough_when_spread_within_benchmark():
    lo, hi, quality = validate_range(100_000, 80_000, 120_000)
    assert lo == 80_000
    assert hi == 120_000
    assert quality == "normal"


def test_validate_range_wide_uses_interquartile_band_when_available():
    # P10–P90 spread is $5.4M vs $4.5M benchmark — clearly wide.
    lo, hi, quality = validate_range(
        4_500_000,
        2_700_000,
        8_100_000,
        p25=3_400_000,
        p75=5_200_000,
    )
    assert quality == "wide"
    assert lo == 3_400_000
    assert hi == 5_200_000


def test_validate_range_wide_falls_back_to_symmetric_band():
    # Wide spread but no IQR available — fall back to ±30% symmetric band.
    lo, hi, quality = validate_range(4_500_000, 2_700_000, 8_100_000)
    assert quality == "wide"
    assert lo < 4_500_000 < hi
    assert hi - lo < 8_100_000 - 2_700_000


def test_validate_range_returns_normal_when_benchmark_missing():
    lo, hi, quality = validate_range(None, 10_000, 100_000)
    assert lo == 10_000
    assert hi == 100_000
    assert quality == "normal"


def test_validate_range_returns_normal_when_endpoints_missing():
    lo, hi, quality = validate_range(50_000, None, 80_000)
    assert quality == "normal"
    assert lo is None
    assert hi == 80_000


def test_validate_range_negative_benchmark_treated_as_normal():
    lo, hi, quality = validate_range(-1_000, 100, 200)
    assert quality == "normal"
