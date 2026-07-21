"""Unit tests for Sports Reference search URL builder and HTML parsing (no network)."""

import urllib.parse
import builtins

from gravity_api.scrapers.parsers.sports_reference_stats import (
    extract_player_url_from_search_html,
    parse_sports_ref_stats_from_html,
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


def test_extract_player_url_from_search_html():
    html = '''
    <div class="search-item"><a href="/cfb/players/m/arch-manning-1.html">Arch Manning</a></div>
    '''
    url = extract_player_url_from_search_html("cfb", html, "Arch Manning")
    assert url == "https://www.sports-reference.com/cfb/players/m/arch-manning-1.html"


def test_parse_sports_ref_stats_from_html_table():
    html = """
    <table id="stats">
      <tr><th>G</th><th>Pass Yds</th><th>Pass TD</th></tr>
      <tr><td>12</td><td>2800</td><td>22</td></tr>
    </table>
    """
    parsed = parse_sports_ref_stats_from_html("cfb", html)
    assert parsed.get("season_stats")
    assert parsed["season_stats"]["gp"] == 12.0
    assert parsed["season_stats"]["pass_yards"] == 2800.0
    assert parsed["stats_source"] == "sports_reference"


def test_parse_sports_ref_table_without_beautifulsoup(monkeypatch):
    real_import = builtins.__import__

    def no_bs4(name, *args, **kwargs):
        if name == "bs4":
            raise ModuleNotFoundError("bs4 intentionally unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_bs4)
    parsed = parse_sports_ref_stats_from_html(
        "cfb",
        "<table id='stats'><tr><th>G</th><th>Pass Yds</th><th>Pass TD</th></tr>"
        "<tr><td>12</td><td>2800</td><td>22</td></tr></table>",
    )
    assert parsed["season_stats"] == {"gp": 12.0, "pass_yards": 2800.0, "pass_td": 22.0}
