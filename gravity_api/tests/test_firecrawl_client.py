"""Tests for Firecrawl disable flag and per-athlete URL dedup."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from gravity_api.scrapers.clients import firecrawl as fc_mod
from gravity_api.scrapers.clients.firecrawl import FirecrawlClient


@pytest.fixture(autouse=True)
def _clear_scrape_cache():
    fc_mod.clear_scrape_cache()
    yield
    fc_mod.clear_scrape_cache()


def test_disabled_when_env_flag(monkeypatch):
    monkeypatch.setenv("DISABLE_FIRECRAWL", "1")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-real-key")
    fc_mod.get_settings.cache_clear()
    client = FirecrawlClient()
    assert client.enabled is False
    fc_mod.get_settings.cache_clear()


def test_disabled_for_placeholder_key(monkeypatch):
    monkeypatch.delenv("DISABLE_FIRECRAWL", raising=False)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-YOUR_API_KEY")
    fc_mod.get_settings.cache_clear()
    client = FirecrawlClient()
    assert client.enabled is False
    fc_mod.get_settings.cache_clear()


def test_enabled_for_real_key(monkeypatch):
    monkeypatch.delenv("DISABLE_FIRECRAWL", raising=False)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-production-key")
    fc_mod.get_settings.cache_clear()
    client = FirecrawlClient()
    assert client.enabled is True
    fc_mod.get_settings.cache_clear()


def test_scrape_dedupes_same_url_within_run(monkeypatch):
    monkeypatch.delenv("DISABLE_FIRECRAWL", raising=False)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-production-key")
    fc_mod.get_settings.cache_clear()

    client = FirecrawlClient()
    calls = {"n": 0}

    async def fake_post(*_args, **_kwargs):
        calls["n"] += 1
        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"success": True, "data": {"markdown": "hello"}}

        return Resp()

    async def run():
        fc_mod.begin_scrape_cache()
        with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=fake_post)):
            md1 = await client.scrape_markdown("https://www.instagram.com/test/")
            md2 = await client.scrape_markdown("https://www.instagram.com/test/")
        fc_mod.clear_scrape_cache()
        return md1, md2

    md1, md2 = asyncio.run(run())
    assert md1 == "hello"
    assert md2 == "hello"
    assert calls["n"] == 1
    fc_mod.get_settings.cache_clear()
