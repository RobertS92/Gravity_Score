"""Unit tests for merge_scraper_fields."""

from gravity_api.scrapers.observations import merge_scraper_fields


def test_merge_scraper_fields_preserves_season_stats_on_empty_incoming():
    base = {"season_stats": {"gp": 16, "pass_yds": 4200}, "team": "Chiefs"}
    incoming = {"season_stats": {}, "source": "espn"}
    merged = merge_scraper_fields(base, incoming)
    assert merged["season_stats"] == {"gp": 16, "pass_yds": 4200}
    assert merged["source"] == "espn"
    assert merged["team"] == "Chiefs"


def test_merge_scraper_fields_replaces_non_empty_season_stats():
    """Successful stats refresh must not keep prior-season keys stuck in raw."""
    base = {"season_stats": {"gp": 10, "pass_yds": 2000, "legacy_2023_stat": 99}}
    incoming = {"season_stats": {"gp": 16, "pass_td": 25}}
    merged = merge_scraper_fields(base, incoming)
    assert merged["season_stats"] == {"gp": 16, "pass_td": 25}
    assert "legacy_2023_stat" not in merged["season_stats"]


def test_merge_scraper_fields_history_replaces_per_year():
    base = {
        "season_stats_history": {
            "2024": {"gp": 12, "pass_yds": 3000},
            "2023": {"gp": 10, "pass_yds": 2100},
        }
    }
    incoming = {"season_stats_history": {"2024": {"gp": 13, "pass_td": 30}}}
    merged = merge_scraper_fields(base, incoming)
    assert merged["season_stats_history"]["2024"] == {"gp": 13, "pass_td": 30}
    assert merged["season_stats_history"]["2023"] == {"gp": 10, "pass_yds": 2100}


def test_merge_scraper_fields_skips_null_and_empty_strings():
    base = {"position": "QB"}
    incoming = {"position": "", "team": None, "conference": "AFC West"}
    merged = merge_scraper_fields(base, incoming)
    assert merged == {"position": "QB", "conference": "AFC West"}
