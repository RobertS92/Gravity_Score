"""Wikipedia scraping adapter."""

from __future__ import annotations

import re
import time
from typing import Any, Dict, Iterable, Optional

from bs4 import BeautifulSoup

from .discovery import FirecrawlDiscovery
from .fallback import extract_with_llm
from .utils import AdapterResult, RequestManager, fields_with_values, log_request, utc_now_iso

INFOBOX_FIELDS = {
    "position": "position",
    "born": "born",
    "height": "height",
    "weight": "weight",
    "college": "college",
    "career highlights and awards": "awards",
}

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _parse_birthdate(text: str) -> Optional[str]:
    match = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", text)
    if not match:
        return None
    month = MONTHS.get(match.group(1).lower())
    if not month:
        return None
    day = int(match.group(2))
    year = int(match.group(3))
    return f"{year:04d}-{month:02d}-{day:02d}"


def _parse_age(text: str) -> Optional[int]:
    match = re.search(r"age\s+(\d+)", text)
    return int(match.group(1)) if match else None


def _parse_height(text: str) -> Optional[str]:
    match = re.search(r"(\d+)\s*ft\s*(\d+)\s*in", text)
    if match:
        return f"{match.group(1)} ft {match.group(2)} in"
    return text.strip() or None


def _parse_weight(text: str) -> Optional[int]:
    match = re.search(r"(\d+)\s*lb", text)
    if match:
        return int(match.group(1))
    return None


def parse_infobox(soup: BeautifulSoup) -> Dict[str, Any]:
    """Parse standard infobox rows."""

    table = soup.find("table", class_="infobox")
    if table is None:
        return {}

    data: Dict[str, Any] = {}
    for row in table.find_all("tr"):
        header = row.find("th")
        value = row.find("td")
        if not header or not value:
            continue
        label = header.get_text(" ", strip=True).lower()
        text = " ".join(value.stripped_strings)
        field = INFOBOX_FIELDS.get(label)
        if not field:
            continue
        if field == "born":
            data["birthdate"] = _parse_birthdate(text)
            age = _parse_age(text)
            if age is not None:
                data["age"] = age
        elif field == "height":
            data["height"] = _parse_height(text)
        elif field == "weight":
            data["weight"] = _parse_weight(text)
        elif field == "awards":
            items = row.find_all("li")
            if items:
                data["awards_count"] = len(items)
        else:
            data[field] = text.strip()

    if "awards_count" not in data:
        highlights = table.find("tr", string=re.compile("Career highlights"))
        if highlights and highlights.find_next("td"):
            items = highlights.find_next("td").find_all("li")
            if items:
                data["awards_count"] = len(items)

    return data


def _needs_fallback(data: Dict[str, Any], expected: Iterable[str]) -> Iterable[str]:
    return [field for field in expected if data.get(field) in (None, "")]


def fetch_wikipedia_profile(
    athlete: str,
    discovery: Optional[FirecrawlDiscovery] = None,
    session: Optional[RequestManager] = None,
    html: Optional[str] = None,
) -> AdapterResult:
    """Fetch and parse Wikipedia information for an athlete."""

    start = time.perf_counter()
    url: Optional[str] = None
    manager = session or RequestManager()
    try:
        discovery = discovery or FirecrawlDiscovery()
        url = discovery.discover(athlete, "https://en.wikipedia.org", keyword="wikipedia")
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
        data = parse_infobox(soup)
        required = ["age", "position", "height", "weight", "college", "birthdate", "awards_count"]
        missing = _needs_fallback(data, required)
        if missing:
            fallback_values = extract_with_llm(str(soup), missing)
            data.update({k: v for k, v in fallback_values.items() if v is not None})

    timestamp = utc_now_iso()
    elapsed = (time.perf_counter() - start) * 1000
    log_request("wikipedia", athlete, url, "success" if data else "empty", elapsed, fields_with_values(data))
    return AdapterResult(data=data, url=url, timestamp=timestamp)


__all__ = ["fetch_wikipedia_profile", "parse_infobox"]
