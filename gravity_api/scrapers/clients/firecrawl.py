"""Firecrawl v2 client for social and page scraping."""

from __future__ import annotations

import contextvars
import logging
import os
from typing import Any

import httpx

from gravity_api.config import get_settings

logger = logging.getLogger(__name__)

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"

_PLACEHOLDER_KEYS = frozenset(
    {"fc-YOUR_API_KEY", "fc-test", "fc-YOUR_API_KEY_HERE", "your-api-key-here"}
)

# Per-athlete scrape dedup — set by orchestrator around run_scrapers_for_athlete.
_scrape_url_cache: contextvars.ContextVar[dict[str, dict[str, Any]] | None] = (
    contextvars.ContextVar("_scrape_url_cache", default=None)
)


def begin_scrape_cache() -> None:
    """Start URL dedup cache for the current athlete scrape run."""
    _scrape_url_cache.set({})


def clear_scrape_cache() -> None:
    _scrape_url_cache.set(None)


def firecrawl_globally_disabled() -> bool:
    return os.environ.get("DISABLE_FIRECRAWL", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


class FirecrawlClient:
    def __init__(self, api_key: str | None = None, *, timeout_s: float = 90.0):
        settings = get_settings()
        self.api_key = api_key or settings.firecrawl_api_key
        self.timeout_s = timeout_s

    @property
    def enabled(self) -> bool:
        if firecrawl_globally_disabled():
            return False
        key = (self.api_key or "").strip()
        return bool(key) and key not in _PLACEHOLDER_KEYS

    async def scrape(
        self,
        url: str,
        *,
        wait_for_ms: int = 2000,
        formats: list[str] | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Firecrawl is disabled (DISABLE_FIRECRAWL or missing API key)")

        cache = _scrape_url_cache.get()
        if cache is not None and url in cache:
            return cache[url]

        payload = {
            "url": url,
            "formats": formats or ["markdown"],
            "onlyMainContent": True,
            "waitFor": wait_for_ms,
            "timeout": 60000,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(FIRECRAWL_SCRAPE_URL, json=payload, headers=headers)
            resp.raise_for_status()
            body = resp.json()

        if body.get("success") and isinstance(body.get("data"), dict):
            data = body["data"]
        elif isinstance(body, dict) and ("markdown" in body or "html" in body):
            data = body
        else:
            data = body if isinstance(body, dict) else {}

        if cache is not None:
            cache[url] = data
        return data

    async def scrape_markdown(self, url: str) -> str:
        data = await self.scrape(url, formats=["markdown"])
        return str(data.get("markdown") or "")

    async def scrape_links(self, url: str) -> list[str]:
        data = await self.scrape(url, formats=["links"])
        links = data.get("links")
        if isinstance(links, list):
            return [str(x) for x in links if x]
        return []
