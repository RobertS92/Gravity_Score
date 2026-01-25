"""Helpers for Firecrawl-backed URL discovery."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlparse

try:  # pragma: no cover - optional import handled in tests
    from firecrawl import FirecrawlApp
except Exception:  # pragma: no cover - gracefully degrade when SDK unavailable
    FirecrawlApp = None  # type: ignore

LOGGER = logging.getLogger("nfl_gravity.scrapers.discovery")

_DEFAULT_APP: Optional[FirecrawlApp] = None
_DEFAULT_APP_INITIALISED = False


@dataclass
class DiscoveryResult:
    """Container describing a discovered URL and confidence score."""

    url: str
    score: float


def _slugify(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _compute_score(name: str, domain: str, candidate: str) -> float:
    parsed = urlparse(candidate)
    score = 0.0
    if domain.replace("https://", "").replace("http://", "") in parsed.netloc:
        score += 10
    slug_name = _slugify(name)
    slug_path = _slugify(parsed.path)
    if slug_name and slug_name in slug_path:
        score += 6
    if slug_path.endswith(slug_name):
        score += 2
    if any(token in parsed.path.lower() for token in ["official", "verified", "player", "athlete"]):
        score += 1.5
    if "?" not in candidate:
        score += 1
    return score


def _get_default_app() -> Optional[FirecrawlApp]:
    global _DEFAULT_APP_INITIALISED, _DEFAULT_APP
    if _DEFAULT_APP_INITIALISED:
        return _DEFAULT_APP
    _DEFAULT_APP_INITIALISED = True
    if FirecrawlApp is None:
        LOGGER.warning("Firecrawl SDK not installed; discovery will be disabled")
        _DEFAULT_APP = None
        return None
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        LOGGER.warning("FIRECRAWL_API_KEY missing; discovery will return None")
        _DEFAULT_APP = None
        return None
    _DEFAULT_APP = FirecrawlApp(api_key=api_key)
    return _DEFAULT_APP


class FirecrawlDiscovery:
    """Wrapper around :class:`FirecrawlApp`'s ``map_url`` search."""

    def __init__(self, app: Optional[FirecrawlApp] = None) -> None:
        if app is not None:
            self.app = app
            return
        default_app = _get_default_app()
        if default_app is None:
            raise RuntimeError("Firecrawl discovery unavailable: SDK or API key missing")
        self.app = default_app

    def discover(self, name: str, domain: str, keyword: Optional[str] = None) -> Optional[str]:
        query = name if not keyword else f"{name} {keyword}"
        LOGGER.debug("Discovering %s on %s with query '%s'", name, domain, query)
        try:
            response: Dict[str, List[str]] = self.app.map_url(domain, params={"search": query})  # type: ignore[call-arg]
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.error("Firecrawl discovery failed for %s on %s: %s", name, domain, exc)
            return None
        urls = response.get("urls", [])
        if not urls:
            return None
        ranked = sorted(
            (DiscoveryResult(url=u, score=_compute_score(name, domain, u)) for u in urls),
            key=lambda result: result.score,
            reverse=True,
        )
        LOGGER.debug("Ranked URLs for %s: %s", name, ranked)
        return ranked[0].url if ranked else None


def discover_best_url(name: str, domain: str, keyword: Optional[str] = None, app: Optional[FirecrawlApp] = None) -> Optional[str]:
    """Convenience wrapper used by adapters."""

    if app is not None:
        discovery = FirecrawlDiscovery(app=app)
    else:
        try:
            discovery = FirecrawlDiscovery()
        except RuntimeError:
            LOGGER.warning("Discovery skipped for %s: Firecrawl unavailable", name)
            return None
    return discovery.discover(name=name, domain=domain, keyword=keyword)


__all__ = ["FirecrawlDiscovery", "discover_best_url"]
