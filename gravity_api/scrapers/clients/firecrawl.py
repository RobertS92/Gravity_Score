"""Firecrawl v2 client for social and page scraping."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from gravity_api.config import get_settings

logger = logging.getLogger(__name__)

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"


class FirecrawlClient:
    def __init__(self, api_key: str | None = None, *, timeout_s: float = 90.0):
        settings = get_settings()
        self.api_key = api_key or settings.firecrawl_api_key
        self.timeout_s = timeout_s

    @property
    def enabled(self) -> bool:
        key = self.api_key or ""
        return bool(key) and key not in {"fc-YOUR_API_KEY", "fc-test", "fc-YOUR_API_KEY_HERE"}

    async def scrape(
        self,
        url: str,
        *,
        wait_for_ms: int = 2000,
        formats: list[str] | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("FIRECRAWL_API_KEY is not configured")

        payload = {
            "url": url,
            "formats": formats or ["markdown", "html", "links"],
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
            return body["data"]
        if isinstance(body, dict) and ("markdown" in body or "html" in body):
            return body
        return body if isinstance(body, dict) else {}

    async def scrape_markdown(self, url: str) -> str:
        data = await self.scrape(url)
        return str(data.get("markdown") or "")

    async def scrape_links(self, url: str) -> list[str]:
        data = await self.scrape(url)
        links = data.get("links")
        if isinstance(links, list):
            return [str(x) for x in links if x]
        return []
