"""Tests for CFBD client mapping and event tier resolution."""

from __future__ import annotations

from gravity_api.scraper_registry.events import resolve_event_scraper_keys
from gravity_api.scrapers.clients.cfbd import _map_cfbd_category_row


def test_cfbd_passing_row_maps_to_canonical():
    row = {
        "category": "passing",
        "yards": 3512,
        "touchdowns": 28,
        "interceptions": 7,
        "attempts": 450,
        "completions": 290,
        "completionPct": 64.4,
        "rating": 148.2,
        "games": 12,
    }
    out = _map_cfbd_category_row(row)
    assert out["pass_yards"] == 3512.0
    assert out["pass_td"] == 28.0
    assert out["pass_int"] == 7.0
    assert out["games_played_season"] == 12.0


def test_cfbd_not_in_nfl_scheduled():
    keys = resolve_event_scraper_keys("scheduled_full", "nfl")
    assert "cfbd_api_stats_cfb" not in keys


def test_wnba_gets_spotrac_in_scheduled():
    keys = resolve_event_scraper_keys("scheduled_full", "wnba")
    assert "spotrac_contract_wnba" in keys
    assert "forbes_earnings_wnba" in keys


def test_pro_extended_blocks_college_nil():
    keys = resolve_event_scraper_keys("scheduled_full", "nfl", include_extended=True)
    assert "on3_nil_nfl" not in keys
    assert "recruiting_247_nfl" not in keys


def test_cfb_scheduled_includes_cfbd_and_news():
    keys = resolve_event_scraper_keys("scheduled_full", "cfb")
    assert "cfbd_api_stats_cfb" in keys
    assert "news_rss_on3" in keys
    assert "social_growth_delta" in keys


def test_get_scraper_impl_cfbd_and_news():
    from gravity_api.scrapers.implementations import get_scraper_impl

    assert get_scraper_impl("cfbd_api_stats_cfb") is not None
    assert get_scraper_impl("news_rss_on3") is not None
    assert get_scraper_impl("spotrac_contract_wnba") is not None
    assert get_scraper_impl("kenpom_ncaab_mens") is not None
    assert get_scraper_impl("her_hoop_stats_ncaab_womens") is not None
    assert get_scraper_impl("fantasy_adp_nfl") is not None
    assert get_scraper_impl("recruiting_247_cfb") is not None
    assert get_scraper_impl("opendorse_profile_cfb") is not None
    assert get_scraper_impl("sports_ref_honors_nfl") is not None


def test_ncaab_mens_scheduled_includes_kenpom():
    keys = resolve_event_scraper_keys("scheduled_full", "ncaab_mens")
    assert "kenpom_ncaab_mens" in keys


def test_nfl_scheduled_includes_fantasy_adp():
    keys = resolve_event_scraper_keys("scheduled_full", "nfl")
    assert "fantasy_adp_nfl" in keys


def test_kenpom_markdown_parse():
    from gravity_api.scrapers.clients.kenpom import parse_kenpom_markdown

    md = "Player stats ORtg 118.4 BPM 4.2 Usage 22.1"
    out = parse_kenpom_markdown(md)
    assert out["kenpom_rating"] == 118.4
    assert out["bpm"] == 4.2
    assert out["usage_rate"] == 22.1
