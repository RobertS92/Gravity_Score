"""Map DB athlete.sport values to CapIQ sport codes."""

from __future__ import annotations

CAP_SPORTS = frozenset({"CFB", "NCAAB", "NCAAW"})


def athlete_row_sport_to_cap(sport: str | None) -> str:
    """Normalize athletes.sport (cfb, mcbb, …) to CFB | NCAAB | NCAAW."""
    if not sport:
        return "CFB"
    s = sport.strip().lower()
    if s == "cfb":
        return "CFB"
    if s in ("mcbb", "ncaab_mens", "mens"):
        return "NCAAB"
    if s in ("ncaab_womens", "wcbb", "womens"):
        return "NCAAW"
    return "NCAAB" if "bb" in s or "basket" in s else "CFB"


def assert_cap_sport(sport: str) -> str:
    u = sport.strip().upper()
    if u not in CAP_SPORTS:
        raise ValueError(f"sport must be one of {sorted(CAP_SPORTS)}")
    return u
