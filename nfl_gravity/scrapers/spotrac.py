"""Spotrac scraping adapter."""

from __future__ import annotations

import re
import time
from typing import Any, Dict, Optional

from .discovery import FirecrawlDiscovery
from .fallback import extract_with_llm
from .utils import AdapterResult, RequestManager, fields_with_values, log_request, to_int, utc_now_iso

CAREER_REGEX = re.compile(r"Career Earnings\D+\$([0-9,]+)", re.IGNORECASE)


def parse_career_earnings(text: str) -> Optional[int]:
    match = CAREER_REGEX.search(text)
    if not match:
        return None
    return to_int(match.group(1))


def fetch_spotrac_earnings(
    athlete: str,
    discovery: Optional[FirecrawlDiscovery] = None,
    session: Optional[RequestManager] = None,
    html: Optional[str] = None,
) -> AdapterResult:
    """Fetch Spotrac contract information for an athlete."""

    start = time.perf_counter()
    url: Optional[str] = None
    manager = session or RequestManager()
    try:
        discovery = discovery or FirecrawlDiscovery()
        url = discovery.discover(athlete, "https://www.spotrac.com", keyword="spotrac")
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
        earnings = parse_career_earnings(html)
        if earnings is None:
            fallback = extract_with_llm(html, ["career_earnings"])
            earnings = fallback.get("career_earnings") if isinstance(fallback, Dict) else None
        if earnings is not None:
            data["career_earnings"] = earnings

    timestamp = utc_now_iso()
    elapsed = (time.perf_counter() - start) * 1000
    log_request("spotrac", athlete, url, "success" if data else "empty", elapsed, list(fields_with_values(data)))
    return AdapterResult(data=data, url=url, timestamp=timestamp)


__all__ = ["fetch_spotrac_earnings", "parse_career_earnings"]
