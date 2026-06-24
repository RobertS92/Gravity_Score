"""Opendorse marketplace profile parsing."""

from __future__ import annotations

import re
from typing import Any

from gravity_api.scrapers.parsers.common import parse_count, parse_money_usd
from gravity_api.scrapers.parsers.nil import parse_nil_from_text

_LISTING_PAT = re.compile(r"opendorse\.com/(?:athletes|a)/", re.I)
_ENGAGEMENT_PAT = re.compile(r"engagement[^\d.]*([\d.]+)\s*%?", re.I)
_FOLLOWERS_PAT = re.compile(
    r"(?:followers|social\s*reach)[^\d]*([\d,.]+[KMB]?)",
    re.I,
)


def parse_opendorse_profile(text: str) -> dict[str, Any]:
    """Extract NIL and marketplace signals from an Opendorse profile page."""
    out: dict[str, Any] = {}

    if _LISTING_PAT.search(text):
        out["marketplace_listing"] = True

    nil_val = parse_nil_from_text(text)
    if nil_val is None:
        for pat in (
            r"estimated\s*(?:value|earnings)[^\d$]*(\$[\d,.]+[KMB]?)",
            r"deal\s*value[^\d$]*(\$[\d,.]+[KMB]?)",
        ):
            m = re.search(pat, text, re.I)
            if m:
                nil_val = parse_money_usd(m.group(1))
                if nil_val:
                    break
    if nil_val:
        out["nil_valuation"] = float(nil_val)
        out["nil_valuation_source"] = "opendorse"

    m = _ENGAGEMENT_PAT.search(text)
    if m:
        try:
            out["engagement_rate"] = float(m.group(1))
        except ValueError:
            pass

    m = _FOLLOWERS_PAT.search(text)
    if m:
        followers = parse_count(m.group(1))
        if followers:
            out["social_metrics"] = {"followers": followers}

    return out


__all__ = ["parse_opendorse_profile"]
