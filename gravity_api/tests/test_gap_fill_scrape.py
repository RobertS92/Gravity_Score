"""Tests for gap-fill scrape mode."""

from gravity_api.scraper_registry.gap_fill import analyze_field_gaps, scrapers_for_gaps
from gravity_api.scraper_registry.field_sufficiency import is_sufficient
from gravity_api.scrapers.parsers.quality_label import compute_external_quality_score
from gravity_api.scrapers.types import AthleteScrapeContext


def test_instagram_2500_placeholder_insufficient():
    raw = {"instagram_followers": 2500, "instagram_followers_observed": 1}
    assert is_sufficient(raw, "instagram_followers") is False


def test_instagram_real_observed_sufficient():
    raw = {"instagram_followers": 12500, "instagram_followers_observed": 1}
    assert is_sufficient(raw, "instagram_followers") is True


def test_instagram_bogus_observed_insufficient():
    raw = {"instagram_followers": 2, "instagram_followers_observed": 1}
    assert is_sufficient(raw, "instagram_followers") is False


def test_analyze_gaps_detects_nil_and_ig():
    raw = {"instagram_followers": 2500, "instagram_followers_observed": 1}
    gaps = analyze_field_gaps(raw)
    assert "instagram_followers" in gaps
    assert "nil_valuation" in gaps


def test_scrapers_for_gaps_includes_instagram_chain():
    keys = scrapers_for_gaps(["instagram_followers", "instagram_handle"], "cfb")
    assert any("instagram_followers" in k for k in keys)
    assert any("social_handle_discovery" in k for k in keys)


def test_external_quality_score_from_awards():
    score, parts = compute_external_quality_score(
        {"all_american_count": 2, "heisman_finalist": True}
    )
    assert score > 50
    assert "all_american" in parts


def test_nil_imputed_not_sufficient_without_observed():
    raw = {"nil_valuation": 500_000, "nil_confidence": 0.9}
    assert is_sufficient(raw, "nil_valuation") is False


def test_nil_observed_sufficient():
    raw = {
        "nil_valuation": 500_000,
        "nil_valuation_observed": 1,
        "nil_confidence": 0.9,
    }
    assert is_sufficient(raw, "nil_valuation") is True


def test_resolve_gap_fill_empty_when_sufficient():
    from gravity_api.scraper_registry.gap_fill import resolve_gap_fill_scraper_keys

    ctx = AthleteScrapeContext(
        athlete_id="a1",
        name="Test",
        sport="cfb",
        school="Alabama",
        team="Alabama",
        position="QB",
        conference="SEC",
        class_year="Junior",
        espn_id="1",
        college="Alabama",
        existing_raw={
            "instagram_handle": "qb1",
            "instagram_handle_source": "espn",
            "instagram_followers": 50000,
            "instagram_followers_observed": 1,
            "instagram_engagement_rate": 3.2,
            "nil_valuation": 500000,
            "nil_valuation_observed": 1,
            "nil_confidence": 0.9,
            "external_quality_score": 72,
            "external_quality_score_observed": 1,
        },
        league_tier="college",
    )
    assert resolve_gap_fill_scraper_keys(ctx) == []
