"""Commercial Gravity models — WP-G.

Labels are registered in ``gravity_ml.labels.registry`` (L_deal_180, …).
Builders and trainers are stubbed until deal/social history coverage is
sufficient and Impact outputs exist for the Proof feature group.
"""

BLOCKED_REASON = (
    "WP-G needs (1) dated deals in athlete_nil_deals / verified_deal_transactions "
    "with scrape coverage flags, (2) point-in-time social/metric history from "
    "scraper WP1–WP7, and (3) Impact outputs for Proof features after WP-I gates. "
    "Do not train on raw_composite_score or athlete_gravity_scores."
)

__all__ = ["BLOCKED_REASON"]
