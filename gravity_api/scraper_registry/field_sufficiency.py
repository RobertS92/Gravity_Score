"""Shared field sufficiency checks for gap-fill scrape mode."""

from __future__ import annotations

from typing import Any

from gravity_api.scrapers.parsers.handle_discovery import has_trusted_instagram_handle

# Placeholder values that must be re-scraped even when "present".
PLACEHOLDER_NUMBERS = frozenset({2500, 2500.0})

# Minimum followers to treat IG as real (below = likely bad scrape).
MIN_REAL_INSTAGRAM_FOLLOWERS = 100


def _as_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _as_int(val: Any) -> int | None:
    f = _as_float(val)
    return int(f) if f is not None else None


def _observed(raw: dict[str, Any], field: str) -> bool:
    flag = raw.get(f"{field}_observed")
    if flag is None:
        return _as_float(raw.get(field)) is not None and _as_float(raw.get(field)) > 0
    try:
        return int(float(flag)) == 1
    except (TypeError, ValueError):
        return bool(flag)


def is_present(raw: dict[str, Any], field: str) -> bool:
    val = raw.get(field)
    if val is None or val == "":
        return False
    if isinstance(val, (list, dict)):
        return len(val) > 0
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, (int, float)):
        return val > 0
    return True


def is_sufficient(raw: dict[str, Any], field: str) -> bool:
    """Return True when a field is present, observed (if applicable), and not a known placeholder."""
    if field == "instagram_followers":
        count = _as_int(raw.get("instagram_followers"))
        if count is None or count <= 0:
            return False
        if count in PLACEHOLDER_NUMBERS:
            return False
        # Real follower counts only — never trust observed=1 on tiny bogus values (e.g. 2).
        if count < MIN_REAL_INSTAGRAM_FOLLOWERS:
            return False
        return _observed(raw, "instagram_followers") or count >= MIN_REAL_INSTAGRAM_FOLLOWERS

    if field == "instagram_handle":
        if not has_trusted_instagram_handle(raw):
            return False
        h = str(raw.get("instagram_handle") or "").strip().lower()
        return h not in {
            "reel",
            "reels",
            "p",
            "explore",
            "accounts",
            "popular",
        }

    if field == "nil_valuation":
        val = _as_float(raw.get("nil_valuation"))
        if val is None or val <= 0:
            return False
        flag = raw.get("nil_valuation_observed")
        if flag is None:
            return False
        try:
            if int(float(flag)) != 1:
                return False
        except (TypeError, ValueError):
            return False
        conf = _as_float(raw.get("nil_confidence")) or 0.0
        return conf >= 0.55 or val > 0

    if field == "instagram_engagement_rate":
        if not is_sufficient(raw, "instagram_followers"):
            return False
        return _as_float(raw.get("instagram_engagement_rate")) is not None

    if field == "external_quality_score":
        score = _as_float(raw.get("external_quality_score"))
        return score is not None and _observed(raw, "external_quality_score")

    if field.endswith("_count") or field.endswith("_json"):
        return is_present(raw, field)

    if field in ("espn_id", "stats_as_of", "stats_source"):
        return is_present(raw, field)

    if not is_present(raw, field):
        return False
    obs_key = f"{field}_observed"
    if obs_key in raw:
        return _observed(raw, field)
    return True


def insufficient_fields(raw: dict[str, Any], fields: tuple[str, ...] | list[str]) -> list[str]:
    return [f for f in fields if not is_sufficient(raw, f)]
