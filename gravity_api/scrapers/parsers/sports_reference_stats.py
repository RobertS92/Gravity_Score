"""Parse season stat lines from Sports Reference HTML (fallback when ESPN empty)."""

from __future__ import annotations

import logging
import re
import urllib.parse
from html import unescape
from datetime import datetime, timezone
from typing import Any

from gravity_api.scrapers.parsers.sports_reference import ref_domain_for_sport
from gravity_api.scrapers.parsers.stat_catalog import all_stat_keys_for_sport

logger = logging.getLogger(__name__)

_SR_DIRECT_SEARCH: dict[str, str] = {
    "cfb": "https://www.sports-reference.com/cfb/search/search.fcgi?search={query}",
    "ncaab_mens": "https://www.sports-reference.com/cbb/search/search.fcgi?search={query}",
    "ncaab_womens": "https://www.sports-reference.com/cbb/search/search.fcgi?search={query}",
    "nfl": "https://www.pro-football-reference.com/search/search.fcgi?search={query}",
}

_SR_BASE: dict[str, str] = {
    "cfb": "https://www.sports-reference.com",
    "ncaab_mens": "https://www.sports-reference.com",
    "ncaab_womens": "https://www.sports-reference.com",
    "nfl": "https://www.pro-football-reference.com",
}

# Label aliases in SR tables -> canonical keys (sport-specific overrides applied in parser).
_LABEL_ALIASES: dict[str, str] = {
    "g": "gp",
    "gs": "gs",
    "games": "gp",
    "gp": "gp",
    "pass yds": "pass_yards",
    "passing yds": "pass_yards",
    "pass yd": "pass_yards",
    "pass td": "pass_td",
    "pass tds": "pass_td",
    "rush yds": "rush_yards",
    "rush yd": "rush_yards",
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

_PLAYER_LINK_RE = re.compile(
    r'href="(?P<path>/[a-z]+/players/[a-z]/[a-z0-9\-]+\.html)"',
    re.I,
)


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


def _canon_label(label: str, sport: str) -> str | None:
    aliases = _label_aliases_for_sport(sport)
    keys = all_stat_keys_for_sport(sport)
    norm = _normalize_label(label)
    # Explicit Sports Reference aliases are trusted canonical fields even when
    # the model's position-specific feature catalog does not consume that raw
    # counting stat directly. Keeping them lets downstream normalizers derive
    # rates (for example pass yards per attempt) from fallback HTML tables.
    if norm in aliases:
        return aliases[norm]
    canon = norm.replace(" ", "_")
    if canon in keys or canon.replace("_", "") in {k.replace("_", "") for k in keys}:
        return canon
    if canon in ("gp", "gs", "min"):
        return canon
    return None


def _basic_table_rows(html: str) -> list[list[str]]:
    """Extract table rows without optional BeautifulSoup.

    Railway/API CI intentionally installs only runtime requirements. This
    fallback keeps simple Sports Reference tables parseable when bs4 is absent.
    """
    tables = re.findall(r"<table\b[^>]*>(.*?)</table>", html, flags=re.I | re.S)
    for table in tables:
        rows: list[list[str]] = []
        for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, flags=re.I | re.S):
            cells = []
            for cell_html in re.findall(
                r"<(?:th|td)\b[^>]*>(.*?)</(?:th|td)>", row_html, flags=re.I | re.S
            ):
                text = re.sub(r"<[^>]+>", " ", cell_html)
                cells.append(re.sub(r"\s+", " ", unescape(text)).strip())
            if cells:
                rows.append(cells)
        if len(rows) >= 2:
            return rows
    return []


def _merge_table_rows(season: dict[str, float], rows: list[list[str]], sport: str) -> None:
    if len(rows) < 2:
        return
    headers = rows[0]
    data_row = next(
        (cells for cells in reversed(rows[1:]) if len(cells) >= 2 and any(re.search(r"\d", c) for c in cells)),
        None,
    )
    if not data_row:
        return
    for label, val_s in zip(headers, data_row):
        canon = _canon_label(label, sport)
        if not canon:
            continue
        try:
            value = float(val_s.replace(",", ""))
        except ValueError:
            continue
        if value >= 0:
            season[canon] = value


