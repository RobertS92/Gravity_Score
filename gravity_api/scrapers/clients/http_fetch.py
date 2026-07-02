"""Direct HTTP page fetch — free alternative to Firecrawl for static pages."""

from __future__ import annotations

import contextvars
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; GravityScrapers/1.0; +https://gravityscore.com/bot)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_http_text_cache: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    "_http_text_cache", default=None
)


def begin_http_cache() -> None:
    _http_text_cache.set({})


def clear_http_cache() -> None:
    _http_text_cache.set(None)


class HttpFetchClient:
    def __init__(self, *, timeout_s: float = 30.0):
        self.timeout_s = timeout_s

    async def fetch_text(self, url: str) -> str:
        cache = _http_text_cache.get()
        if cache is not None and url in cache:
            return cache[url]

        async with httpx.AsyncClient(
            timeout=self.timeout_s,
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text

        if cache is not None:
            cache[url] = text
        return text

    async def fetch_html(self, url: str) -> str:
        return await self.fetch_text(url)


def html_to_markdownish(html: str) -> str:
    """Strip tags to line-oriented text for regex parsers."""
    if not html:
        return ""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<tr[^>]*>", "\n| ", text, flags=re.I)
    text = re.sub(r"<t[hd][^>]*>", " | ", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


__all__ = [
    "HttpFetchClient",
    "begin_http_cache",
    "clear_http_cache",
    "html_to_markdownish",
]
