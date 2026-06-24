"""Firecrawl site-search configs for sport-specific registry scrapers."""

from __future__ import annotations

import re
from typing import Callable

FloatParser = Callable[[str], dict[str, float]]


def _float_field(key: str, pattern: str) -> tuple[str, str]:
    return key, pattern


def _extract_floats(md: str, patterns: list[tuple[str, str]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, pat in patterns:
        m = re.search(pat, md, re.I)
        if not m:
            continue
        try:
            out[key] = float(m.group(1).replace(",", ""))
        except (TypeError, ValueError):
            continue
    return out


def _extract_rank(md: str, key: str, label: str) -> dict[str, float]:
    m = re.search(rf"{label}[^\d#]*#?\s*(\d{{1,4}})", md, re.I)
    if not m:
        m = re.search(rf"{label}[^\d]*(\d{{1,4}})", md, re.I)
    if m:
        return {key: float(m.group(1))}
    return {}


SITE_SEARCH_CONFIG: dict[str, dict] = {
    "her_hoop_stats": {
        "domain": "herhoopstats.com",
        "sport": "ncaab_womens",
        "parse": lambda md: _extract_floats(
            md,
            [
                _float_field("bpm", r"BPM[^\d-]*(-?[\d.]+)"),
                _float_field("usage", r"Usage[^\d]*([\d.]+)"),
                _float_field("pts", r"PPG[^\d]*([\d.]+)"),
                _float_field("reb", r"RPG[^\d]*([\d.]+)"),
                _float_field("ast", r"APG[^\d]*([\d.]+)"),
            ],
        ),
    },
    "perfect_game_recruiting": {
        "domain": "perfectgame.org",
        "sport": "ncaa_baseball",
        "parse": lambda md: {
            **_extract_rank(md, "recruiting_rank_national", r"(?:National\s+Rank|Overall\s+Rank)"),
            **_extract_floats(md, [_float_field("pg_grade", r"PG\s*Grade[^\d]*([\d.]+)")]),
        },
    },
    "d1baseball_rankings": {
        "domain": "d1baseball.com",
        "sport": "ncaa_baseball",
        "parse": lambda md: _extract_rank(md, "d1baseball_rank", r"(?:Rank|Ranking)"),
    },
    "mlb_draft_pipeline": {
        "domain": "mlb.com",
        "sport": "ncaa_baseball",
        "parse": lambda md: _extract_rank(md, "draft_prospect_rank", r"(?:Prospect\s+Rank|Pipeline\s+Rank)"),
    },
    "avca_poll": {
        "domain": "avca.org",
        "sport": "ncaa_volleyball",
        "parse": lambda md: {
            **_extract_rank(md, "avca_rank", r"(?:AVCA\s+Rank|Poll\s+Rank)"),
            **_extract_floats(md, [_float_field("avca_poll_points", r"Points[^\d]*([\d.]+)")]),
        },
    },
    "prepvolleyball_recruiting": {
        "domain": "prepvolleyball.com",
        "sport": "ncaa_volleyball",
        "parse": lambda md: _extract_rank(md, "recruiting_rank_national", r"(?:National\s+Rank|Stars)"),
    },
    "avca_all_american": {
        "domain": "avca.org",
        "sport": "ncaa_volleyball",
        "parse": lambda md: {
            **_extract_floats(md, [_float_field("all_american_count", r"All[- ]American[^\d]*(\d+)")]),
        },
    },
    "fantasy_adp": {
        "domain": "fantasypros.com",
        "sport": "nfl",
        "parse": lambda md: _extract_floats(
            md,
            [
                _float_field("fantasy_adp", r"ADP[^\d]*([\d.]+)"),
                _float_field("fantasy_trend_30d", r"Trend[^\d-]*(-?[\d.]+)"),
            ],
        ),
    },
}


def site_suffix_for_key(scraper_key: str) -> str | None:
    for suffix in SITE_SEARCH_CONFIG:
        if scraper_key.startswith(f"{suffix}_") or scraper_key == suffix:
            return suffix
    return None


async def scrape_site_fields(
    fc,
    *,
    domain: str,
    name: str,
    team: str | None,
    parse: FloatParser,
) -> dict[str, float]:
    parts = [name.replace(" ", "+")]
    if team:
        parts.append(team.replace(" ", "+"))
    q = "+".join(parts)
    md = await fc.scrape_markdown(f"https://www.google.com/search?q=site:{domain}+{q}")
    return parse(md)


__all__ = ["SITE_SEARCH_CONFIG", "site_suffix_for_key", "scrape_site_fields"]
