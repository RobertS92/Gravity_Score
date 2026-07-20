from gravity_api.services.global_scores import (
    calibrate_global_commercial_score,
    midrank_percentile,
)


def test_midrank_percentile_is_monotonic_and_tie_safe():
    values = [40.0, 50.0, 50.0, 80.0]
    assert midrank_percentile(40.0, values) < midrank_percentile(50.0, values)
    assert midrank_percentile(50.0, values) == midrank_percentile(50.0, list(reversed(values)))
    assert midrank_percentile(80.0, values) == 99.0


def test_brand_lift_can_exceed_salary_only_score():
    score, audit = calibrate_global_commercial_score(
        {"brand_score": 96.0, "dollar_confidence": {}},
        {"instagram_followers": 50_000_000, "wikipedia_views_30d": 800_000},
        "nba",
    )
    assert score >= 90.0
    assert audit["observed_market_used"] is False


def test_wnba_adjustment_lowers_typical_but_preserves_exceptional_star():
    typical, _ = calibrate_global_commercial_score(
        {"brand_score": 65.0, "dollar_confidence": {}}, {}, "wnba"
    )
    star, audit = calibrate_global_commercial_score(
        {"brand_score": 86.0, "dollar_confidence": {}},
        {
            "instagram_followers": 400_000,
            "wikipedia_views_30d": 120_000,
            "social_authenticity_score": 85.0,
            "social_account_verified": True,
        },
        "wnba",
    )
    assert typical < 65.0
    assert 82.0 <= star <= 88.0
    assert audit["sport_market_adjustment"] > -4.0


def test_bio_verified_personal_instagram_trusts_audience():
    """Bio-matched personal IG must count as trusted audience even if auth < 70."""
    score, audit = calibrate_global_commercial_score(
        {"brand_score": 86.4, "dollar_confidence": {}},
        {
            "instagram_followers": 352_204,
            "twitter_followers": 10,
            "social_authenticity_score": 35.0,
            "social_account_verified": False,
            "instagram_handle": "angel.reese",
            "twitter_handle": "reese10angel",
            "instagram_handle_bio_verified": 1,
            "instagram_handle_source": "bio_verified",
            "wikipedia_views_30d": 115_809,
            "google_trends_score": 50.0,
        },
        "wnba",
    )
    assert audit["audience_trusted"] is True
    assert audit["personal_identity"] is True
    assert 82.0 <= score <= 88.0


def test_missing_commercial_data_regresses_to_neutral():
    score, audit = calibrate_global_commercial_score(
        {"dollar_confidence": {}}, {}, "nfl"
    )
    assert 40.0 <= score <= 60.0
    assert audit["observed_market_used"] is False


def test_observed_college_nil_anchors_commercial_gravity():
    score, audit = calibrate_global_commercial_score(
        {"brand_score": 48.0, "dollar_confidence": {}},
        {
            "nil_valuation": 16_743_000,
            "nil_valuation_observed": 1,
            "instagram_followers": 3_000,
            "twitter_followers": 1_050,
        },
        "cfb",
    )
    assert 85.0 <= score <= 88.0
    assert audit["observed_market_used"] is True
    assert audit["market_score"] is not None and audit["market_score"] >= 85.0


def test_salary_without_global_brand_does_not_mint_ninety():
    score, audit = calibrate_global_commercial_score(
        {"brand_score": 78.0, "dollar_confidence": {}},
        {
            "observed_market_value_usd": 46_000_000,
            "wikipedia_views_30d": 20_000,
        },
        "nba",
    )
    assert 72.0 <= score <= 82.0
    assert audit["market_score"] >= 80.0


def test_nba_elite_star_market_floor_without_social_hardcode():
    score, audit = calibrate_global_commercial_score(
        {"brand_score": 74.0, "dollar_confidence": {}},
        {
            "observed_market_value_usd": 45_550_512,
            "games_played_season": 79,
            "pts": 2_177,
            "all_star_count": 5,
            "wikipedia_views_30d": 786,
            "social_authenticity_score": 10.0,
            "social_account_verified": False,
        },
        "nba",
    )
    assert 84.0 <= score <= 88.0
    assert audit["nba_star_commercial_floor"] is not None
    assert score < 95.0


def test_nba_high_usage_superstar_floor_uses_production_not_name():
    score, audit = calibrate_global_commercial_score(
        {"brand_score": 74.0, "dollar_confidence": {}},
        {
            "observed_market_value_usd": 37_250_000,
            "games_played_season": 64,
            "pts": 2_143,
            "all_star_count": 4,
            "wikipedia_views_30d": 789,
            "instagram_handle": "personal_handle",
            "social_authenticity_score": 10.0,
            "social_account_verified": False,
        },
        "nba",
    )
    assert 86.0 <= score <= 89.0
    assert audit["nba_star_commercial_floor"] is not None
    assert score < 95.0


