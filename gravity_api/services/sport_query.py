"""Map UI cap sport codes to athletes.sport DB values."""

from __future__ import annotations

from typing import List

from gravity_api.services.onboarding_defaults import CAP_SPORTS


CAP_TO_DB_SLUGS = {
    "CFB": ["cfb"],
    # Keep legacy mcbb compatibility while supporting explicit men's slug.
    "NCAAB": ["ncaab_mens", "mcbb"],
    # Support explicit women's slug. Do not map NCAAW -> mcbb to avoid pulling men's rows.
    "NCAAW": ["ncaab_womens", "wcbb"],
}


def cap_prefs_to_db_slugs(caps: List[str]) -> List[str]:
    """Map cap sport preferences to one or more DB slugs."""
    out: List[str] = []
    for c in caps:
        u = str(c).strip().upper()
        if u not in CAP_SPORTS:
            continue
        for slug in CAP_TO_DB_SLUGS.get(u, []):
            if slug not in out:
                out.append(slug)
    return out
