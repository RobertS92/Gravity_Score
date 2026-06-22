"""Event type → scraper key resolution for the prop-shop pipeline."""

from __future__ import annotations

# Dimension tags used by legacy COLLECTOR_MAP (still exposed for compatibility)
DIMENSION_TAGS = (
    "identity",
    "brand",
    "proof",
    "proximity",
    "velocity",
    "risk",
    "achievements",
)

# Event → scraper suffix patterns (expanded to full keys at runtime per sport)
EVENT_SCRAPER_SUFFIXES: dict[str, list[str]] = {
    "transfer_portal": [
        "transfer_portal",
        "ncaa_official_roster",
        "espn_roster",
        "recruiting_247",
        "recruiting_rivals",
        "identity_consensus",
        "news_rss_on3",
    ],
    "injury_report": [
        "injury_structured",
        "news_rss_on3",
        "google_trends_athlete",
    ],
    "nil_deal": [
        "nil_deal_verified",
        "on3_nil",
        "opendorse_profile",
        "instagram_followers",
        "social_engagement_instagram",
        "news_rss_on3",
    ],
    "social_delta": [
        "social_handle_discovery",
        "instagram_followers",
        "tiktok_followers",
        "twitter_followers",
        "social_engagement_instagram",
        "social_engagement_tiktok",
        "social_growth_delta",
        "youtube_subscribers",
    ],
    "stat_update": [
        "espn_stats",
        "sports_ref_stats",
        "stats_freshness",
        "cfbd_api_stats_cfb",
    ],
    "achievements_update": [
        "espn_awards",
        "sports_ref_honors",
        "all_american",
        "conference_honors",
        "championship_results",
        "national_awards",
        "avca_all_american_volleyball",
    ],
    "scheduled_full": [
        "social_handle_discovery",
        "espn_roster",
        "ncaa_official_roster",
        "espn_stats",
        "stats_freshness",
        "cfbd_api_stats_cfb",
        "recruiting_247",
        "on3_nil",
        "nil_deal_verified",
        "opendorse_profile",
        "instagram_followers",
        "tiktok_followers",
        "twitter_followers",
        "social_engagement_instagram",
        "youtube_subscribers",
        "google_trends_athlete",
        "wikipedia_pageviews",
        "media_appearances",
        "injury_structured",
        "transfer_portal",
        "identity_consensus",
        "social_authenticity",
        "espn_awards",
        "all_american",
        "conference_honors",
        "championship_results",
        "national_awards",
        "social_growth_delta",
        "college_experience_pro",
    ],
    "school_submission": [
        "espn_roster",
        "ncaa_official_roster",
        "espn_stats",
        "instagram_followers",
        "identity_consensus",
    ],
    "roster_sync": [
        "espn_roster",
        "ncaa_official_roster",
        "identity_consensus",
    ],
}

# Legacy dimension map (unchanged API surface)
COLLECTOR_MAP: dict[str, list[str]] = {
    "transfer_portal": ["identity", "proximity", "risk"],
    "injury_report": ["risk", "velocity"],
    "nil_deal": ["proximity", "brand", "velocity"],
    "social_delta": ["brand", "velocity"],
    "stat_update": ["proof", "velocity"],
    "achievements_update": ["achievements", "proof"],
    "scheduled_full": [
        "identity",
        "brand",
        "proof",
        "proximity",
        "velocity",
        "risk",
        "achievements",
    ],
    "school_submission": ["identity", "proof", "brand"],
    "roster_sync": ["identity"],
}


def resolve_event_scraper_keys(event_type: str, sport: str) -> list[str]:
    """Return concrete scraper_keys for an event + sport."""
    from gravity_api.scraper_registry import registry_by_key

    keys_map = registry_by_key()
    suffixes = EVENT_SCRAPER_SUFFIXES.get(
        event_type, EVENT_SCRAPER_SUFFIXES["scheduled_full"]
    )
    shared_keys = {
        "news_rss_on3",
        "social_growth_delta",
        "program_context",
        "perplexity_gap_fill",
        "college_experience_pro",
    }
    sport_only_keys = {
        "cfbd_api_stats_cfb",
        "kenpom_ncaab_mens",
        "her_hoop_stats_ncaab_womens",
        "perfect_game_recruiting_baseball",
        "d1baseball_rankings_baseball",
        "mlb_draft_pipeline_baseball",
        "avca_poll_volleyball",
        "prepvolleyball_recruiting_volleyball",
        "avca_all_american_volleyball",
        "college_experience_pro_nba",
        "spotrac_contract_nfl",
        "spotrac_contract_nba",
        "forbes_earnings_nfl",
        "forbes_earnings_nba",
        "fantasy_adp_nfl",
        "news_rss_espn_cfb",
        "news_rss_espn_ncaab_mens",
        "news_rss_espn_ncaab_womens",
        "news_rss_espn_baseball",
        "news_rss_espn_volleyball",
    }

    resolved: list[str] = []
    for suffix in suffixes:
        if suffix in shared_keys:
            key = suffix
        elif suffix in sport_only_keys:
            key = suffix
        else:
            key = f"{suffix}_{sport}"
        if key in keys_map:
            resolved.append(key)
    return resolved


# Pre-built for events without sport context (all suffixes as patterns)
EVENT_SCRAPER_KEYS: dict[str, list[str]] = {
    k: v for k, v in EVENT_SCRAPER_SUFFIXES.items()
}
