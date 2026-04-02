import numpy as np
from typing import Any, Dict, List

CONFERENCE_STRENGTH = {
    "SEC": 1.0,
    "Big Ten": 0.97,
    "Big 12": 0.93,
    "ACC": 0.90,
    "Pac-12": 0.88,
    "American": 0.72,
    "Mountain West": 0.70,
    "Sun Belt": 0.65,
    "MAC": 0.62,
    "CUSA": 0.60,
}

POSITION_GROUPS_CFB = {
    "QB": "skill",
    "RB": "skill",
    "WR": "skill",
    "TE": "skill",
    "OL": "offensive_line",
    "DL": "defensive_line",
    "LB": "linebacker",
    "CB": "defensive_back",
    "S": "defensive_back",
    "K": "specialist",
    "P": "specialist",
}

POSITION_GROUPS_MCBB = {
    "PG": "guard",
    "SG": "guard",
    "SF": "forward",
    "PF": "forward",
    "C": "center",
}

# Fixed order for model input (35 dims) — must match training export.
FEATURE_ORDER: List[str] = [
    "log_total_social",
    "log_ig_followers",
    "log_tt_followers",
    "ig_engagement_norm",
    "tt_engagement_norm",
    "platform_diversity",
    "verified_social",
    "log_news_mentions",
    "recruiting_stars_norm",
    "primary_stat_norm",
    "secondary_stat_norm",
    "usage_rate_norm",
    "conference_strength",
    "awards_norm",
    "starter_status",
    "market_size_norm",
    "collective_budget_norm",
    "tv_exposure_norm",
    "existing_deals_norm",
    "rev_share_norm",
    "social_growth_velocity",
    "news_velocity_norm",
    "performance_trajectory",
    "injury_risk_norm",
    "controversy_norm",
    "eligibility_remaining",
    "transfer_instability",
    "data_completeness",
    "pad_28",
    "pad_29",
    "pad_30",
    "pad_31",
    "pad_32",
    "pad_33",
    "pad_34",
]


