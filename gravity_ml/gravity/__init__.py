"""Commercial Gravity models — WP-G.

Label builders live in ``gravity_ml.gravity.labels`` and are registered in F2.
Trainers are skeleton-only until deal/social history coverage is sufficient and
Impact outputs exist for the Proof feature group. Never train on
``raw_composite_score`` or ``athlete_gravity_scores``.
"""

BLOCKED_REASON = (
    "WP-G needs (1) dated deals in athlete_nil_deals / verified_deal_transactions "
    "with scrape coverage flags, (2) point-in-time social/metric history from "
    "scraper WP1–WP7, and (3) Impact outputs for Proof features after WP-I gates. "
    "Do not train on raw_composite_score or athlete_gravity_scores."
)

# Register real builders on import.
from gravity_ml.gravity import labels as labels  # noqa: E402,F401

__all__ = ["BLOCKED_REASON", "labels"]
