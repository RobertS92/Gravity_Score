"""Unit tests for Sports Reference search URL builder (no network)."""

import urllib.parse

from gravity_api.scrapers.parsers.sports_reference_stats import (
    sports_ref_google_search_url,
    sports_ref_search_url,
)


def test_sports_ref_search_url_cfb_direct():
    url = sports_ref_search_url("Caleb Williams", "cfb")
    assert url == (
        "https://www.sports-reference.com/cfb/search/search.fcgi?"
        f"search={urllib.parse.quote('Caleb Williams')}"
    )


def test_sports_ref_search_url_ncaab_direct():
    url = sports_ref_search_url("Zach Edey", "ncaab_mens", "Purdue")
    assert url.startswith("https://www.sports-reference.com/cbb/search/search.fcgi?search=")
    assert "Zach" in urllib.parse.unquote(url.split("search=", 1)[1])


def test_sports_ref_search_url_nfl_direct():
    url = sports_ref_search_url("Patrick Mahomes", "nfl")
    assert url.startswith("https://www.pro-football-reference.com/search/search.fcgi?search=")


def test_sports_ref_google_fallback_for_unknown_sport():
    url = sports_ref_google_search_url("Test Athlete", "nba")
    assert url.startswith("https://www.google.com/search?q=")
    assert "basketball-reference.com" in urllib.parse.unquote(url)
