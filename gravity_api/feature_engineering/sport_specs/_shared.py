"""Shared BPXVR metric profile specs applied across all sports."""

from __future__ import annotations

from gravity_api.feature_engineering.constants import DEFAULT_PLATFORM_WEIGHTS
from gravity_api.feature_engineering.types import MetricProfileSpec

BRAND_METRICS: tuple[MetricProfileSpec, ...] = (
    MetricProfileSpec("brand.social_reach_total", "brand", "social_reach_total", log_transform=True),
    MetricProfileSpec("brand.social_reach_weighted", "brand", "social_reach_weighted", log_transform=True),
    MetricProfileSpec("brand.engagement_quality", "brand", "engagement_quality"),
    MetricProfileSpec("brand.platform_diversity", "brand", "platform_diversity", yoy=False, deltas=()),
    MetricProfileSpec("brand.wikipedia_buzz", "brand", "wikipedia_views_30d", log_transform=True),
    MetricProfileSpec("brand.cross_platform_pctile", "brand", "cross_platform_reach"),
    MetricProfileSpec("brand.instagram_followers", "brand", "instagram_followers", log_transform=True),
    MetricProfileSpec("brand.tiktok_followers", "brand", "tiktok_followers", log_transform=True),
    MetricProfileSpec("brand.twitter_followers", "brand", "twitter_followers", log_transform=True),
    MetricProfileSpec("brand.youtube_subscribers", "brand", "youtube_subscribers", log_transform=True),
)

PROXIMITY_COLLEGE_METRICS: tuple[MetricProfileSpec, ...] = (
    MetricProfileSpec("proximity.nil_valuation", "proximity", "nil_valuation", log_transform=True, mask_below_confidence=0.6),
    MetricProfileSpec("proximity.nil_deal_count", "proximity", "nil_deal_count"),
    MetricProfileSpec("proximity.nil_per_follower", "proximity", "nil_per_follower"),
    MetricProfileSpec("proximity.market_index", "proximity", "market_index"),
    MetricProfileSpec("proximity.program_gravity", "proximity", "program_gravity_score"),
    MetricProfileSpec("proximity.collective_env", "proximity", "nil_environment_score"),
)

PROXIMITY_PRO_METRICS: tuple[MetricProfileSpec, ...] = (
    MetricProfileSpec("proximity.contract_aav", "proximity", "contract_aav", log_transform=True),
    MetricProfileSpec("proximity.endorsement_earnings", "proximity", "endorsement_earnings", log_transform=True),
    MetricProfileSpec("proximity.market_index", "proximity", "market_index"),
    MetricProfileSpec("proximity.team_market_size", "proximity", "team_dma_rank", invert_for_risk=False),
)

PROXIMITY_BASEBALL_METRICS: tuple[MetricProfileSpec, ...] = (
    MetricProfileSpec("proximity.draft_stock", "proximity", "draft_stock_score"),
    MetricProfileSpec("proximity.market_index", "proximity", "market_index"),
    MetricProfileSpec("proximity.program_gravity", "proximity", "program_gravity_score"),
    MetricProfileSpec("proximity.nil_valuation", "proximity", "nil_valuation", log_transform=True, mask_below_confidence=0.6),
)

VELOCITY_METRICS: tuple[MetricProfileSpec, ...] = (
    MetricProfileSpec("velocity.proof_performance", "velocity", "proof.performance_index"),
    MetricProfileSpec("velocity.social_reach", "brand", "social_reach_total"),
    MetricProfileSpec("velocity.engagement", "brand", "engagement_quality"),
    MetricProfileSpec("velocity.news_volume", "brand", "news_count_30d"),
    MetricProfileSpec("velocity.google_trends", "brand", "google_trends_score"),
    MetricProfileSpec("velocity.media_buzz", "brand", "media_buzz_score"),
    MetricProfileSpec("velocity.nil_valuation", "proximity", "nil_valuation", log_transform=True),
    MetricProfileSpec("velocity.deal_activity", "proximity", "nil_deal_count"),
)

RISK_METRICS: tuple[MetricProfileSpec, ...] = (
    MetricProfileSpec("risk.injury_risk", "risk", "injury_risk_score", invert_for_risk=True),
    MetricProfileSpec("risk.availability", "risk", "availability_rate"),
    MetricProfileSpec("risk.transfer_portal", "risk", "transfer_portal_active"),
    MetricProfileSpec("risk.narrative", "risk", "controversy_count_30d"),
    MetricProfileSpec("risk.data_quality", "risk", "data_quality_score"),
    MetricProfileSpec("risk.games_missed", "risk", "games_missed_season"),
)

COLLEGE_RECRUITING_KEYS = ("recruiting_stars", "recruiting_rank_national", "recruiting_rank_position")
ACHIEVEMENT_WEIGHTS = {
    "all_american": 1.0,
    "conference_honor": 0.4,
    "national_award": 1.5,
    "championship": 0.8,
    "pro_bowl": 0.6,
    "all_pro": 1.0,
    "all_star": 0.8,
}

__all__ = [
    "ACHIEVEMENT_WEIGHTS",
    "BRAND_METRICS",
    "COLLEGE_RECRUITING_KEYS",
    "DEFAULT_PLATFORM_WEIGHTS",
    "PROXIMITY_BASEBALL_METRICS",
    "PROXIMITY_COLLEGE_METRICS",
    "PROXIMITY_PRO_METRICS",
    "RISK_METRICS",
    "VELOCITY_METRICS",
]
