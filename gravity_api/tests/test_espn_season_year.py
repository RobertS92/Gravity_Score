"""Unit tests for ESPN season-year normalization (NBA/NCAAB off-by-one)."""

from __future__ import annotations

import pytest

from gravity_api.scrapers.parsers.espn_season_year import (
    espn_season_year,
    is_current_espn_season,
    season_label_for_espn_year,
)


@pytest.mark.parametrize(
    "label,sport,expected",
    [
        ("2026-27", "nba", 2027),
        ("2026-27", "ncaab_mens", 2027),
        ("2026-27", "ncaab_womens", 2027),
        ("2025-26", "nba", 2026),
        ("2003-04", "nba", 2004),
        (2027, "nba", 2027),
        ("2027", "nba", 2027),
        ("2026", "nfl", 2026),
        ("2026", "cfb", 2026),
        (2026, "nfl", 2026),
        ("2025-26", "nfl", 2025),  # calendar sports keep start when split-shaped
    ],
)
def test_espn_season_year(label, sport, expected):
    assert espn_season_year(label, sport) == expected


def test_season_label_roundtrip_nba():
    assert season_label_for_espn_year(2027, "nba") == "2026-27"
    assert espn_season_year(season_label_for_espn_year(2004, "nba"), "nba") == 2004


def test_is_current_espn_season_nba_oct_2026():
    # Tip-off / in-progress 2026-27 → ESPN year 2027.
    assert is_current_espn_season(2027, "nba", now_year=2026)
    assert not is_current_espn_season(2026, "nba", now_year=2026)


def test_is_current_espn_season_nfl_oct_2026():
    assert is_current_espn_season(2026, "nfl", now_year=2026)
    assert not is_current_espn_season(2025, "nfl", now_year=2026)


def test_fallback_and_errors():
    assert espn_season_year("", "nba", fallback=2027) == 2027
    with pytest.raises(ValueError):
        espn_season_year("no-year-here", "nba")
