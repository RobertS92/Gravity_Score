"""Unit tests for merge_scraper_fields."""

from gravity_api.scrapers.observations import merge_scraper_fields


def test_merge_scraper_fields_preserves_season_stats_on_empty_incoming():
    base = {"season_stats": {"gp": 16, "pass_yds": 4200}, "team": "Chiefs"}
    incoming = {"season_stats": {}, "source": "espn"}
    merged = merge_scraper_fields(base, incoming)
    assert merged["season_stats"] == {"gp": 16, "pass_yds": 4200}
    assert merged["source"] == "espn"
    assert merged["team"] == "Chiefs"


def test_merge_scraper_fields_merges_non_empty_stats():
    base = {"season_stats": {"gp": 10, "pass_yds": 2000}}
    incoming = {"season_stats": {"gp": 16, "pass_td": 25}}
    merged = merge_scraper_fields(base, incoming)
    assert merged["season_stats"] == {"gp": 16, "pass_yds": 2000, "pass_td": 25}


def test_merge_scraper_fields_skips_null_and_empty_strings():
    base = {"position": "QB"}
    incoming = {"position": "", "team": None, "conference": "AFC West"}
    merged = merge_scraper_fields(base, incoming)
    assert merged == {"position": "QB", "conference": "AFC West"}
