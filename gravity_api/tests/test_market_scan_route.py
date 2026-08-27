import asyncio
from unittest.mock import AsyncMock, patch

from gravity_api.routers.market import market_scan
from gravity_api.services.athlete_eligibility import DEFAULT_FRESHNESS_DAYS


def _empty() -> dict:
    return {"athletes": [], "total": 0, "returned": 0}


def _one() -> dict:
    return {"athletes": [{"id": "a1", "name": "A. Player"}], "total": 1, "returned": 1}


def test_market_scan_keeps_live_window_when_populated():
    with patch("gravity_api.routers.market.run_athlete_search", new_callable=AsyncMock) as search:
        search.return_value = _one()
        out = asyncio.run(
            market_scan(
                sports=None,
                include_stale_roster=False,
                limit=50,
                offset=0,
                db=AsyncMock(),
            )
        )

    assert search.call_count == 1
    assert search.await_args.kwargs["roster_verified_within_days"] == DEFAULT_FRESHNESS_DAYS
    assert search.await_args.kwargs["exclude_inactive"] is True
    assert out["roster_window"] == "live"
    assert out["total"] == 1


def test_market_scan_falls_back_when_live_window_empty():
    with patch("gravity_api.routers.market.run_athlete_search", new_callable=AsyncMock) as search:
        search.side_effect = [_empty(), _one()]
        out = asyncio.run(
            market_scan(
                sports=None,
                include_stale_roster=False,
                limit=50,
                offset=0,
                db=AsyncMock(),
            )
        )

    assert search.call_count == 2
    assert search.await_args_list[0].kwargs["roster_verified_within_days"] == DEFAULT_FRESHNESS_DAYS
    assert search.await_args_list[1].kwargs["roster_verified_within_days"] is None
    assert out["roster_window"] == "stale_fallback"
    assert out["total"] == 1


def test_market_scan_include_stale_skips_live_window():
    with patch("gravity_api.routers.market.run_athlete_search", new_callable=AsyncMock) as search:
        search.return_value = _one()
        out = asyncio.run(
            market_scan(
                sports=None,
                include_stale_roster=True,
                limit=50,
                offset=0,
                db=AsyncMock(),
            )
        )

    assert search.call_count == 1
    assert search.await_args.kwargs["roster_verified_within_days"] is None
    assert out["roster_window"] == "stale"
    assert out["total"] == 1
