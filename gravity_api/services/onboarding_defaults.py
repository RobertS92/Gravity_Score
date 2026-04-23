"""Org type validation and default dashboard tab mapping (server-side).

`default_dashboard_tab` values are logical keys for the terminal. Client mapping
(see `mapDashboardTabToPath` in gravity-terminal) includes:
  roster  → /cap (CapIQ; legacy path /roster redirects to /cap/scenarios)
  market  → /market-scan
  athletes → / (NIL Intelligence)
  deals   → /csc
"""

from __future__ import annotations

from typing import List, Optional

ORG_TYPES = frozenset(
    {
        "school",
        "nil_collective",
        "brand_agency",
        "law_firm_agent",
        "insurance_finance",
        "media_research",
    }
)

CAP_SPORTS = frozenset({"CFB", "NCAAB", "NCAAW"})

VALID_DASHBOARD_TABS = frozenset({"roster", "market", "athletes", "deals"})


def assert_org_type(v: str) -> str:
    s = v.strip().lower()
    if s not in ORG_TYPES:
        raise ValueError(f"org_type must be one of: {', '.join(sorted(ORG_TYPES))}")
    return s


def normalize_sport_preferences(values: List[str]) -> List[str]:
    out: List[str] = []
    for x in values:
        u = str(x).strip().upper()
        if u not in CAP_SPORTS:
            raise ValueError(f"Invalid sport: {x}")
        if u not in out:
            out.append(u)
    if not out:
        raise ValueError("sport_preferences must contain at least one sport")
    return out


def default_dashboard_tab_for_org_type(org_type: str) -> str:
    """Logical tab keys consumed by the terminal route mapper."""
    m = {
        "school": "roster",
        "nil_collective": "market",
        "brand_agency": "athletes",
        "law_firm_agent": "deals",
        "insurance_finance": "athletes",
        "media_research": "market",
    }
    return m[org_type]


def default_athletes_sort_for_org_type(org_type: str) -> Optional[str]:
    if org_type == "brand_agency":
        return "gravity_desc"
    if org_type == "insurance_finance":
        return "risk_desc"
    return None