def parse_sports_ref_stats_from_html(sport: str, html: str) -> dict[str, Any]:
    """Parse current-season stats from SR player page HTML."""
    if not html:
        return {}

    season: dict[str, float] = {}

    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        tables = soup.select("table#stats, table#stats_standard, table.stats_table")
        if not tables:
            tables = soup.find_all("table", class_=re.compile(r"stats", re.I))
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            header_cells = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
            data_row = None
            for row in reversed(rows[1:]):
                cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                if len(cells) >= 2 and any(re.search(r"\d", c) for c in cells):
                    data_row = cells
                    break
            if not data_row or not header_cells:
                continue
            n = min(len(header_cells), len(data_row))
            for label, val_s in zip(header_cells[:n], data_row[:n]):
                canon = _canon_label(label, sport)
                if not canon:
                    continue
                try:
                    val = float(val_s.replace(",", ""))
                except ValueError:
                    continue
                if val >= 0:
                    season[canon] = val
            if len(season) >= 3:
                break
    except Exception as exc:
        logger.debug("bs4 SR parse failed: %s", exc)

    if not season:
        _merge_table_rows(season, _basic_table_rows(html), sport)

    if not season:
        from gravity_api.scrapers.clients.http_fetch import html_to_markdownish

        return parse_sports_ref_stats_from_markdown(sport, html_to_markdownish(html))

    return _pack_season_stats(season)


def parse_sports_ref_stats_from_markdown(sport: str, text: str) -> dict[str, Any]:
    """Best-effort parse of current-season stats from SR page markdown."""
    if not text:
        return {}
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
        canon = _canon_label(label, sport)
        if not canon:
            continue
        try:
            val = float(val_s.replace(",", ""))
        except ValueError:
            continue
        if val >= 0:
            season[canon] = val
    if not season:
        return {}
    return _pack_season_stats(season)


def _pack_season_stats(season: dict[str, float]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "season_stats": season,
        "stats_source": "sports_reference",
        "stats_as_of": datetime.now(timezone.utc).date().isoformat(),
    }
    if season.get("gp"):
        out["games_played_season"] = int(season["gp"])
    return out


def extract_player_url_from_search_html(sport: str, html: str, name: str) -> str | None:
    """Pick best player page link from SR search results HTML."""
    if not html:
        return None
    base = _SR_BASE.get(sport, "https://www.sports-reference.com")
    name_parts = [p.lower() for p in name.split() if p]
    candidates: list[str] = []
    for m in _PLAYER_LINK_RE.finditer(html):
        path = m.group("path")
        if name_parts and not all(p in path.lower() for p in name_parts[:2]):
            continue
        candidates.append(f"{base}{path}")
    if candidates:
        return candidates[0]
    # fallback: first player link
    m = _PLAYER_LINK_RE.search(html)
    if m:
        return f"{base}{m.group('path')}"
    return None


async def fetch_sports_ref_stats(
    sport: str,
    name: str,
    school: str | None = None,
) -> dict[str, Any]:
    """Fetch stats via direct HTTP: search page → player page → HTML parse."""
    from gravity_api.scrapers.clients.http_fetch import HttpFetchClient

    search_url = sports_ref_search_url(name, sport, school)
    if not search_url:
        return {}

    http = HttpFetchClient()
    try:
        search_html = await http.fetch_html(search_url)
    except Exception as exc:
        logger.debug("SR search fetch failed %s: %s", search_url, exc)
        return {}

    player_url = extract_player_url_from_search_html(sport, search_html, name)
    if not player_url:
        # search page may already be player page on exact match redirect
        if "/players/" in search_url:
            player_url = search_url
        else:
            parsed = parse_sports_ref_stats_from_html(sport, search_html)
            return parsed if parsed.get("season_stats") else {}

    try:
        player_html = await http.fetch_html(player_url)
    except Exception as exc:
        logger.debug("SR player fetch failed %s: %s", player_url, exc)
        return {}

    return parse_sports_ref_stats_from_html(sport, player_html)


def count_position_stats(season: dict[str, float], sport: str) -> int:
    keys = all_stat_keys_for_sport(sport) - {"games_played_season", "gp", "gs"}
    return sum(1 for k in keys if season.get(k))
