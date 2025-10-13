"""Pro-Football-Reference scraping adapter."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup

from .discovery import FirecrawlDiscovery
from .utils import AdapterResult, RequestManager, fields_with_values, log_request, utc_now_iso


STAT_FIELDS = {
    "passing": ["pass_yds", "pass_td", "pass_cmp", "pass_att"],
    "rushing_and_receiving": ["rush_yds", "rec_yds", "rush_td", "rec_td", "rush_att"],
    "defense": ["tackle_comb", "sk", "int"],
    "kicking": ["fgm", "xpm"],
    "returns": ["kick_ret", "punt_ret"]
}


def _parse_numeric(cell: Optional[Any]) -> Optional[float]:
    if cell is None:
        return None
    text = getattr(cell, "text", "") or ""
    text = text.replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_career_tables(soup: BeautifulSoup) -> Dict[str, Any]:
    """Parse career aggregates across PFR stat tables."""

    data: Dict[str, Any] = {}
    totals = {
        "career_yards": 0.0,
        "total_touchdowns": 0.0,
        "career_sacks": 0.0,
        "career_interceptions": 0.0,
    }

    for table_id, stat_names in STAT_FIELDS.items():
        table = soup.find("table", id=table_id)
        if table is None:
            continue
        career_row = table.find("tr", id="Career")
        if career_row is None:
            continue
        table_data: Dict[str, Optional[float]] = {}
        for stat in stat_names:
            cell = career_row.find("td", attrs={"data-stat": stat})
            table_data[stat] = _parse_numeric(cell)
        data[table_id] = table_data

        if table_id == "passing":
            totals["career_yards"] += table_data.get("pass_yds") or 0.0
            totals["total_touchdowns"] += table_data.get("pass_td") or 0.0
        if table_id == "rushing_and_receiving":
            totals["career_yards"] += (table_data.get("rush_yds") or 0.0) + (table_data.get("rec_yds") or 0.0)
            totals["total_touchdowns"] += (table_data.get("rush_td") or 0.0) + (table_data.get("rec_td") or 0.0)
        if table_id == "defense":
            totals["career_sacks"] = table_data.get("sk") or totals["career_sacks"]
            totals["career_interceptions"] = table_data.get("int") or totals["career_interceptions"]
            data["career_tackles"] = table_data.get("tackle_comb")

    for key, value in totals.items():
        if value is None:
            continue
        if key == "career_sacks":
            data[key] = float(value)
        else:
            data[key] = int(round(value))
    if "career_tackles" in data and data["career_tackles"] is not None:
        data["career_tackles"] = float(data["career_tackles"])
    return data


def fetch_pfr_career(
    athlete: str,
    discovery: Optional[FirecrawlDiscovery] = None,
    session: Optional[RequestManager] = None,
    html: Optional[str] = None,
) -> AdapterResult:
    """Fetch PFR career stats for an athlete."""

    url: Optional[str] = None
    start = time.perf_counter()
    manager = session or RequestManager()
    try:
        discovery = discovery or FirecrawlDiscovery()
        url = discovery.discover(athlete, "https://www.pro-football-reference.com", keyword="pfr")
    except Exception:
        url = None

    data: Dict[str, Any] = {}
    if url and html is None:
        try:
            response = manager.get(url)
            html = response.text
        except Exception:
            html = None
    if html:
        soup = BeautifulSoup(html, "lxml")
        data = parse_career_tables(soup)

    timestamp = utc_now_iso()
    elapsed = (time.perf_counter() - start) * 1000
    log_request("pfr", athlete, url, "success" if data else "empty", elapsed, list(fields_with_values(data)))
    return AdapterResult(data=data, url=url, timestamp=timestamp)


__all__ = ["fetch_pfr_career", "parse_career_tables"]
