"""Scraper registry package — canonical manifest for gravity-scrapers."""

from gravity_api.scraper_registry.build import (
    build_registry,
    registry_by_key,
    scrapers_for_event,
    scrapers_for_sport,
)
from gravity_api.scraper_registry.events import COLLECTOR_MAP, resolve_event_scraper_keys
from gravity_api.scraper_registry.types import ScraperDefinition

__all__ = [
    "ScraperDefinition",
    "build_registry",
    "registry_by_key",
    "scrapers_for_event",
    "scrapers_for_sport",
    "COLLECTOR_MAP",
    "resolve_event_scraper_keys",
]
