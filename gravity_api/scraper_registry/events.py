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
    # Nightly default — ESPN-first, minimal Firecrawl (0–3 calls/athlete typical).
    "scheduled_full": [
        "social_handle_discovery",
        "espn_roster",
        "espn_stats",
        "stats_freshness",
        "cfbd_api_stats_cfb",
        "instagram_followers",
        "tiktok_followers",
        "twitter_followers",
        "injury_structured",
        "identity_consensus",
        "social_authenticity",
        "espn_awards",
        "all_american",
        "conference_honors",
        "championship_results",
        "national_awards",
        "wikipedia_pageviews",
        "college_experience_pro",
    ],
    # Optional tier — Firecrawl-heavy / nice-to-have (SCRAPE_EXTENDED=1).
    "scheduled_extended": [
        "ncaa_official_roster",
        "transfer_portal",
        "recruiting_247",
        "on3_nil",
        "nil_deal_verified",
        "opendorse_profile",
        "social_engagement_instagram",
        "social_engagement_tiktok",
        "youtube_subscribers",
        "google_trends_athlete",
        "media_appearances",
        "social_growth_delta",
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
    # Gap-fill: resolver picks scrapers dynamically from field gaps (see gap_fill.py).
    "gap_fill": [],
}

# Suffixes that only apply to college athletes (blocked for pro tier).
COLLEGE_ONLY_SUFFIXES = frozenset(
    {
        "ncaa_official_roster",
        "transfer_portal",
        "recruiting_247",
        "recruiting_rivals",
        "recruiting_espn",
        "on3_nil",
        "nil_deal_verified",
        "inflcr_social",
    }
)

# Additional sport-specific keys appended to scheduled_full (beyond suffix expansion).
SCHEDULED_SPORT_API_KEYS: dict[str, list[str]] = {
    "ncaab_mens": ["kenpom_ncaab_mens"],
    "ncaab_womens": ["her_hoop_stats_ncaab_womens"],
    "ncaa_baseball": [
        "perfect_game_recruiting_baseball",
        "d1baseball_rankings_baseball",
        "mlb_draft_pipeline_baseball",
    ],
    "ncaa_volleyball": [
        "avca_poll_volleyball",
        "prepvolleyball_recruiting_volleyball",
        "avca_all_american_volleyball",
    ],
}

SCHEDULED_PRO_API_KEYS: dict[str, list[str]] = {
    "nfl": ["spotrac_contract_nfl", "forbes_earnings_nfl", "fantasy_adp_nfl"],
    "nba": ["spotrac_contract_nba", "forbes_earnings_nba", "college_experience_pro_nba"],
    "wnba": ["spotrac_contract_wnba", "forbes_earnings_wnba"],
}

SCHEDULED_SHARED_VELOCITY = [
    "news_rss_on3",
    "social_growth_delta",
    "program_context",
]

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


def resolve_event_scraper_keys(
    event_type: str,
    sport: str,
    *,
    include_extended: bool = False,
) -> list[str]:
    """Return concrete scraper_keys for an event + sport."""
    from gravity_api.scraper_registry import registry_by_key
    from gravity_api.scraper_registry.sports import SPORTS

    keys_map = registry_by_key()
    league_tier = SPORTS.get(sport, {}).get("league_tier", "college")
    suffixes = list(
        EVENT_SCRAPER_SUFFIXES.get(event_type, EVENT_SCRAPER_SUFFIXES["scheduled_full"])
    )
    if event_type == "scheduled_full":
        suffixes.extend(SCHEDULED_SHARED_VELOCITY)
        suffixes.extend(SCHEDULED_SPORT_API_KEYS.get(sport, []))
        if league_tier == "pro":
            suffixes.extend(SCHEDULED_PRO_API_KEYS.get(sport, []))
    if event_type == "scheduled_full" and include_extended:
        suffixes.extend(EVENT_SCRAPER_SUFFIXES.get("scheduled_extended", []))
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
        "spotrac_contract_wnba",
        "forbes_earnings_nfl",
        "forbes_earnings_nba",
        "forbes_earnings_wnba",
        "fantasy_adp_nfl",
        "news_rss_espn_cfb",
        "news_rss_espn_ncaab_mens",
        "news_rss_espn_ncaab_womens",
        "news_rss_espn_baseball",
        "news_rss_espn_volleyball",
    }

    pro_sports = {"nfl", "nba", "wnba"}
    # Keys that only apply to specific sports (skip wrong-sport suffix expansion).
    sport_exclusive_keys: dict[str, frozenset[str]] = {
        "cfbd_api_stats_cfb": frozenset({"cfb"}),
        "kenpom_ncaab_mens": frozenset({"ncaab_mens"}),
        "her_hoop_stats_ncaab_womens": frozenset({"ncaab_womens"}),
        "perfect_game_recruiting_baseball": frozenset({"ncaa_baseball"}),
        "d1baseball_rankings_baseball": frozenset({"ncaa_baseball"}),
        "mlb_draft_pipeline_baseball": frozenset({"ncaa_baseball"}),
        "avca_poll_volleyball": frozenset({"ncaa_volleyball"}),
        "prepvolleyball_recruiting_volleyball": frozenset({"ncaa_volleyball"}),
        "avca_all_american_volleyball": frozenset({"ncaa_volleyball"}),
        "college_experience_pro_nba": frozenset({"nba"}),
        "spotrac_contract_nfl": frozenset({"nfl"}),
        "spotrac_contract_nba": frozenset({"nba"}),
        "spotrac_contract_wnba": frozenset({"wnba"}),
        "forbes_earnings_nfl": frozenset({"nfl"}),
        "forbes_earnings_nba": frozenset({"nba"}),
        "forbes_earnings_wnba": frozenset({"wnba"}),
        "fantasy_adp_nfl": frozenset({"nfl"}),
    }
    resolved: list[str] = []
    for suffix in suffixes:
        if league_tier == "pro" and suffix in COLLEGE_ONLY_SUFFIXES:
            continue
        if suffix in shared_keys:
            key = suffix
        elif suffix in sport_only_keys:
            key = suffix
        else:
            key = f"{suffix}_{sport}"
        allowed = sport_exclusive_keys.get(key)
        if allowed is not None and sport not in allowed:
            continue
        if key == "college_experience_pro" and sport not in pro_sports:
            continue
        if key in keys_map:
            resolved.append(key)
    return resolved


# Pre-built for events without sport context (all suffixes as patterns)
EVENT_SCRAPER_KEYS: dict[str, list[str]] = {
    k: v for k, v in EVENT_SCRAPER_SUFFIXES.items()
}
