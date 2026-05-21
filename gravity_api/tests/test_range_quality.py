"""Range-quality sanity checks for the CSC report builder."""

from __future__ import annotations

from gravity_api.services.csc_report_builder import (
    range_incoherent_with_benchmark,
    validate_range,
)


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


# ---------------------------------------------------------------------------
# range_incoherent_with_benchmark — catches benchmark/range mismatch like
# the Arch Manning $21.9M headline with a $4.5M-$4.6M model band.
# ---------------------------------------------------------------------------


def test_incoherent_when_range_entirely_below_benchmark():
    """$21.9M benchmark with $4.5M-$4.6M model band → incoherent."""
    assert (
        range_incoherent_with_benchmark(21_900_000, 4_500_000, 4_600_000)
        is True
    )


def test_incoherent_when_range_entirely_above_benchmark():
    """Defensive — never seen in production but should still flag."""
    assert (
        range_incoherent_with_benchmark(100_000, 500_000, 600_000) is True
    )


def test_incoherent_when_band_collapsed_around_benchmark():
    """Model P10/P90 within 5% of each other → collapsed band, useless range."""
    # Benchmark $1M, range $999K-$1.001K (width 0.2% of benchmark).
    assert (
        range_incoherent_with_benchmark(1_000_000, 999_000, 1_001_000)
        is True
    )


def test_coherent_when_band_brackets_benchmark_normally():
    """$1M benchmark with $700K-$1.4M band — normal, do not re-snap."""
    assert (
        range_incoherent_with_benchmark(1_000_000, 700_000, 1_400_000)
        is False
    )


def test_coherent_when_benchmark_or_endpoints_missing():
    assert range_incoherent_with_benchmark(None, 1, 2) is False
    assert range_incoherent_with_benchmark(100_000, None, 200_000) is False
    assert range_incoherent_with_benchmark(100_000, 50_000, None) is False
    assert range_incoherent_with_benchmark(0, 50_000, 100_000) is False
