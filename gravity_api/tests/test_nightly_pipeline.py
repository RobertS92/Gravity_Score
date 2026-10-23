"""Tests for nightly pipeline pooling helpers."""

from gravity_api.scrapers.orchestrator import _partition_scraper_keys
from gravity_api.services.sport_pipeline.nightly import NIGHTLY_PIPELINE_ORDER


def test_nightly_order_roster_sync_then_hygiene_then_stats():
    """WP8: identity preamble before stats (documented stage order)."""
    assert NIGHTLY_PIPELINE_ORDER[0] == "roster_sync"
    assert NIGHTLY_PIPELINE_ORDER[1] == "roster_hygiene"
    assert NIGHTLY_PIPELINE_ORDER[2] == "stats"
    assert NIGHTLY_PIPELINE_ORDER.index("roster_sync") < NIGHTLY_PIPELINE_ORDER.index(
        "roster_hygiene"
    )
    assert NIGHTLY_PIPELINE_ORDER.index("roster_hygiene") < NIGHTLY_PIPELINE_ORDER.index(
        "stats"
    )


def test_partition_scraper_keys_parallel_espn():
    keys = [
        "espn_roster_nfl",
        "espn_stats_nfl",
        "college_experience_pro",
        "transfer_portal_nfl",
    ]
    bootstrap, parallel, serial = _partition_scraper_keys(keys, "nfl")
    assert bootstrap == []
    assert "espn_roster_nfl" in parallel
    assert "espn_stats_nfl" in parallel
    assert "college_experience_pro" in serial
    assert "transfer_portal_nfl" in serial


def test_partition_scraper_keys_db_scrapers_serial():
    keys = [
        "cfbd_api_stats_cfb",
        "news_rss_on3",
        "social_growth_delta",
        "recruiting_247_cfb",
        "espn_stats_cfb",
    ]
    bootstrap, parallel, serial = _partition_scraper_keys(keys, "cfb")
    assert bootstrap == []
    assert "espn_stats_cfb" in parallel
    assert "cfbd_api_stats_cfb" in parallel
    assert "news_rss_on3" in serial
    assert "social_growth_delta" in serial
    assert "recruiting_247_cfb" in serial