def test_nba_icon_attention_floor_without_social_hardcode():
    score, audit = calibrate_global_commercial_score(
        {"brand_score": 74.0, "dollar_confidence": {}},
        {
            "observed_market_value_usd": 48_500_000,
            "games_played_season": 43,
            "pts": 1_142,
            "all_star_count": 5,
            "wikipedia_views_30d": 272_183,
            "social_authenticity_score": 10.0,
            "social_account_verified": False,
        },
        "nba",
    )
    assert 88.0 <= score <= 92.5
    assert audit["nba_star_commercial_floor"] is not None
    assert score < 95.0


def test_nfl_contract_scale_remains_strong_but_brand_sensitive():
    mahomes, audit = calibrate_global_commercial_score(
        {"brand_score": 78.0, "dollar_confidence": {}},
        {
            "observed_market_value_usd": 64_000_000,
            "wikipedia_views_30d": 115_000,
        },
        "nfl",
    )
    sutton, _ = calibrate_global_commercial_score(
        {"brand_score": 77.0, "dollar_confidence": {}},
        {
            "observed_market_value_usd": 23_000_000,
            "wikipedia_views_30d": 3_500,
        },
        "nfl",
    )
    # Elite top-of-market APY + solid wiki → mid-90s commercial Gravity.
    assert 94.0 <= mahomes <= 97.0
    assert audit["market_score"] is not None and audit["market_score"] >= 92.0
    assert 70.0 <= sutton <= 80.0
    assert mahomes > sutton + 10.0


def test_elite_apy_without_consumer_evidence_stays_blended():
    """Huge APY alone must not mint mid-90s without wiki/audience/identity."""
    score, audit = calibrate_global_commercial_score(
        {"brand_score": 55.0, "dollar_confidence": {}},
        {
            "observed_market_value_usd": 64_000_000,
            "wikipedia_views_30d": 0,
            "social_authenticity_score": 10.0,
        },
        "nfl",
    )
    assert score < 94.0
    assert audit["market_score"] == 94.0


def test_untrusted_team_twitter_cannot_mint_ninety():
    """Team/org Twitter attached to a roster player must not bypass APY."""
    score, audit = calibrate_global_commercial_score(
        {"brand_score": 95.8, "dollar_confidence": {}},
        {
            "observed_market_value_usd": 10_000_000,
            "instagram_followers": 46_877,
            "twitter_followers": 852_690,
            "twitter_handle": "jaguars",
            "social_authenticity_score": 40.0,
            "social_account_verified": False,
            "wikipedia_views_30d": 0,
            "google_trends_score": 50.0,
        },
        "nfl",
    )
    assert score < 75.0
    assert audit["audience_trusted"] is False
    assert audit["market_score"] is not None
    assert audit["market_score"] < 72.0
    # Absolute brand may use Instagram-only; must stay below brand-led override.
    assert audit["brand_score_absolute"] < 90.0


def test_trusted_mega_audience_can_still_brand_lead():
    score, audit = calibrate_global_commercial_score(
        {"brand_score": 96.0, "dollar_confidence": {}},
        {
            "instagram_followers": 50_000_000,
            "social_authenticity_score": 85.0,
            "social_account_verified": True,
            "wikipedia_views_30d": 800_000,
        },
        "nba",
    )
    assert score >= 90.0
    assert audit["audience_trusted"] is True


def test_mega_wiki_plus_personal_handle_lifts_global_icon():
    """Mega encyclopedic attention + personal IG handle + market → mid-90s."""
    score, audit = calibrate_global_commercial_score(
        {"brand_score": 74.0, "dollar_confidence": {}},
        {
            "observed_market_value_usd": 52_627_153,
            "wikipedia_views_30d": 853_952,
            "instagram_handle": "kingjames",
            "social_authenticity_score": 35.0,
            "social_account_verified": False,
        },
        "nba",
    )
    assert 95.0 <= score <= 97.0
    assert audit["personal_identity"] is True
    assert audit["audience_trusted"] is False
    assert (audit["wiki_score"] or 0.0) >= 90.0


def test_team_twitter_handle_is_not_personal_identity():
    score, audit = calibrate_global_commercial_score(
        {"brand_score": 95.8, "dollar_confidence": {}},
        {
            "observed_market_value_usd": 10_000_000,
            "instagram_followers": 46_877,
            "twitter_followers": 852_690,
            "twitter_handle": "jaguars",
            "instagram_handle": "foyelicious",
            "social_authenticity_score": 40.0,
            "social_account_verified": False,
            "wikipedia_views_30d": 0,
            "google_trends_score": 50.0,
        },
        "nfl",
    )
    assert score < 75.0
    # Personal IG handle may corroborate identity, but without mega wiki /
    # trusted audience it must not mint 90+.
    assert score < 90.0
    assert audit["audience_trusted"] is False
