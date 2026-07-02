"""Common parsing utilities."""

from __future__ import annotations

import re
from typing import Any

_HANDLE_BLOCKLIST = frozenset(
    {
        "p",
        "reel",
        "reels",
        "explore",
        "accounts",
        "popular",
        "intent",
        "share",
        "home",
        "stories",
        "tv",
        "about",
    }
)
_FOLLOWERS_RE = re.compile(
    r"([\d,.]+)\s*(K|M|B)?\s*(followers|subscriber|subscribers)",
    re.IGNORECASE,
)
_MONEY_RE = re.compile(r"\$?\s*([\d,.]+)\s*([KMBkmb])?", re.IGNORECASE)
_NUMBER_RE = re.compile(r"([\d,]+(?:\.\d+)?)")
_HANDLE_RE = re.compile(r"@([A-Za-z0-9._]{1,30})")


def parse_count(text: str | None) -> int | None:
    if not text:
        return None
    m = _FOLLOWERS_RE.search(text.replace(",", ""))
    if not m:
        m2 = _NUMBER_RE.search(text.replace(",", ""))
        if not m2:
            return None
        try:
            return int(float(m2.group(1)))
        except ValueError:
            return None
    num = float(m.group(1).replace(",", ""))
    suffix = (m.group(2) or "").upper()
    mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(suffix, 1)
    return int(num * mult)


def parse_money_usd(text: str | None) -> float | None:
    if not text:
        return None
    m = _MONEY_RE.search(text.replace(",", ""))
    if not m:
        return None
    num = float(m.group(1).replace(",", ""))
    suffix = (m.group(2) or "").upper()
    mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(suffix, 1)
    return num * mult


def extract_handles(text: str) -> dict[str, str]:
    """Extract social handles from markdown/html text."""
    out: dict[str, str] = {}
    lower = text.lower()
    for platform, patterns in (
        ("instagram", (r"instagram\.com/([A-Za-z0-9._]+)", r"ig:\s*@?([A-Za-z0-9._]+)")),
        ("tiktok", (r"tiktok\.com/@([A-Za-z0-9._]+)",)),
        ("twitter", (r"(?:twitter|x)\.com/([A-Za-z0-9_]+)",)),
        ("youtube", (r"youtube\.com/(?:@|channel/|c/)([A-Za-z0-9._-]+)",)),
    ):
        for pat in patterns:
            m = re.search(pat, lower if "ig:" not in pat else text, re.IGNORECASE)
            if m:
                handle = m.group(1).strip().rstrip("/")
                if handle.lower() not in _HANDLE_BLOCKLIST:
                    out[platform] = handle
                    break
    for m in _HANDLE_RE.finditer(text):
        h = m.group(1)
        if "instagram" in lower and "instagram_handle" not in out:
            out.setdefault("instagram", h)
    return out


def slugify_school(school: str) -> str:
    s = school.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s
