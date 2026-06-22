"""Field classification for scraped payloads."""

from __future__ import annotations

from typing import Any

DIMENSION_FIELDS: dict[str, set[str]] = {
    "identity": {
        "player_name",
        "team",
        "position",
        "class_year",
        "jersey_number",
        "instagram_handle",
        "tiktok_handle",
        "twitter_handle",
        "external_id_espn",
        "college_espn_id",
    },
    "brand": {
        "instagram_followers",
        "tiktok_followers",
        "twitter_followers",
        "youtube_subscribers",
        "instagram_engagement_rate",
        "social_authenticity_score",
        "wikipedia_views_30d",
    },
    "proof": {
        "season_stats",
        "career_stats",
        "recruiting_stars",
        "college_stats",
        "games_played_season",
    },
    "proximity": {
        "nil_valuation",
        "nil_confidence",
        "contract_total_usd",
        "program_gravity_score",
    },
    "velocity": {
        "news_count_30d",
        "google_trends_score",
        "media_buzz_score",
        "instagram_growth_30d",
    },
    "risk": {
        "in_transfer_portal",
        "injury_risk_score",
        "current_injury_status",
    },
    "achievements": {
        "achievements_json",
        "all_american_count",
        "national_awards_count",
    },
}


def classify_field(field_key: str) -> str:
    for dim, keys in DIMENSION_FIELDS.items():
        if field_key in keys:
            return dim
    if "achievement" in field_key or "award" in field_key or "honor" in field_key:
        return "achievements"
    if "injury" in field_key or "portal" in field_key:
        return "risk"
    if "nil" in field_key or "contract" in field_key:
        return "proximity"
    if "follower" in field_key or "engagement" in field_key or "youtube" in field_key:
        return "brand"
    if "stat" in field_key or "recruiting" in field_key or "college_" in field_key:
        return "proof"
    if "news" in field_key or "trend" in field_key or "media" in field_key:
        return "velocity"
    return "identity"


def classify_payload(fields: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {k: [] for k in DIMENSION_FIELDS}
    for key in fields:
        dim = classify_field(key)
        out.setdefault(dim, []).append(key)
    return {k: v for k, v in out.items() if v}
