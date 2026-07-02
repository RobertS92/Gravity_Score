"""Parse season stat lines from Sports Reference markdown (fallback when ESPN empty)."""

from __future__ import annotations

import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any

from gravity_api.scrapers.parsers.sports_reference import ref_domain_for_sport
from gravity_api.scrapers.parsers.stat_catalog import all_stat_keys_for_sport

_SR_DIRECT_SEARCH: dict[str, str] = {
    "cfb": "https://www.sports-reference.com/cfb/search/search.fcgi?search={query}",
    "ncaab_mens": "https://www.sports-reference.com/cbb/search/search.fcgi?search={query}",
    "ncaab_womens": "https://www.sports-reference.com/cbb/search/search.fcgi?search={query}",
    "nfl": "https://www.pro-football-reference.com/search/search.fcgi?search={query}",
}

# Label aliases in SR tables -> canonical keys (sport-specific overrides applied in parser).
_LABEL_ALIASES: dict[str, str] = {
    "g": "gp",
    "gs": "gs",
    "games": "gp",
    "gp": "gp",
    "pass yds": "pass_yards",
    "passing yds": "pass_yards",
    "pass td": "pass_td",
    "pass tds": "pass_td",
    "rush yds": "rush_yards",
    "rec yds": "rec_yards",
    "rec": "receptions",
    "rec td": "rec_td",
    "rec tds": "rec_td",
    "tackles": "tackles",
    "solo": "solo_tackles",
    "sacks": "sacks",
    "int": "interceptions",
    "pts": "pts",
    "points": "pts",
    "reb": "reb",
    "rebounds": "reb",
    "assists": "ast",
    "stl": "stl",
    "steals": "stl",
    "blk": "blk",
    "blocks": "blk",
    "fg%": "fg_pct",
    "3p%": "three_pct",
    "ft%": "ft_pct",
    "min": "min",
    "mp": "min",
}


def _label_aliases_for_sport(sport: str) -> dict[str, str]:
    aliases = dict(_LABEL_ALIASES)
    if sport in {"cfb", "nfl"}:
        aliases["ast"] = "assist_tackles"
    else:
        aliases["ast"] = "ast"
    return aliases


def sports_ref_google_search_url(name: str, sport: str, school: str | None = None) -> str | None:
    domain = ref_domain_for_sport(sport)
    if not domain:
        return None
    parts = [f'"{name}"']
    if school:
        parts.append(f'"{school}"')
    parts.append(f"site:{domain}")
    q = " ".join(parts)
    return f"https://www.google.com/search?q={urllib.parse.quote(q)}"


def sports_ref_search_url(name: str, sport: str, school: str | None = None) -> str | None:
    """Direct Sports Reference search URL; Google site search as fallback."""
    direct = _SR_DIRECT_SEARCH.get(sport)
    query = name.strip()
    if school:
        query = f"{query} {school.strip()}"
    if direct:
        return direct.format(query=urllib.parse.quote(query))
    return sports_ref_google_search_url(name, sport, school)


def _normalize_label(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip().lower())


def parse_sports_ref_stats_from_markdown(sport: str, text: str) -> dict[str, Any]:
    """Best-effort parse of current-season stats from SR page markdown."""
    if not text:
        return {}
    keys = all_stat_keys_for_sport(sport)
    aliases = _label_aliases_for_sport(sport)
    season: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) > 200:
            continue
        m = re.match(r"^([A-Za-z0-9%\.]+(?:\s+[A-Za-z0-9%\.]+)?)\s+([\d,\.]+)\s*$", line)
        if not m:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= 2:
                label, val_s = cells[0], cells[-1]
            else:
                continue
        else:
            label, val_s = m.group(1), m.group(2)
        canon = aliases.get(_normalize_label(label), _normalize_label(label).replace(" ", "_"))
        if canon not in keys and canon.replace("_", "") not in {k.replace("_", "") for k in keys}:
            if canon not in ("gp", "gs", "min"):
                continue
        try:
            val = float(val_s.replace(",", ""))
        except ValueError:
            continue
        if val >= 0:
            season[canon] = val
    if not season:
        return {}
    return {
        "season_stats": season,
        "stats_source": "sports_reference",
        "stats_as_of": datetime.now(timezone.utc).date().isoformat(),
    }


def count_position_stats(season: dict[str, float], sport: str) -> int:
    keys = all_stat_keys_for_sport(sport) - {"games_played_season", "gp", "gs"}
    return sum(1 for k in keys if season.get(k))
