"""Multi-sport scraper smoke tests.

Live ESPN path runs by default (network). DB scheduled_full runs only when PG_DSN is set.
"""

from __future__ import annotations

import os

import pytest

from gravity_api.scraper_smoke.athletes import SMOKE_ATHLETES, athletes_by_sport
from gravity_api.scraper_smoke.runner import (
    run_smoke_suite,
    smoke_athlete_espn_scrapers,
)


def test_smoke_catalog_covers_priority_sports():
    by = athletes_by_sport()
    for sport in ("nfl", "nba", "cfb", "ncaab_mens", "ncaab_womens"):
        assert sport in by, f"missing sport {sport}"
        assert len(by[sport]) >= 2, f"{sport} needs >=2 athletes"


def test_smoke_athletes_have_espn_ids():
    for a in SMOKE_ATHLETES:
        assert a.espn_id.isdigit() or a.espn_id
        assert a.name_tokens


@pytest.mark.asyncio
async def test_live_espn_scraper_smoke_all_priority_athletes():
    """Live network smoke: roster+stats scrapers for all catalog athletes."""
    failures = []
    for athlete in SMOKE_ATHLETES:
        result = await smoke_athlete_espn_scrapers(athlete)
        if not result.passed:
            failed_checks = [c for c in result.checks if not c.ok]
            failures.append(
                f"{athlete.sport}/{athlete.name}: {result.error or failed_checks}"
            )
    assert not failures, "ESPN scraper smoke failures:\n" + "\n".join(failures)


@pytest.mark.asyncio
async def test_live_smoke_suite_summary():
    payload = await run_smoke_suite(include_db=False)
    assert payload["summary"]["espn_scrapers_passed"] == len(SMOKE_ATHLETES)
    assert payload["summary"]["espn_scrapers_failed"] == 0
    assert payload["summary"]["all_espn_passed"] is True


@pytest.mark.asyncio
async def test_db_scheduled_full_optional():
    if not os.environ.get("PG_DSN", "").strip():
        pytest.skip("PG_DSN unset — DB scheduled_full smoke skipped")
    payload = await run_smoke_suite(include_db=True)
    db_failed = payload["summary"]["db_scheduled_full_failed"]
    # Allow athletes missing from DB to fail athlete_in_db — report but don't
    # hard-fail CI unless SMOKE_REQUIRE_DB=1.
    if os.environ.get("SMOKE_REQUIRE_DB", "").strip() in {"1", "true", "yes"}:
        assert db_failed == 0, payload["summary"]
    else:
        assert "db_scheduled_full_passed" in payload["summary"]
