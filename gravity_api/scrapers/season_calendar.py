"""Single source of truth for league season years (SCRAPER_FIX_SPEC §4.1).

Everything that touches a season year imports from here.
Season windows come from ESPN core ``seasons/{year}`` (``startDate``/``endDate``),
cached per (league, year). Fixture-seeded defaults cover offline tests.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Any, Literal, Mapping

SeasonStatus = Literal["complete", "in_progress", "future"]

_SPLIT_RE = re.compile(
    r"^\s*(?P<start>\d{4})\s*[-/–—]\s*(?P<end>\d{2}|\d{4})\s*$"
)
_YEAR_RE = re.compile(r"(\d{4})")

# Leagues whose stored season_year is the year the season **ends**
# and whose human label is ``YYYY-YY``.
_SPLIT_LEAGUES = frozenset(
    {
        "nba",
        "ncaab_mens",
        "ncaab_womens",
        "mcbb",
        "wcbb",
        "ncaab",
    }
)

# WNBA plays within one calendar year; season_year == that year.
# NFL/CFB: year the season starts. Baseball/volleyball: calendar year played.
_CALENDAR_LEAGUES = frozenset(
    {
        "nfl",
        "cfb",
        "ncaaf",
        "wnba",
        "ncaa_baseball",
        "ncaa_volleyball",
    }
)

# Seeded from live ESPN core seasons/{year} captures (WP0 fixtures, 2026-10-23).
# Values are (start_date inclusive, end_date inclusive) in UTC calendar dates.
_SEED_WINDOWS: dict[tuple[str, int], tuple[date, date]] = {
    ("nba", 2026): (date(2025, 10, 1), date(2026, 6, 26)),
    ("nba", 2027): (date(2026, 9, 30), date(2027, 6, 25)),
    ("ncaab_mens", 2026): (date(2025, 11, 1), date(2026, 4, 7)),
    ("ncaab_mens", 2027): (date(2026, 11, 1), date(2027, 4, 7)),
    ("ncaab_womens", 2026): (date(2025, 11, 1), date(2026, 4, 7)),
    ("ncaab_womens", 2027): (date(2026, 11, 1), date(2027, 4, 7)),
    ("nfl", 2025): (date(2025, 8, 6), date(2026, 2, 16)),
    ("nfl", 2026): (date(2026, 8, 6), date(2027, 2, 15)),
    ("cfb", 2025): (date(2025, 2, 1), date(2026, 1, 28)),
    ("cfb", 2026): (date(2026, 2, 1), date(2027, 1, 27)),
    ("wnba", 2025): (date(2025, 5, 1), date(2025, 10, 20)),
    ("wnba", 2026): (date(2026, 5, 1), date(2026, 10, 20)),
}

# Runtime cache: (league, year) -> (start, end). Seeded from _SEED_WINDOWS.
_WINDOW_CACHE: dict[tuple[str, int], tuple[date, date]] = dict(_SEED_WINDOWS)


def normalize_league(league: str | None) -> str:
    s = (league or "").lower().strip()
    aliases = {
        "mcbb": "ncaab_mens",
        "wcbb": "ncaab_womens",
        "ncaab": "ncaab_mens",
        "ncaaf": "cfb",
    }
    return aliases.get(s, s)


def _parse_espn_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # ESPN: ``2026-09-30T07:00Z``
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def register_season_window(
    league: str,
    season_year: int,
    *,
    start: date | datetime | str,
    end: date | datetime | str,
) -> None:
    """Cache a league-year window from ESPN ``seasons/{year}`` (or tests)."""
    lg = normalize_league(league)
    start_d = start if isinstance(start, date) and not isinstance(start, datetime) else _parse_espn_date(start)
    end_d = end if isinstance(end, date) and not isinstance(end, datetime) else _parse_espn_date(end)
    if isinstance(start, datetime):
        start_d = start.astimezone(timezone.utc).date() if start.tzinfo else start.date()
    if isinstance(end, datetime):
        end_d = end.astimezone(timezone.utc).date() if end.tzinfo else end.date()
    if start_d is None or end_d is None:
        raise ValueError(f"invalid season window for {lg}/{season_year}: {start!r} .. {end!r}")
    _WINDOW_CACHE[(lg, int(season_year))] = (start_d, end_d)
    season_window.cache_clear()


def register_season_window_from_espn_payload(league: str, payload: Mapping[str, Any]) -> int | None:
    """Extract year/start/end from a core ``seasons/{year}`` JSON document."""
    if not isinstance(payload, Mapping):
        return None
    year = payload.get("year")
    if year is None:
        return None
    start = payload.get("startDate")
    end = payload.get("endDate")
    if not start or not end:
        return None
    register_season_window(league, int(year), start=str(start), end=str(end))
    return int(year)


@lru_cache(maxsize=512)
def season_window(league: str, season_year: int) -> tuple[date, date]:
    """Return (start, end) for a league season year.

    Prefer cached ESPN windows; otherwise synthesize a conservative window from
    the league's year convention (verified against WP0 seeds for nearby years).
    """
    lg = normalize_league(league)
    year = int(season_year)
    cached = _WINDOW_CACHE.get((lg, year))
    if cached:
        return cached

    if lg in _SPLIT_LEAGUES:
        # NBA/NCAAB: roughly Oct (year-1) → June (year)
        start = date(year - 1, 10, 1)
        end = date(year, 6, 30)
    elif lg == "wnba":
        start = date(year, 5, 1)
        end = date(year, 10, 20)
    elif lg in {"nfl", "cfb"}:
        # NFL: Aug → Feb(+1); CFB window is wide (Feb → Jan+1) per ESPN.
        if lg == "cfb":
            start = date(year, 2, 1)
            end = date(year + 1, 1, 28)
        else:
            start = date(year, 8, 1)
            end = date(year + 1, 2, 15)
    else:
        start = date(year, 1, 1)
        end = date(year, 12, 31)
    return start, end


def season_label(league: str, season_year: int) -> str:
    """Human label for a stored season_year."""
    lg = normalize_league(league)
    year = int(season_year)
    if lg in _SPLIT_LEAGUES:
        start = year - 1
        return f"{start}-{year % 100:02d}"
    return str(year)


def parse_season_label(league: str, label: str | int | float) -> int:
    """Parse a human / ESPN label to stored ``season_year``.

    ``\"2003-04\"`` → ``2004`` for nba; ``\"2026\"`` → ``2026`` for nfl/cfb.
    Accepts pre-2000 four-digit years (unlike the old ``20\\d{2}`` regex).
    """
    lg = normalize_league(league)

    if isinstance(label, bool):
        raise TypeError("season label cannot be bool")
    if isinstance(label, (int, float)):
        year = int(label)
        if year < 1800 or year > 2100:
            raise ValueError(f"out-of-range season year: {year}")
        return year

    text = str(label or "").strip()
    if not text:
        raise ValueError("empty season label")

    split = _SPLIT_RE.match(text)
    if split:
        start = int(split.group("start"))
        end_raw = split.group("end")
        end = int(end_raw) if len(end_raw) == 4 else (start // 100) * 100 + int(end_raw)
        # Handle ``1999-00`` → end 2000
        if len(end_raw) == 2 and end < start:
            end += 100
        if lg in _SPLIT_LEAGUES:
            return end
        if lg in _CALENDAR_LEAGUES:
            return start
        return end

    years = [int(m.group(1)) for m in _YEAR_RE.finditer(text)]
    if not years:
        raise ValueError(f"no year in season label: {text!r}")
    if lg in _SPLIT_LEAGUES and len(years) >= 2:
        return max(years)
    return years[0]


def season_status(league: str, season_year: int, on: date) -> SeasonStatus:
    """Whether ``season_year`` is complete / in_progress / future on ``on``."""
    start, end = season_window(league, season_year)
    if on < start:
        return "future"
    if on > end:
        return "complete"
    return "in_progress"


def current_season_year(league: str, on: date) -> int:
    """ESPN/stored season year that is in progress on ``on``.

    If the date falls between seasons, returns the next future season year
    (off-season prep), matching ESPN tip-off conventions verified in WP0.
    """
    lg = normalize_league(league)

    if lg in _SPLIT_LEAGUES:
        candidates = [on.year - 1, on.year, on.year + 1, on.year + 2]
    else:
        candidates = [on.year - 1, on.year, on.year + 1]

    in_progress = [
        y for y in candidates if season_status(lg, y, on) == "in_progress"
    ]
    if in_progress:
        return max(in_progress)

    future = [
        y for y in candidates if season_status(lg, y, on) == "future"
    ]
    if future:
        # Soonest future season.
        future.sort(key=lambda y: season_window(lg, y)[0])
        return future[0]

    complete = [
        y for y in candidates if season_status(lg, y, on) == "complete"
    ]
    if complete:
        return max(complete)

    # Absolute fallback.
    return on.year + 1 if lg in _SPLIT_LEAGUES and on.month >= 7 else on.year


def load_seed_windows_from_fixtures(fixtures_root: str | None = None) -> int:
    """Load ``seasons_*.json`` captures into the window cache. Returns count."""
    from pathlib import Path
    import json

    root = Path(fixtures_root) if fixtures_root else (
        Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "espn"
    )
    if not root.is_dir():
        return 0
    loaded = 0
    for path in root.glob("*/*/seasons_*.json"):
        league = path.parent.parent.name
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        # Strip capture meta
        if isinstance(payload, dict) and "_capture" in payload:
            payload = {k: v for k, v in payload.items() if k != "_capture"}
        if register_season_window_from_espn_payload(league, payload) is not None:
            loaded += 1
    return loaded


# Populate cache from fixtures when the package is imported (best-effort).
try:
    load_seed_windows_from_fixtures()
except Exception:
    pass


__all__ = [
    "SeasonStatus",
    "current_season_year",
    "load_seed_windows_from_fixtures",
    "normalize_league",
    "parse_season_label",
    "register_season_window",
    "register_season_window_from_espn_payload",
    "season_label",
    "season_status",
    "season_window",
]
