"""Resolve Power 4 (+ Notre Dame CFB) schools from ESPN public APIs."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CFB_CONFERENCE_GROUPS: tuple[tuple[int, str], ...] = (
    (1, "ACC"),
    (4, "Big 12"),
    (5, "Big Ten"),
    (8, "SEC"),
)

HOOPS_CONFERENCE_ABBREVS: dict[str, str] = {
    "acc": "ACC",
    "big12": "Big 12",
    "big10": "Big Ten",
    "sec": "SEC",
}

_TEAM_ID_FROM_REF = re.compile(r"/teams/(\d+)", re.IGNORECASE)

CFB_CORE_TEAMS_TMPL = (
    "https://sports.core.api.espn.com/v2/sports/football/leagues/college-football"
    "/seasons/{year}/types/0/groups/{group_id}/teams?limit=200"
)
MBB_GROUPS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/groups"
)
WBB_GROUPS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/groups"
)

NOTRE_DAME_CFB_TEAM_ID = "87"
DEFAULT_MARKET_RANK = 50
ESPN_HEADERS = {"User-Agent": "GravityScrapers/1.0", "Accept": "application/json"}


def _fetch_json(url: str) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=30.0, headers=ESPN_HEADERS) as client:
            resp = client.get(url)
            if resp.status_code in (400, 404, 500):
                return {}
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("ESPN fetch failed %s: %s", url, exc)
        return {}


def _team_ids_from_cfb_group(year: int, group_id: int) -> list[str]:
    url = CFB_CORE_TEAMS_TMPL.format(year=year, group_id=group_id)
    data = _fetch_json(url)
    out: list[str] = []
    for item in data.get("items") or []:
        ref = item.get("$ref") or ""
        m = _TEAM_ID_FROM_REF.search(ref)
        if m:
            out.append(m.group(1))
    return out


def fetch_cfb_power_entries(*, season_year: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for gid, cname in CFB_CONFERENCE_GROUPS:
        for tid in _team_ids_from_cfb_group(season_year, gid):
            if tid in seen:
                continue
            seen.add(tid)
            rows.append(
                {
                    "espn_team_id": tid,
                    "school_name": "",
                    "conference": cname,
                    "sport": "cfb",
                    "nil_market_rank": DEFAULT_MARKET_RANK,
                }
            )
    if NOTRE_DAME_CFB_TEAM_ID not in seen:
        rows.append(
            {
                "espn_team_id": NOTRE_DAME_CFB_TEAM_ID,
                "school_name": "Notre Dame Fighting Irish",
                "conference": "Independent",
                "sport": "cfb",
                "nil_market_rank": DEFAULT_MARKET_RANK,
            }
        )
    return rows


def _walk_hoops_conference_teams(
    obj: Any,
    sport_key: str,
    accum: dict[str, dict[str, Any]],
) -> None:
    if isinstance(obj, dict):
        abb = (obj.get("abbreviation") or "").lower()
        teams = obj.get("teams")
        if abb in HOOPS_CONFERENCE_ABBREVS and isinstance(teams, list):
            cname = HOOPS_CONFERENCE_ABBREVS[abb]
            for t in teams:
                if not isinstance(t, dict):
                    continue
                tid = str(t.get("id") or "").strip()
                if not tid:
                    continue
                name = str(t.get("displayName") or t.get("name") or "").strip()
                slug = str(t.get("slug") or "").strip()
                accum[tid] = {
                    "espn_team_id": tid,
                    "school_name": name,
                    "slug": slug,
                    "conference": cname,
                    "sport": sport_key,
                    "nil_market_rank": DEFAULT_MARKET_RANK,
                }
        for v in obj.values():
            _walk_hoops_conference_teams(v, sport_key, accum)
    elif isinstance(obj, list):
        for x in obj:
            _walk_hoops_conference_teams(x, sport_key, accum)


def fetch_mens_power4_entries() -> list[dict[str, Any]]:
    data = _fetch_json(MBB_GROUPS_URL) or {}
    acc: dict[str, dict[str, Any]] = {}
    _walk_hoops_conference_teams(data.get("groups") or data, "ncaab_mens", acc)
    return list(acc.values())


def fetch_womens_power4_entries() -> list[dict[str, Any]]:
    data = _fetch_json(WBB_GROUPS_URL) or {}
    acc: dict[str, dict[str, Any]] = {}
    _walk_hoops_conference_teams(data.get("groups") or data, "ncaab_womens", acc)
    return list(acc.values())


def fetch_all_power5_entries(*, season_year: int) -> list[dict[str, Any]]:
    from gravity_api.scrapers.roster.college_sport_resolver import (
        fetch_ncaa_baseball_power_entries,
        fetch_ncaa_volleyball_power_entries,
    )

    out: list[dict[str, Any]] = []
    out.extend(fetch_cfb_power_entries(season_year=season_year))
    out.extend(fetch_mens_power4_entries())
    out.extend(fetch_womens_power4_entries())
    out.extend(fetch_ncaa_baseball_power_entries())
    out.extend(fetch_ncaa_volleyball_power_entries())
    return out
