"""WP1 acceptance: season calendar single source of truth."""

from __future__ import annotations

from datetime import date

import pytest

from gravity_api.scrapers.season_calendar import (
    current_season_year,
    parse_season_label,
    season_label,
    season_status,
)


def test_lebron_2003_04_roundtrip():
    assert parse_season_label("nba", "2003-04") == 2004
    assert season_label("nba", 2004) == "2003-04"
    assert parse_season_label("nba", season_label("nba", 2004)) == 2004


def test_nba_current_on_2026_10_22():
    on = date(2026, 10, 22)
    assert current_season_year("nba", on) == 2027
    assert season_status("nba", 2027, on) == "in_progress"
    assert season_status("nba", 2026, on) == "complete"


def test_cfb_current_on_2026_10_22():
    on = date(2026, 10, 22)
    assert current_season_year("cfb", on) == 2026
    assert season_status("cfb", 2026, on) == "in_progress"


def test_nba_july_15_2026_complete_and_future():
    on = date(2026, 7, 15)
    assert season_status("nba", 2026, on) == "complete"
    assert season_status("nba", 2027, on) == "future"


def test_nfl_current_on_2026_10_22():
    on = date(2026, 10, 22)
    assert current_season_year("nfl", on) == 2026


@pytest.mark.parametrize(
    "league,label,expected",
    [
        ("nba", "2026-27", 2027),
        ("ncaab_mens", "2025-26", 2026),
        ("ncaab_womens", "2026-27", 2027),
        ("nfl", "2026", 2026),
        ("cfb", "2026", 2026),
        ("nba", 2004, 2004),
        ("nba", "1999-00", 2000),
        ("nba", "1998-99", 1999),
    ],
)
def test_parse_season_label_matrix(league, label, expected):
    assert parse_season_label(league, label) == expected


def test_pre_2000_not_swallowed():
    # Old regex ``20\\d{2}`` could not parse these.
    assert parse_season_label("nba", "1995-96") == 1996
    assert season_label("nba", 1996) == "1995-96"


def test_no_legacy_helpers_remain():
    """Acceptance: B7 private helpers must be gone (repo-wide *.py except this assert)."""
    from pathlib import Path
    import re

    # Built from parts so this file does not itself match the acceptance grep.
    names = [
        "_" + "current_season_year",
        "_" + "parse_season_year",
        "_" + "season_label_to_key",
    ]
    pattern = re.compile("|".join(re.escape(n) for n in names))
    root = Path(__file__).resolve().parents[2]  # repo root
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path.name == "test_season_calendar.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if pattern.search(text):
            offenders.append(str(path.relative_to(root)))
    assert offenders == [], f"legacy season helpers still present: {offenders}"
