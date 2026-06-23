"""Resolve Power 4 baseball / volleyball teams via ESPN slug + name matching."""

from __future__ import annotations

import logging
import re
from typing import Any

from gravity_api.scrapers.roster.power5_resolver import (
    ESPN_HEADERS,
    HOOPS_CONFERENCE_ABBREVS,
    _fetch_json,
    _walk_hoops_conference_teams,
)

logger = logging.getLogger(__name__)

MBB_GROUPS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/groups"
)
WBB_GROUPS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/groups"
)

BASEBALL_TEAMS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/teams?limit=500"
)
VOLLEYBALL_TEAMS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/volleyball/womens-college-volleyball/teams?limit=500"
)

DEFAULT_MARKET_RANK = 50


def _normalize_display_key(name: str) -> str:
    n = (name or "").lower()
    for token in (
        " lady ",
        " cowgirls",
        " cowboys",
        " crimson tide",
        " fighting irish",
        " yellow jackets",
        " blue devils",
        " red raiders",
        " nittany lions",
        " golden bears",
        " tar heels",
        " volunteer",
        " volunteers",
    ):
        n = n.replace(token, " ")
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())


def _slug_variants(slug: str) -> list[str]:
    if not slug:
        return []
    variants = [slug]
    alt = (
        slug.replace("-lady-", "-")
        .replace("-cowgirls", "-cowboys")
        .replace("-lady-raiders", "-red-raiders")
        .replace("-lady-lions", "-nittany-lions")
        .replace("-lady-volunteers", "-volunteers")
        .replace("-lady-bulldogs", "-bulldogs")
    )
    if alt != slug:
        variants.append(alt)
    return variants


def _load_site_teams(url: str) -> tuple[dict[str, tuple[str, str]], dict[str, tuple[str, str]]]:
    """Return (by_slug, by_display_key) -> (team_id, display_name)."""
    data = _fetch_json(url)
    by_slug: dict[str, tuple[str, str]] = {}
    by_name: dict[str, tuple[str, str]] = {}
    for block in data.get("sports") or []:
        for league_obj in block.get("leagues") or []:
            for team_wrap in league_obj.get("teams") or []:
                team = team_wrap.get("team") or team_wrap
                tid = str(team.get("id") or "").strip()
                if not tid:
                    continue
                display = str(team.get("displayName") or team.get("name") or "").strip()
                slug = str(team.get("slug") or "").strip()
                if slug:
                    by_slug[slug] = (tid, display)
                key = _normalize_display_key(display)
                if key:
                    by_name[key] = (tid, display)
    return by_slug, by_name


def _power_hoops_entries(groups_url: str, sport_key: str) -> list[dict[str, Any]]:
    data = _fetch_json(groups_url) or {}
    acc: dict[str, dict[str, Any]] = {}
    _walk_hoops_conference_teams(data.get("groups") or data, sport_key, acc)
    return list(acc.values())


def _resolve_target_sport(
    power_rows: list[dict[str, Any]],
    *,
    target_sport: str,
    by_slug: dict[str, tuple[str, str]],
    by_name: dict[str, tuple[str, str]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in power_rows:
        slug = str(row.get("slug") or "").strip()
        display = str(row.get("school_name") or row.get("displayName") or "").strip()
        matched: tuple[str, str] | None = None
        for variant in _slug_variants(slug):
            if variant in by_slug:
                matched = by_slug[variant]
                break
        if not matched:
            key = _normalize_display_key(display)
            matched = by_name.get(key)
        if not matched:
            logger.debug("No %s team match for %s (%s)", target_sport, display, slug)
            continue
        tid, tname = matched
        if tid in seen:
            continue
        seen.add(tid)
        out.append(
            {
                "espn_team_id": tid,
                "school_name": tname,
                "conference": str(row.get("conference") or ""),
                "sport": target_sport,
                "nil_market_rank": DEFAULT_MARKET_RANK,
            }
        )
    return out


def fetch_ncaa_baseball_power_entries() -> list[dict[str, Any]]:
    power = _power_hoops_entries(MBB_GROUPS_URL, "ncaab_mens")
    by_slug, by_name = _load_site_teams(BASEBALL_TEAMS_URL)
    rows = _resolve_target_sport(
        power,
        target_sport="ncaa_baseball",
        by_slug=by_slug,
        by_name=by_name,
    )
    logger.info("Resolved %d Power 4 ncaa_baseball teams (from %d MBB index)", len(rows), len(power))
    return rows


def fetch_ncaa_volleyball_power_entries() -> list[dict[str, Any]]:
    power = _power_hoops_entries(WBB_GROUPS_URL, "ncaab_womens")
    by_slug, by_name = _load_site_teams(VOLLEYBALL_TEAMS_URL)
    rows = _resolve_target_sport(
        power,
        target_sport="ncaa_volleyball",
        by_slug=by_slug,
        by_name=by_name,
    )
    logger.info(
        "Resolved %d Power 4 ncaa_volleyball teams (from %d WBB index)",
        len(rows),
        len(power),
    )
    return rows
