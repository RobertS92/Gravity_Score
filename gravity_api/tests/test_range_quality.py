"""Range-quality sanity checks for the CSC report builder."""

from __future__ import annotations

from gravity_api.services.csc_report_builder import (
    build_driver_interpretation_fallback,
    deal_construction_band,
    ensure_benchmark_within_range,
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
    # IQR still brackets the athlete, so it is usable.
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


def test_validate_range_wide_skips_iqr_that_excludes_benchmark():
    # Wide model band (spread > benchmark) whose peer IQR excludes the athlete.
    lo, hi, quality = validate_range(
        1_000_000,
        100_000,
        5_000_000,
        p25=200_000,
        p75=400_000,
    )
    assert quality == "wide"
    assert lo <= 1_000_000 <= hi
    # Must not keep the excluding peer IQR.
    assert not (lo == 200_000 and hi == 400_000)


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


def test_incoherent_when_benchmark_outside_otherwise_wide_band():
    assert range_incoherent_with_benchmark(2_000_000, 100_000, 500_000) is True


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


def test_ensure_benchmark_within_range_expands_low_side():
    lo, hi = ensure_benchmark_within_range(1_000_000, 1_200_000, 1_500_000)
    assert lo <= 1_000_000 <= hi


def test_ensure_benchmark_within_range_expands_high_side():
    lo, hi = ensure_benchmark_within_range(1_000_000, 400_000, 700_000)
    assert lo <= 1_000_000 <= hi


def test_deal_construction_band_brackets_point_estimate():
    lo, hi = deal_construction_band(21_900_000)
    assert lo < 21_900_000 < hi


def test_driver_interpretation_fallback_is_actionable_and_specific():
    text = build_driver_interpretation_fallback(
        athlete_name="Arch Manning",
        label="Brand Strength",
        signal="High",
        cohort_label="SEC QBs",
        athlete_d={
            "instagram_followers": 1_200_000,
            "tiktok_followers": None,
            "twitter_followers": None,
            "instagram_engagement_rate": 6.0,
            "news_mentions_30d": 22,
            "wikipedia_page_views_30d": 60_000,
            "google_trends_score": 78,
            "school": "Texas",
            "conference": "SEC",
            "position_group": "QB",
        },
        latest_dict={},
    )
    assert "Arch Manning" in text
    assert "Instagram" in text
    assert "SEC QBs" in text
    assert "Manning" in text and "family" in text.lower()
    # Must synthesize beyond Instagram-only.
    assert "news" in text.lower() or "search" in text.lower() or "Wikipedia" in text
    assert "Texas" in text or "SEC" in text
    assert "awareness" in text.lower() or "partnership" in text.lower()
    assert text != "Brand Strength leads the SEC QBs cohort."
    sentences = [s for s in text.replace("!", ".").split(".") if s.strip()]
    assert len(sentences) >= 2


def test_brand_interpretation_avoids_instagram_only_framing_when_sparse():
    """Even with IG-only owned social, call out concentration + incomplete overlays."""
    text = build_driver_interpretation_fallback(
        athlete_name="Arch Manning",
        label="Brand Strength",
        signal="High",
        cohort_label="SEC QBs",
        athlete_d={
            "instagram_followers": 1_200_000,
            "tiktok_followers": None,
            "twitter_followers": None,
            "instagram_engagement_rate": 6.0,
            "school": "Texas",
            "conference": "SEC",
        },
        latest_dict={},
    )
    assert "concentrated" in text.lower() or "owned social" in text.lower()
    assert "TikTok" in text or "X" in text
    assert "Texas" in text or "SEC" in text
