"""Current-college eligibility rules for live search, scoring, and pricing."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

LIVE_ROSTER_STATUSES = frozenset({"active_on_roster", "transferred"})
DEFAULT_FRESHNESS_DAYS = int(os.getenv("LIVE_ROSTER_FRESHNESS_DAYS", "21"))


def _lifecycle_columns_present(athlete: Mapping[str, Any]) -> bool:
    # Test doubles from pre-lifecycle code do not expose these columns. Real
    # database rows do, and are evaluated fail-closed below.
    return any(key in athlete for key in ("is_active", "roster_status", "roster_verified_at"))


def roster_membership_block_reason(athlete: Mapping[str, Any]) -> str | None:
    """Hard block: athlete is not on a current college roster.

    Freshness is intentionally excluded — search and reports handle stale
    verification separately so the terminal can still open profiles that
    bootstrap loads via ``include_stale_roster``.
    """
    if not _lifecycle_columns_present(athlete):
        return None
    if athlete.get("is_active") is not True:
        return "athlete is not on an active college roster"
    status = str(athlete.get("roster_status") or "").strip().lower()
    if status not in LIVE_ROSTER_STATUSES:
        return f"roster status {status or 'unknown'} is not eligible for live pricing"
    return None


def roster_freshness_issue(
    athlete: Mapping[str, Any],
    *,
    now: datetime | None = None,
    freshness_days: int = DEFAULT_FRESHNESS_DAYS,
) -> str | None:
    """Soft issue when roster verification is missing or outside the live window."""
    if not _lifecycle_columns_present(athlete):
        return None
    verified_at = athlete.get("roster_verified_at")
    if verified_at is None:
        return "current roster membership has not been verified"
    if isinstance(verified_at, str):
        try:
            verified_at = datetime.fromisoformat(verified_at.replace("Z", "+00:00"))
        except ValueError:
            return "roster verification timestamp is invalid"
    if not isinstance(verified_at, datetime):
        return "roster verification timestamp is invalid"
    if verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if verified_at < current - timedelta(days=freshness_days):
        return f"roster verification is older than {freshness_days} days"
    return None


def live_eligibility_reason(
    athlete: Mapping[str, Any],
    *,
    now: datetime | None = None,
    freshness_days: int = DEFAULT_FRESHNESS_DAYS,
) -> str | None:
    """Return a blocking reason, or None when the athlete is live-eligible.

    Used by live discovery (search/leaderboards). Requires current roster
    membership *and* fresh verification.
    """
    return roster_membership_block_reason(athlete) or roster_freshness_issue(
        athlete, now=now, freshness_days=freshness_days
    )


def _env_flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


def report_eligibility_block_reason(
    athlete: Mapping[str, Any],
    *,
    now: datetime | None = None,
    freshness_days: int = DEFAULT_FRESHNESS_DAYS,
) -> str | None:
    """Blocking reason for CSC / deal reports.

    Default: only departed/inactive athletes are blocked. Stale roster
    verification is returned via :func:`roster_freshness_issue` so callers can
    stamp report metadata instead of failing closed — matching terminal
    bootstrap, which already falls back to ``include_stale_roster``.

    Set ``CSC_REQUIRE_FRESH_ROSTER=1`` to hard-block stale verification again
    (strict governance mode).
    """
    hard = roster_membership_block_reason(athlete)
    if hard:
        return hard
    if _env_flag("CSC_REQUIRE_FRESH_ROSTER"):
        return roster_freshness_issue(athlete, now=now, freshness_days=freshness_days)
    return None
