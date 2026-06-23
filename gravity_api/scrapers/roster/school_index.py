"""School / team index for roster sync — Power 4 college + pro leagues."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import TypedDict

logger = logging.getLogger(__name__)


class SchoolEntry(TypedDict, total=False):
    espn_team_id: str
    school_name: str
    conference: str
    sport: str
    nil_market_rank: int


_STATIC_SAMPLE: list[SchoolEntry] = [
    {"espn_team_id": "61", "school_name": "Georgia", "conference": "SEC", "sport": "cfb"},
    {"espn_team_id": "333", "school_name": "Alabama", "conference": "SEC", "sport": "cfb"},
    {"espn_team_id": "150", "school_name": "Duke", "conference": "ACC", "sport": "ncaab_mens"},
    {
        "espn_team_id": "399",
        "school_name": "South Carolina",
        "conference": "SEC",
        "sport": "ncaab_womens",
    },
]

_resolved: list[SchoolEntry] | None = None

COLLEGE_ROSTER_SPORTS = (
    "cfb",
    "ncaab_mens",
    "ncaab_womens",
    "ncaa_baseball",
    "ncaa_volleyball",
)
PRO_ROSTER_SPORTS = ("nfl", "nba", "wnba")
DEFAULT_ROSTER_SPORTS = COLLEGE_ROSTER_SPORTS + PRO_ROSTER_SPORTS


def _season_year_for_cfb() -> int:
    raw = (
        os.getenv("POWER5_CFB_SEASON")
        or os.getenv("CURRENT_STATS_SEASON")
        or os.getenv("SCRAPE_SEASON")
        or ""
    ).strip()
    if raw:
        return int(raw.split("-")[0] if "-" in raw else raw)
    return datetime.now(timezone.utc).year


def _resolve_entries() -> list[SchoolEntry]:
    if os.getenv("POWER5_USE_STATIC_SAMPLE", "").strip().lower() in ("1", "true", "yes"):
        return list(_STATIC_SAMPLE)

    from gravity_api.scrapers.roster.power5_resolver import fetch_all_power5_entries
    from gravity_api.scrapers.roster.pro_league_resolver import fetch_all_pro_entries

    year = _season_year_for_cfb()
    rows: list[SchoolEntry] = []
    try:
        for r in fetch_all_power5_entries(season_year=year):
            rows.append(
                {
                    "espn_team_id": str(r["espn_team_id"]),
                    "school_name": str(r.get("school_name") or ""),
                    "conference": str(r.get("conference") or ""),
                    "sport": str(r["sport"]),
                }
            )
        for r in fetch_all_pro_entries():
            rows.append(
                {
                    "espn_team_id": str(r["espn_team_id"]),
                    "school_name": str(r.get("school_name") or ""),
                    "conference": str(r.get("conference") or ""),
                    "sport": str(r["sport"]),
                }
            )
    except Exception:
        logger.exception("ESPN school index resolve failed; using static sample")
        return list(_STATIC_SAMPLE)

    if not rows:
        logger.warning("ESPN school index empty; using static sample")
        return list(_STATIC_SAMPLE)

    cfb_n = sum(1 for e in rows if e.get("sport") == "cfb")
    if cfb_n < 20:
        logger.warning("CFB index looks incomplete (%s teams); using static sample", cfb_n)
        return list(_STATIC_SAMPLE)
    return rows


def _all_entries() -> list[SchoolEntry]:
    global _resolved
    if _resolved is None:
        _resolved = _resolve_entries()
    return _resolved


def clear_school_index_cache() -> None:
    global _resolved
    _resolved = None


def schools_for_sport(sport: str) -> list[SchoolEntry]:
    s = (sport or "").lower().strip()
    if s == "mcbb":
        s = "ncaab_mens"
    if s == "wcbb":
        s = "ncaab_womens"
    return [e for e in _all_entries() if e.get("sport") == s]


def all_sports_in_index() -> list[str]:
    seen: list[str] = []
    for e in _all_entries():
        sp = e.get("sport")
        if sp and sp not in seen:
            seen.append(sp)
    return seen


def default_team_ids_for_sport(sport: str) -> list[str]:
    raw = (os.getenv("ROSTER_SYNC_DEFAULT_TEAM_IDS") or "").strip()
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    return [str(s["espn_team_id"]) for s in schools_for_sport(sport)]
