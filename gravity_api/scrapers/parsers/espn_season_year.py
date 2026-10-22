"""Normalize human season labels to ESPN's integer season year.

NBA / NCAAB use split labels like ``2026-27`` where ESPN's path year is the
**end** year (2027). NFL / CFB use calendar season years (``2026`` → 2026).

This is the shared off-by-one guard required by the season-history backfill spec.
"""

from __future__ import annotations

import re
from typing import Any

_SPLIT_RE = re.compile(
    r"^\s*(?P<start>20\d{2})\s*[-/–—]\s*(?P<end>\d{2}|\d{4})\s*$"
)
_YEAR_RE = re.compile(r"(20\d{2})")

# Sports whose human labels are ``YYYY-YY`` and whose ESPN year is the end year.
_SPLIT_SPORTS = frozenset(
    {
        "nba",
        "wnba",
        "ncaab_mens",
        "ncaab_womens",
        "mcbb",
        "wcbb",
        "ncaab",
    }
)

# Sports whose ESPN year equals the calendar / fall start year.
_CALENDAR_SPORTS = frozenset(
    {
        "nfl",
        "cfb",
        "ncaaf",
        "ncaa_baseball",
        "ncaa_volleyball",
    }
)


def normalize_sport_key(sport: str | None) -> str:
    s = (sport or "").lower().strip()
    aliases = {
        "mcbb": "ncaab_mens",
        "wcbb": "ncaab_womens",
        "ncaab": "ncaab_mens",
        "ncaaf": "cfb",
    }
    return aliases.get(s, s)


def season_label_for_espn_year(espn_year: int, sport: str | None) -> str:
    """Human label for an ESPN season year."""
    sport_n = normalize_sport_key(sport)
    if sport_n in _SPLIT_SPORTS:
        start = int(espn_year) - 1
        end_yy = int(espn_year) % 100
        return f"{start}-{end_yy:02d}"
    return str(int(espn_year))


def espn_season_year(
    label: Any,
    sport: str | None = None,
    *,
    fallback: int | None = None,
) -> int:
    """Map a season label / int to ESPN's integer season year.

    Examples
    --------
    >>> espn_season_year("2026-27", "nba")
    2027
    >>> espn_season_year("2026", "nfl")
    2026
    >>> espn_season_year(2027, "ncaab_mens")
    2027
    """
    sport_n = normalize_sport_key(sport)

    if isinstance(label, bool):
        raise TypeError("season label cannot be bool")
    if isinstance(label, (int, float)) and not isinstance(label, bool):
        year = int(label)
        if year < 1900 or year > 2100:
            if fallback is not None:
                return int(fallback)
            raise ValueError(f"out-of-range ESPN season year: {year}")
        return year

    text = str(label or "").strip()
    if not text:
        if fallback is not None:
            return int(fallback)
        raise ValueError("empty season label")

    split = _SPLIT_RE.match(text)
    if split:
        start = int(split.group("start"))
        end_raw = split.group("end")
        end = int(end_raw) if len(end_raw) == 4 else 2000 + int(end_raw)
        # Prefer end year for split sports; for calendar sports a mistaken
        # "2025-26" style label still maps to end if sport is split, else start.
        if sport_n in _SPLIT_SPORTS or sport_n not in _CALENDAR_SPORTS:
            return end
        return start

    years = [int(m.group(1)) for m in _YEAR_RE.finditer(text)]
    if not years:
        if fallback is not None:
            return int(fallback)
        raise ValueError(f"no year in season label: {text!r}")

    if sport_n in _SPLIT_SPORTS and len(years) == 1:
        # Bare "2027" for NBA already is the ESPN year.
        return years[0]
    if sport_n in _SPLIT_SPORTS and len(years) >= 2:
        return max(years)
    # NFL / CFB: first four-digit year wins ("2026 season").
    return years[0]


def is_current_espn_season(espn_year: int, sport: str | None, *, now_year: int | None = None) -> bool:
    """Whether ``espn_year`` is the in-progress season for ``sport``."""
    from datetime import datetime, timezone

    sport_n = normalize_sport_key(sport)
    now = datetime.now(tz=timezone.utc)
    calendar_year = int(now_year if now_year is not None else now.year)
    month = now.month

    if sport_n in _SPLIT_SPORTS:
        # NBA/NCAAB: season spanning calendar_year-1 → calendar_year uses ESPN year
        # = calendar_year while Aug–Jun; Jul starts next season's prep (still prior
        # ESPN year until tip-off — treat Jul+ as next ESPN year).
        current = calendar_year if month >= 7 else calendar_year
        # Oct 2026 → 2026-27 → ESPN 2027 when month >= 10? Tip-off is Oct.
        # Spec anchors current in-progress as 2026-27 → 2027.
        if month >= 10:
            current = calendar_year + 1
        elif month >= 7:
            current = calendar_year + 1
        else:
            current = calendar_year
        return int(espn_year) == current

    # NFL / CFB: season year == calendar year from Aug onward; Jan–Jul still prior.
    current = calendar_year if month >= 8 else calendar_year - 1
    return int(espn_year) == current


__all__ = [
    "espn_season_year",
    "is_current_espn_season",
    "normalize_sport_key",
    "season_label_for_espn_year",
]
