"""College baseball / volleyball roster index tests."""

from gravity_api.scrapers.roster.college_sport_resolver import (
    _normalize_display_key,
    _slug_variants,
    fetch_ncaa_baseball_power_entries,
    fetch_ncaa_volleyball_power_entries,
)


def test_slug_variants_lady_teams():
    variants = _slug_variants("georgia-lady-bulldogs")
    assert "georgia-bulldogs" in variants


def test_normalize_display_key_strips_lady():
    assert "georgia" in _normalize_display_key("Georgia Lady Bulldogs")


def test_fetch_ncaa_baseball_power_entries():
    rows = fetch_ncaa_baseball_power_entries()
    assert len(rows) >= 60
    assert all(r["sport"] == "ncaa_baseball" for r in rows)
    assert all(r["espn_team_id"] for r in rows)


def test_fetch_ncaa_volleyball_power_entries():
    rows = fetch_ncaa_volleyball_power_entries()
    assert len(rows) >= 58
    assert all(r["sport"] == "ncaa_volleyball" for r in rows)
    assert all(r["espn_team_id"] for r in rows)
