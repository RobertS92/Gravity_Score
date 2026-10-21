"""Freshness / correctness fixes for scrapers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gravity_api.scrapers.clients import espn as espn_mod
from gravity_api.scrapers.implementations import (
    ChampionshipResultsScraper,
    InstagramFollowersScraper,
    InjuryStructuredScraper,
    StatsFreshnessScraper,
)
from gravity_api.scrapers.types import AthleteScrapeContext


def _ctx(**kwargs) -> AthleteScrapeContext:
    base = dict(
        athlete_id="a1",
        name="Test Athlete",
        sport="cfb",
        school="Alabama",
        team="Alabama",
        position="QB",
        espn_id="123",
        existing_raw={},
        league_tier="college",
        event_type="gap_fill",
        force_refresh=False,
    )
    base.update(kwargs)
    return AthleteScrapeContext(**base)


@pytest.mark.asyncio
async def test_stats_freshness_does_not_invent_now():
    scraper = StatsFreshnessScraper()
    result = await scraper.run(_ctx(existing_raw={}), "stats_freshness_cfb")
    assert result.status == "skipped"
    assert "stats_as_of" not in result.fields


@pytest.mark.asyncio
async def test_stats_freshness_preserves_existing_stamp():
    scraper = StatsFreshnessScraper()
    result = await scraper.run(
        _ctx(existing_raw={"stats_as_of": "2025-09-01", "games_played_season": 5}),
        "stats_freshness_cfb",
    )
    assert result.fields.get("stats_as_of") == "2025-09-01"
    assert result.status == "success"


@pytest.mark.asyncio
async def test_instagram_early_return_only_on_gap_fill():
    scraper = InstagramFollowersScraper()
    raw = {
        "instagram_handle": "qb1",
        "instagram_handle_source": "espn",
        "instagram_followers": 50000,
        "instagram_followers_observed": 1,
    }
    gap_ctx = _ctx(existing_raw=raw, event_type="gap_fill", force_refresh=False)
    with patch(
        "gravity_api.scrapers.implementations.has_trusted_instagram_handle",
        return_value=True,
    ):
        result = await scraper.run(gap_ctx, "instagram_followers_cfb")
    assert result.status == "skipped"
    assert result.fields.get("instagram_followers") == 50000


@pytest.mark.asyncio
async def test_instagram_refreshes_on_scheduled_full():
    scraper = InstagramFollowersScraper()
    raw = {
        "instagram_handle": "qb1",
        "instagram_handle_source": "espn",
        "instagram_followers": 50000,
        "instagram_followers_observed": 1,
    }
    full_ctx = _ctx(
        existing_raw=raw, event_type="scheduled_full", force_refresh=True
    )
    mock_fc = MagicMock()
    mock_fc.enabled = False
    with (
        patch(
            "gravity_api.scrapers.implementations.has_trusted_instagram_handle",
            return_value=True,
        ),
        patch(
            "gravity_api.scrapers.implementations.FirecrawlClient",
            return_value=mock_fc,
        ),
    ):
        result = await scraper.run(full_ctx, "instagram_followers_cfb")
    assert result.error_message == "firecrawl disabled"
    assert result.status == "partial"


@pytest.mark.asyncio
async def test_injury_does_not_proxy_games_missed_from_list_len():
    scraper = InjuryStructuredScraper()
    profile = {
        "injuries": [
            {"status": "Out", "date": "2025-10-01"},
            {"status": "Questionable", "date": "2025-09-20"},
        ]
    }
    with patch(
        "gravity_api.scrapers.implementations.EspnClient.get_athlete_profile",
        new=AsyncMock(return_value=profile),
    ):
        result = await scraper.run(_ctx(), "injury_structured_cfb")
    assert "games_missed_season" not in result.fields
    assert result.fields.get("injury_report_count") == 2
    assert result.fields.get("current_injury_status") == "Out"


@pytest.mark.asyncio
async def test_championship_skips_without_awards_payload():
    scraper = ChampionshipResultsScraper()
    result = await scraper.run(
        _ctx(existing_raw={"player_name": "X"}), "championship_results_cfb"
    )
    assert result.status == "skipped"
    assert "national_championships" not in result.fields


@pytest.mark.asyncio
async def test_espn_does_not_cache_empty_error():
    espn_mod.begin_espn_cache()
    try:
        client = espn_mod.EspnClient()
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.status_code = 503
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client
            data = await client._get("https://example.test/espn")
            assert data == {}
            assert "https://example.test/espn" not in (espn_mod._espn_get_cache.get() or {})
    finally:
        espn_mod.clear_espn_cache()
