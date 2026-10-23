"""WP8: smoke athlete definitions, live-roster team match, lifecycle facts."""

from __future__ import annotations

from gravity_api.scraper_smoke.athletes import (
    DRAFT_DEPARTURE_FIXTURES,
    LIFECYCLE_FACTS,
    SMOKE_ATHLETES,
    LifecycleFact,
    athletes_by_sport,
    lifecycle_facts_for_espn_id,
)
from gravity_api.scraper_smoke.runner import (
    _assert_identity_and_signal,
    lifecycle_fact_checks_from_rows,
    teams_match,
)
from gravity_api.services.roster_retirement import departure_status
from gravity_api.services.sport_pipeline.nightly import NIGHTLY_PIPELINE_ORDER


def test_nightly_pipeline_order_is_sync_hygiene_stats():
    assert NIGHTLY_PIPELINE_ORDER == ("roster_sync", "roster_hygiene", "stats")


def test_smoke_catalog_covers_priority_sports():
    by = athletes_by_sport()
    for sport in ("nfl", "nba", "cfb", "ncaab_mens", "ncaab_womens"):
        assert sport in by
        assert len(by[sport]) >= 2


def test_team_hint_is_docs_only_not_pass_fail():
    """Stale team_hint must not drive smoke identity (B10)."""
    lebron = next(a for a in SMOKE_ATHLETES if a.name == "LeBron James")
    # Even if hint were still Lakers-era, live roster match is the criterion.
    fields = {
        "player_name": "LeBron James",
        "espn_id": "1966",
        "position": "F",
        "team": "Philadelphia 76ers",
        "season_stats": {"pts": 20, "reb": 7, "ast": 8, "gp": 10},
        "stats_as_of": "2026-10-22T00:00:00Z",
        "stats_scope": "season",
    }
    checks = _assert_identity_and_signal(
        lebron, fields, live_roster_team="Philadelphia 76ers"
    )
    by_name = {c.name: c for c in checks}
    assert "team_matches_live_espn_roster" in by_name
    assert by_name["team_matches_live_espn_roster"].ok
    assert "team_or_college" not in by_name  # old hint-based check removed


def test_teams_match_helper():
    assert teams_match("Philadelphia 76ers", "76ers")
    assert teams_match("Washington Wizards", "Wizards")
    assert not teams_match("Los Angeles Lakers", "Philadelphia 76ers")
    assert not teams_match(None, "76ers")
    assert not teams_match("76ers", None)


def test_live_roster_mismatch_fails_even_if_hint_matches():
    athlete = next(a for a in SMOKE_ATHLETES if a.name == "Patrick Mahomes")
    fields = {
        "player_name": "Patrick Mahomes",
        "espn_id": athlete.espn_id,
        "position": "QB",
        "team": "Kansas City Chiefs",
        "season_stats": {"pass_yards": 100, "pass_td": 1, "gp": 1},
        "stats_as_of": "2026-10-01T00:00:00Z",
        "stats_scope": "season",
    }
    # Hint says Chiefs, but live ESPN roster says something else → fail.
    checks = _assert_identity_and_signal(
        athlete, fields, live_roster_team="Las Vegas Raiders"
    )
    team_check = next(c for c in checks if c.name == "team_matches_live_espn_roster")
    assert team_check.ok is False


def test_lifecycle_facts_dybantsa_and_boozer():
    assert len(LIFECYCLE_FACTS) >= 2
    by_name = {f.name: f for f in LIFECYCLE_FACTS}
    dyb = by_name["AJ Dybantsa"]
    assert dyb.espn_id == "5142718"
    assert dyb.college_sport == "ncaab_mens"
    assert dyb.pro_sport == "nba"
    assert dyb.college_is_active is False
    assert dyb.pro_record_exists is True
    assert dyb.expected_roster_status == "left_for_draft"
    assert dyb.same_espn_id_college_and_pro is True
    # No separate crosswalk: college+pro share ESPN id.
    assert dyb.espn_id == "5142718"

    booz = by_name["Cameron Boozer"]
    assert booz.espn_id == "5041935"
    assert booz.college_is_active is False
    assert departure_status("Freshman", has_pro_match=True)[0] == "left_for_draft"


def test_draft_departure_fixtures_alias_matches_lifecycle_facts():
    assert len(DRAFT_DEPARTURE_FIXTURES) == len(LIFECYCLE_FACTS)
    for fix, fact in zip(DRAFT_DEPARTURE_FIXTURES, LIFECYCLE_FACTS, strict=True):
        assert fix["espn_id"] == fact.espn_id
        assert fix["expected_roster_status"] == fact.expected_roster_status


def test_lifecycle_fact_checks_from_rows_pass():
    fact = lifecycle_facts_for_espn_id("5142718")[0]
    checks = lifecycle_fact_checks_from_rows(
        fact,
        college_row={
            "espn_id": "5142718",
            "sport": "ncaab_mens",
            "is_active": False,
            "roster_status": "left_for_draft",
        },
        pro_row={
            "espn_id": "5142718",
            "sport": "nba",
            "is_active": True,
            "roster_status": "active_on_roster",
        },
    )
    assert checks
    assert all(c.ok for c in checks)


def test_lifecycle_fact_checks_fail_when_college_still_active():
    fact = LifecycleFact(
        name="AJ Dybantsa",
        espn_id="5142718",
        college_sport="ncaab_mens",
        college_team="BYU",
        pro_sport="nba",
        pro_team="Wizards",
    )
    checks = lifecycle_fact_checks_from_rows(
        fact,
        college_row={
            "espn_id": "5142718",
            "is_active": True,
            "roster_status": "active_on_roster",
        },
        pro_row={"espn_id": "5142718", "sport": "nba"},
    )
    by_name = {c.name: c for c in checks}
    assert by_name["lifecycle_college_is_active"].ok is False
    assert by_name["lifecycle_college_roster_status"].ok is False
    assert by_name["lifecycle_pro_record_exists"].ok is True


def test_no_espn_id_crosswalk_migration_for_fixture_athletes():
    """College→pro fixtures share one ESPN id; 040 crosswalk table not required."""
    from pathlib import Path

    migrations = Path(__file__).resolve().parents[2] / "migrations"
    assert not (migrations / "040_athlete_espn_id_crosswalk.sql").exists()
    for fact in LIFECYCLE_FACTS:
        assert fact.same_espn_id_college_and_pro is True
        # Smoke catalog pro row uses the same espn_id as the college lifecycle fact.
        pro = next(a for a in SMOKE_ATHLETES if a.espn_id == fact.espn_id and a.sport == fact.pro_sport)
        assert pro.espn_id == fact.espn_id
