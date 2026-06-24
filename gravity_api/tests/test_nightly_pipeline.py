"""Tests for nightly pipeline pooling helpers."""

from gravity_api.scrapers.orchestrator import _partition_scraper_keys


def test_partition_scraper_keys_parallel_espn():
    keys = [
        "espn_roster_nfl",
        "espn_stats_nfl",
        "college_experience_pro",
        "transfer_portal_nfl",
    ]
    parallel, serial = _partition_scraper_keys(keys, "nfl")
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
    parallel, serial = _partition_scraper_keys(keys, "cfb")
    assert "espn_stats_cfb" in parallel
    assert "cfbd_api_stats_cfb" in parallel
    assert "news_rss_on3" in serial
    assert "social_growth_delta" in serial
    assert "recruiting_247_cfb" in serial
