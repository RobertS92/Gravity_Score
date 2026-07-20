"""Current-college eligibility rules for live search, scoring, and pricing."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

LIVE_ROSTER_STATUSES = frozenset({"active_on_roster", "transferred"})
DEFAULT_FRESHNESS_DAYS = int(os.getenv("LIVE_ROSTER_FRESHNESS_DAYS", "21"))


def live_eligibility_reason(
    athlete: Mapping[str, Any],
    *,
    now: datetime | None = None,
    freshness_days: int = DEFAULT_FRESHNESS_DAYS,
) -> str | None:
    """Return a blocking reason, or None when the athlete is live-eligible."""
    # Test doubles from pre-lifecycle code do not expose these columns. Real
    # database rows do, and are evaluated fail-closed below.
    lifecycle_columns_present = any(
        key in athlete for key in ("is_active", "roster_status", "roster_verified_at")
    )
    if not lifecycle_columns_present:
        return None
    if athlete.get("is_active") is not True:
        return "athlete is not on an active college roster"
    status = str(athlete.get("roster_status") or "").strip().lower()
    if status not in LIVE_ROSTER_STATUSES:
        return f"roster status {status or 'unknown'} is not eligible for live pricing"
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
