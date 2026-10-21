"""Multi-sport scraper smoke tests.

Catalog checks always run. Live ESPN / DB paths require env flags so CI stays green.
"""

from __future__ import annotations

import os

import pytest

from gravity_api.scraper_smoke.athletes import SMOKE_ATHLETES, athletes_by_sport
from gravity_api.scraper_smoke.runner import (
    run_smoke_suite,
    smoke_athlete_espn_scrapers,
)


def _live_enabled() -> bool:
    return os.environ.get("RUN_LIVE_SCRAPER_SMOKE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def test_smoke_catalog_covers_priority_sports():
    by = athletes_by_sport()
    for sport in ("nfl", "nba", "cfb", "ncaab_mens", "ncaab_womens"):
        assert sport in by, f"missing sport {sport}"
        assert len(by[sport]) >= 2, f"{sport} needs >=2 athletes"


def test_smoke_athletes_have_espn_ids():
    for a in SMOKE_ATHLETES:
        assert a.espn_id.isdigit() or a.espn_id
        assert a.name_tokens


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_espn_scraper_smoke_all_priority_athletes():
    """Live network smoke: roster+stats scrapers for all catalog athletes."""
    if not _live_enabled():
        pytest.skip("Set RUN_LIVE_SCRAPER_SMOKE=1 to run live ESPN smoke")
    failures = []
    for athlete in SMOKE_ATHLETES:
        result = await smoke_athlete_espn_scrapers(athlete)
        if not result.passed:
            failed_checks = [c for c in result.checks if not c.ok]
            failures.append(
                f"{athlete.sport}/{athlete.name}: {result.error or failed_checks}"
            )
    assert not failures, "ESPN scraper smoke failures:\n" + "\n".join(failures)


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_smoke_suite_summary():
    if not _live_enabled():
        pytest.skip("Set RUN_LIVE_SCRAPER_SMOKE=1 to run live ESPN smoke")
    payload = await run_smoke_suite(include_db=False)
    assert payload["summary"]["espn_scrapers_passed"] == len(SMOKE_ATHLETES)
    assert payload["summary"]["espn_scrapers_failed"] == 0
    assert payload["summary"]["all_espn_passed"] is True


@pytest.mark.live
@pytest.mark.asyncio
async def test_db_scheduled_full_optional():
    if not _live_enabled():
        pytest.skip("Set RUN_LIVE_SCRAPER_SMOKE=1 to run live smoke")
    if not os.environ.get("PG_DSN", "").strip():
        pytest.skip("PG_DSN unset — DB scheduled_full smoke skipped")
    payload = await run_smoke_suite(include_db=True)
    db_failed = payload["summary"]["db_scheduled_full_failed"]
    if os.environ.get("SMOKE_REQUIRE_DB", "").strip() in {"1", "true", "yes"}:
        assert db_failed == 0, payload["summary"]
    else:
        assert "db_scheduled_full_passed" in payload["summary"]
