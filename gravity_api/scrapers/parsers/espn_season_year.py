"""Back-compat shim — prefer ``gravity_api.scrapers.season_calendar``.

Kept so older imports (`espn_season_year`, `season_label_for_espn_year`,
`is_current_espn_season`) continue to work while call sites migrate to
``season_calendar`` (SCRAPER_FIX_SPEC §4.1 / WP1).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from gravity_api.scrapers.season_calendar import (
    current_season_year,
    normalize_league,
    parse_season_label,
    season_label,
    season_status,
)

# Re-export under the historical name.
normalize_sport_key = normalize_league


def season_label_for_espn_year(espn_year: int, sport: str | None) -> str:
    return season_label(sport or "", int(espn_year))


def espn_season_year(
    label: Any,
    sport: str | None = None,
    *,
    fallback: int | None = None,
) -> int:
    try:
        return parse_season_label(sport or "", label)
    except (TypeError, ValueError):
        if fallback is not None:
            return int(fallback)
        raise


def is_current_espn_season(
    espn_year: int,
    sport: str | None,
    *,
    now_year: int | None = None,
    on: date | None = None,
) -> bool:
    if on is None:
        if now_year is not None:
            # Historical tests passed calendar year only; assume mid-October.
            on = date(int(now_year), 10, 22)
        else:
            on = datetime.now(tz=timezone.utc).date()
    return season_status(sport or "", int(espn_year), on) == "in_progress"


def current_espn_season_year(sport: str | None = None, *, on: date | None = None) -> int:
    day = on or datetime.now(tz=timezone.utc).date()
    return current_season_year(sport or "", day)


__all__ = [
    "current_espn_season_year",
    "espn_season_year",
    "is_current_espn_season",
    "normalize_sport_key",
    "season_label_for_espn_year",
]
