"""Map UI cap sport codes to athletes.sport DB values."""

from __future__ import annotations

from typing import List

from gravity_api.services.onboarding_defaults import CAP_SPORTS


def cap_prefs_to_db_slugs(caps: List[str]) -> List[str]:
    """CFB→cfb, NCAAB/NCAAW→mcbb until athletes.sport supports women's distinctly."""
    out: List[str] = []
    for c in caps:
        u = str(c).strip().upper()
        if u not in CAP_SPORTS:
            continue
        if u == "CFB":
            slug = "cfb"
        else:
            slug = "mcbb"
        if slug not in out:
            out.append(slug)
    return out
