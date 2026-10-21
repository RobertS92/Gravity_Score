"""Sports in scope for production acceptance gates (excludes deferred sports)."""

from __future__ import annotations

from gravity_api.scraper_registry.sports import SPORTS

# Deferred until roster/stats sources are wired.
EXCLUDED_ACCEPTANCE_SPORTS = frozenset({"ncaa_baseball", "ncaa_volleyball"})

ACCEPTANCE_SPORTS: tuple[str, ...] = tuple(
    slug for slug in SPORTS if slug not in EXCLUDED_ACCEPTANCE_SPORTS
)

# User / product priority for freshness + correctness (men's + women's basketball).
# Tuesday full refresh and GH canary target these; WNBA remains in ACCEPTANCE but
# is not required for the Tuesday priority path.
PRIORITY_SPORTS: tuple[str, ...] = (
    "cfb",
    "ncaab_mens",
    "ncaab_womens",
    "nfl",
    "nba",
)

PRIORITY_SPORTS_CSV = ",".join(PRIORITY_SPORTS)
