"""Tests for brand-heritage / family-name equity detection."""

from __future__ import annotations

from gravity_api.services.brand_heritage import (
    clear_brand_heritage_cache,
    detect_brand_heritage,
)
from gravity_api.services.csc_report_builder import build_driver_interpretation_fallback


def setup_function() -> None:
    clear_brand_heritage_cache()


def test_detects_manning_family_heritage():
    hit = detect_brand_heritage("Arch Manning", sport="CFB")
    assert hit is not None
    assert "Manning" in hit["prose_fragment"]
    assert hit["tier"] == "iconic"


def test_ignores_unrelated_surname():
    assert detect_brand_heritage("Jordan Star", sport="CFB") is None


def test_brady_requires_exact_first_name():
    assert detect_brand_heritage("Tom Brady", sport="NFL") is not None
    assert detect_brand_heritage("Sam Brady", sport="NFL") is None


def test_brand_interpretation_includes_manning_heritage():
    text = build_driver_interpretation_fallback(
        athlete_name="Arch Manning",
        label="Brand Strength",
        signal="High",
        cohort_label="SEC QBs",
        athlete_d={
            "name": "Arch Manning",
            "sport": "CFB",
            "instagram_followers": 1_200_000,
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
    assert "Manning" in text
    assert "family" in text.lower()
    assert "Instagram" in text
    assert "trust transfer" in text.lower() or "heritage" in text.lower() or "recognition" in text.lower()
