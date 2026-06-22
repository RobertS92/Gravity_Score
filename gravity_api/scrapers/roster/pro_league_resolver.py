"""Resolve all NFL / NBA / WNBA teams from ESPN site API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from gravity_api.scrapers.clients.espn import SITE_LEAGUE_PATH, normalize_sport

logger = logging.getLogger(__name__)

ESPN_HEADERS = {"User-Agent": "GravityScrapers/1.0", "Accept": "application/json"}
PRO_SPORTS = ("nfl", "nba", "wnba")


def fetch_pro_league_entries(sport: str) -> list[dict[str, Any]]:
    sport = normalize_sport(sport)
    if sport not in PRO_SPORTS:
        return []
    league = SITE_LEAGUE_PATH.get(sport)
    if not league:
        return []
    url = f"https://site.api.espn.com/apis/site/v2/sports/{league}/teams?limit=100"
    try:
        with httpx.Client(timeout=30.0, headers=ESPN_HEADERS) as client:
            resp = client.get(url)
            if resp.status_code in (400, 404, 500):
                return []
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Pro league team fetch failed %s: %s", sport, exc)
        return []

    rows: list[dict[str, Any]] = []
    for block in data.get("sports") or []:
        for league_obj in block.get("leagues") or []:
            for team_wrap in league_obj.get("teams") or []:
                team = team_wrap.get("team") or team_wrap
                tid = str(team.get("id") or "").strip()
                if not tid:
                    continue
                rows.append(
                    {
                        "espn_team_id": tid,
                        "school_name": str(team.get("displayName") or team.get("name") or ""),
                        "conference": str(
                            (team.get("groups") or {}).get("parent", {}).get("name")
                            or team.get("abbreviation")
                            or ""
                        ),
                        "sport": sport,
                        "nil_market_rank": 50,
                    }
                )
    return rows


def fetch_all_pro_entries() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sport in PRO_SPORTS:
        out.extend(fetch_pro_league_entries(sport))
    return out
