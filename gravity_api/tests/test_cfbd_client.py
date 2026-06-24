"""Tests for CFBD client player id validation and season stats filtering."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx

from gravity_api.scrapers.clients.cfbd import (
    CfbdClient,
    parse_cfbd_player_id,
    player_id_from_row,
)


def test_parse_cfbd_player_id_rejects_negative_and_invalid():
    assert parse_cfbd_player_id(-1028527) is None
    assert parse_cfbd_player_id(0) is None
    assert parse_cfbd_player_id("-1028527") is None
    assert parse_cfbd_player_id("abc") is None
    assert parse_cfbd_player_id(None) is None
    assert parse_cfbd_player_id("1028527") == 1028527
    assert parse_cfbd_player_id(424242) == 424242


def test_player_id_from_row_prefers_positive_fields():
    assert player_id_from_row({"id": "-1028527", "playerId": "424242"}) == 424242
    assert player_id_from_row({"id": "424242"}) == 424242
    assert player_id_from_row({"id": -99}) is None


def test_search_player_skips_invalid_ids_and_matches_team():
    client = CfbdClient(api_key="test-key")

    async def fake_get(path: str, params: dict | None = None):
        assert path == "/player/search"
        return [
            {"id": "-1028527", "name": "John Smith", "team": "Alabama"},
            {"id": "424242", "name": "John Smith", "team": "Alabama"},
            {"id": "999999", "name": "John Smith", "team": "Georgia"},
        ]

    client._get = fake_get  # type: ignore[method-assign]
    row = asyncio.run(client.search_player("John Smith", team="Alabama"))
    assert row is not None
    assert player_id_from_row(row) == 424242


def test_search_player_strict_name_match_when_multiple_valid():
    client = CfbdClient(api_key="test-key")

    async def fake_get(_path: str, _params: dict | None = None):
        return [
            {"id": "111", "name": "John Smith", "team": "Alabama"},
            {"id": "222", "name": "Johnny Smith", "team": "Alabama"},
        ]

    client._get = fake_get  # type: ignore[method-assign]
    row = asyncio.run(client.search_player("John Smith", team="Alabama"))
    assert row is not None
    assert player_id_from_row(row) == 111


def test_player_season_stats_never_sends_player_id_param():
    client = CfbdClient(api_key="test-key")
    captured: list[dict] = []

    class FakeResp:
        status_code = 200

        def json(self):
            return [
                {
                    "playerId": "424242",
                    "player": "John Smith",
                    "category": "passing",
                    "yards": 2500,
                    "touchdowns": 20,
                    "games": 12,
                }
            ]

        def raise_for_status(self):
            return None

    async def fake_get(url, params=None):
        captured.append({"url": url, "params": params or {}})
        return FakeResp()

    async def run():
        with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=fake_get)):
            rows = await client.player_season_stats(
                year=2024,
                player_id=424242,
                team="Alabama",
                player_name="John Smith",
            )
        return rows

    rows = asyncio.run(run())
    assert captured
    params = captured[0]["params"]
    assert "playerId" not in params
    assert params["year"] == 2024
    assert params["team"] == "Alabama"
    assert len(rows) == 1
    assert rows[0]["playerId"] == "424242"


def test_player_season_stats_handles_400_gracefully():
    client = CfbdClient(api_key="test-key")

    class FakeResp:
        status_code = 400

        def json(self):
            return {"message": "bad request"}

        def raise_for_status(self):
            raise httpx.HTTPStatusError(
                "400",
                request=httpx.Request("GET", "https://example.com"),
                response=self,  # type: ignore[arg-type]
            )

    async def fake_get(_url, params=None):
        return FakeResp()

    async def run():
        with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=fake_get)):
            return await client.player_season_stats(
                year=2024,
                player_id=-1028527,
                team="Alabama",
                player_name="John Smith",
            )

    rows = asyncio.run(run())
    assert rows == []


def test_player_season_stats_filters_by_name_when_id_invalid():
    client = CfbdClient(api_key="test-key")

    async def fake_get(_path: str, _params: dict | None = None):
        return [
            {
                "playerId": "111",
                "player": "Jane Doe",
                "category": "rushing",
                "yards": 800,
                "games": 10,
            },
            {
                "playerId": "222",
                "player": "John Smith",
                "category": "passing",
                "yards": 3000,
                "touchdowns": 25,
                "games": 12,
            },
        ]

    client._get = fake_get  # type: ignore[method-assign]
    rows = asyncio.run(
        client.player_season_stats(
            year=2024,
            player_id=None,
            team="Alabama",
            player_name="John Smith",
        )
    )
    assert len(rows) == 1
    assert rows[0]["playerId"] == "222"


def test_cfbd_monthly_request_cap_skips_http():
    import os
    import gravity_api.scrapers.clients.cfbd as cfbd_mod

    cfbd_mod._cfbd_request_count = 0
    cfbd_mod._cfbd_run_request_count = 0
    os.environ["CFBD_MAX_REQUESTS_PER_MONTH"] = "2"
    os.environ.pop("CFBD_MAX_CALLS_PER_RUN", None)
    client = CfbdClient(api_key="test-key")
    calls = 0

    class FakeResp:
        status_code = 200

        def json(self):
            return []

        def raise_for_status(self):
            return None

    async def fake_get(_url, params=None):
        nonlocal calls
        calls += 1
        return FakeResp()

    async def run():
        with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=fake_get)):
            await client._get("/player/search", {"searchTerm": "x"})
            await client._get("/player/search", {"searchTerm": "y"})
            await client._get("/player/search", {"searchTerm": "z"})

    asyncio.run(run())
    assert calls == 2
