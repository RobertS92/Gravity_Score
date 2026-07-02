"""Sports in scope for production acceptance gates (excludes deferred sports)."""

from __future__ import annotations

from gravity_api.scraper_registry.sports import SPORTS

# Deferred until roster/stats sources are wired.
EXCLUDED_ACCEPTANCE_SPORTS = frozenset({"ncaa_baseball", "ncaa_volleyball"})

ACCEPTANCE_SPORTS: tuple[str, ...] = tuple(
    slug for slug in SPORTS if slug not in EXCLUDED_ACCEPTANCE_SPORTS
)
