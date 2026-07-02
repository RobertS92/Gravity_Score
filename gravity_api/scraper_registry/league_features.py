"""League-tier feature key filters for scraper registry materialization."""

from __future__ import annotations

# College-only raw fields (NIL, portal, HS recruiting, NCAA roster, college awards).
COLLEGE_ONLY_FEATURE_KEYS = frozenset(
    {
        "class_year",
        "nil_valuation",
        "nil_valuation_source",
        "nil_confidence",
        "nil_deal_count",
        "nil_deal_count_verified",
        "nil_last_deal_date",
        "nil_rank_national",
        "nil_environment_score",
        "in_transfer_portal",
        "portal_entry_date",
        "destination_school",
        "recruiting_stars",
        "recruiting_rank_national",
        "recruiting_rank_position",
        "recruiting_state_rank",
        "recruiting_composite",
        "marketplace_listing",
        "social_metrics",
        "content_activity_score",
        "engagement_rate",
        "is_on_roster",
        "roster_verified_at",
        "official_jersey",
        "official_position",
        "heisman_finalist",
        "naismith_candidate",
        "golden_spikes_candidate",
        "avca_player_of_year",
        "all_american_count",
        "all_american_first_team",
    }
)

# Pro-only raw fields (contracts, endorsements, pro career bridge).
PRO_ONLY_FEATURE_KEYS = frozenset(
    {
        "contract_total_usd",
        "contract_guaranteed_usd",
        "contract_aav_usd",
        "contract_aav",
        "endorsement_value_usd",
        "endorsement_earnings",
        "total_earnings_usd",
        "forbes_list_rank",
        "fantasy_adp",
        "fantasy_trend_30d",
        "college_career_found",
        "college_espn_id",
        "college_team",
        "college_position",
        "college_stats_json",
        "college_achievements_json",
        "all_pro_count",
        "all_star_count",
    }
)


def filter_feature_keys_for_league(feature_keys: tuple[str, ...], league_tier: str) -> tuple[str, ...]:
    if league_tier == "pro":
        return tuple(k for k in feature_keys if k not in COLLEGE_ONLY_FEATURE_KEYS)
    if league_tier == "college":
        return tuple(k for k in feature_keys if k not in PRO_ONLY_FEATURE_KEYS)
    return feature_keys