def engineer_features(athlete_data: Dict[str, Any]) -> Dict[str, float]:
    """Transform raw athlete row + enrichment into normalized features."""
    features: Dict[str, float] = {}
    sport = athlete_data.get("sport", "cfb")
    conf = athlete_data.get("conference", "")
    conf_adj = CONFERENCE_STRENGTH.get(conf, 0.65)

    ig_followers = float(athlete_data.get("instagram_followers") or 0)
    tt_followers = float(athlete_data.get("tiktok_followers") or 0)
    tw_followers = float(athlete_data.get("twitter_followers") or 0)
    yt_subs = float(athlete_data.get("youtube_subscribers") or 0)
    ig_engagement = float(athlete_data.get("instagram_engagement_rate") or 0)
    tt_engagement = float(athlete_data.get("tiktok_engagement_rate") or 0)

    total_social = ig_followers + tt_followers + tw_followers + yt_subs
    features["log_total_social"] = np.log1p(total_social) / 15.0
    features["log_ig_followers"] = np.log1p(ig_followers) / 15.0
    features["log_tt_followers"] = np.log1p(tt_followers) / 15.0
    features["ig_engagement_norm"] = min(ig_engagement / 0.15, 1.0)
    features["tt_engagement_norm"] = min(tt_engagement / 0.20, 1.0)
    features["platform_diversity"] = sum(
        1 for f in [ig_followers, tt_followers, tw_followers, yt_subs] if f > 1000
    ) / 4.0
    features["verified_social"] = float(
        bool(athlete_data.get("instagram_verified") or athlete_data.get("twitter_verified"))
    )
    news_mentions = float(athlete_data.get("news_mentions_30d") or 0)
    features["log_news_mentions"] = np.log1p(news_mentions) / 6.0

    stats = athlete_data.get("stats", {}) or {}
    if isinstance(stats, str):
        import json

        stats = json.loads(stats)
    recruiting_stars = float(athlete_data.get("recruiting_stars") or 3)
    features["recruiting_stars_norm"] = (recruiting_stars - 1) / 4.0

    usage_rate_norm = 0.0
    if sport == "cfb":
        pos_raw = athlete_data.get("position", "") or ""
        pos_group = POSITION_GROUPS_CFB.get(pos_raw, "skill")
        if pos_group == "skill":
            if pos_raw == "QB":
                yards = float(stats.get("pass_yards_per_game") or 0)
                tds = float(stats.get("pass_tds_per_game") or 0)
                features["primary_stat_norm"] = min(yards / 350.0, 1.0)
                features["secondary_stat_norm"] = min(tds / 3.5, 1.0)
            else:
                yards = float(stats.get("yards_per_game") or 0)
                tds = float(stats.get("tds_per_game") or 0)
                features["primary_stat_norm"] = min(yards / 120.0, 1.0)
                features["secondary_stat_norm"] = min(tds / 1.2, 1.0)
        else:
            pff = float(stats.get("pff_grade") or 65)
            features["primary_stat_norm"] = max(0, (pff - 50) / 40.0)
            features["secondary_stat_norm"] = float(stats.get("starter", False))
    else:
        ppg = float(stats.get("points_per_game") or 0)
        rpg = float(stats.get("rebounds_per_game") or 0)
        apg = float(stats.get("assists_per_game") or 0)
        features["primary_stat_norm"] = min(ppg / 25.0, 1.0)
        features["secondary_stat_norm"] = min((rpg + apg) / 15.0, 1.0)
        usage_rate_norm = min(float(stats.get("usage_rate") or 20) / 35.0, 1.0)

    features["usage_rate_norm"] = usage_rate_norm
    features["conference_strength"] = conf_adj
    awards_count = float(athlete_data.get("awards_count") or 0)
    features["awards_norm"] = min(awards_count / 5.0, 1.0)
    snap_pct = float(athlete_data.get("snap_count_pct") or 0)
    features["starter_status"] = min(snap_pct / 100.0, 1.0)

    dma_rank = int(athlete_data.get("dma_rank") or 100)
    features["market_size_norm"] = max(0, (210 - dma_rank) / 209.0)
    collective_budget = float(athlete_data.get("collective_budget_usd") or 3000000)
    features["collective_budget_norm"] = min(
        np.log1p(collective_budget) / np.log1p(25000000), 1.0
    )
    tv_appearances = float(athlete_data.get("annual_tv_appearances") or 5)
    features["tv_exposure_norm"] = min(tv_appearances / 15.0, 1.0)
    deal_count = float(athlete_data.get("nil_deal_count") or 0)
    features["existing_deals_norm"] = min(deal_count / 10.0, 1.0)
    rev_share = float(athlete_data.get("revenue_share_value") or 0)
    features["rev_share_norm"] = min(np.log1p(rev_share) / np.log1p(2000000), 1.0)

    ig_delta_30d = float(athlete_data.get("ig_follower_delta_30d") or 0)
    features["social_growth_velocity"] = (
        np.clip(ig_delta_30d / max(ig_followers, 1000), -1.0, 1.0) * 0.5 + 0.5
    )
    news_velocity = float(athlete_data.get("news_velocity_30d") or 0)
    features["news_velocity_norm"] = np.clip(news_velocity / 5.0, -1.0, 1.0) * 0.5 + 0.5
    perf_trend = float(athlete_data.get("performance_trend") or 0)
    features["performance_trajectory"] = np.clip(perf_trend, -1.0, 1.0) * 0.5 + 0.5

    injury_pct = float(athlete_data.get("injury_missed_game_pct") or 0)
    features["injury_risk_norm"] = min(injury_pct / 0.30, 1.0)
    controversy = float(athlete_data.get("controversy_score") or 0)
    features["controversy_norm"] = min(controversy / 10.0, 1.0)
    eligibility = int(athlete_data.get("eligibility_year") or 2)
    features["eligibility_remaining"] = (eligibility - 1) / 4.0
    transfers = int(athlete_data.get("prior_transfers") or 0)
    features["transfer_instability"] = min(transfers / 3.0, 1.0)

    filled = sum(1 for v in features.values() if v > 0)
    features["data_completeness"] = filled / max(len(features), 1)

    for i in range(28, 35):
        features[f"pad_{i}"] = 0.0

    return {k: float(features.get(k, 0.0)) for k in FEATURE_ORDER}


def compute_confidence(features: Dict[str, float]) -> float:
    key_features = [
        "log_ig_followers",
        "primary_stat_norm",
        "collective_budget_norm",
        "market_size_norm",
    ]
    filled_key = sum(1 for k in key_features if features.get(k, 0) > 0)
    base_confidence = filled_key / len(key_features)
    completeness_bonus = features.get("data_completeness", 0) * 0.2
    return min(base_confidence + completeness_bonus, 0.99)
