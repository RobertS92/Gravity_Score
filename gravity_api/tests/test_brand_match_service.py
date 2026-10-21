from gravity_api.services.brand_match import (
    BrandMatchBriefData,
    _calc_weights,
    _conference_regions,
    _score_candidate,
    _sports_to_db_slugs,
)


def _brief(**overrides):
    base = BrandMatchBriefData(
        budget=500000,
        category="apparel",
        geography=["Southeast"],
        audience=["18-24"],
        risk_tolerance=0.5,
        max_transfer_risk=False,
        authenticity_weight=0.6,
        min_social_reach=None,
        prioritize_engagement=False,
        excluded_categories=[],
        deal_density_preference="any",
        sports=["CFB"],
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def _row(**overrides):
    base = {
        "id": "a1",
        "name": "Test Athlete",
        "school": "State U",
        "position": "WR",
        "conference": "SEC",
        "sport": "cfb",
        "eligibility_year": 3,
        "data_quality_score": 0.9,
        "gravity_score": 72.0,
        "brand_score": 75.0,
        "risk_score": 18.0,
        "dollar_p50_usd": 300000.0,
        "dollar_p10_usd": 240000.0,
        "dollar_p90_usd": 380000.0,
        "instagram_followers": 250000,
        "twitter_followers": 80000,
        "tiktok_followers": 120000,
        "instagram_engagement_rate": 7.8,
        "verified_deals_count": 3,
        "deal_categories": ["apparel"],
    }
    base.update(overrides)
    return base


def test_weights_shift_to_engagement_when_prioritized():
    normal = _calc_weights(_brief(prioritize_engagement=False))
    focused = _calc_weights(_brief(prioritize_engagement=True))
    assert focused["engagement"] > normal["engagement"]
    assert focused["brand"] < normal["brand"]


def test_brand_match_budget_filter_uses_activation_price_not_annual_benchmark():
    brief = _brief(budget=200000)
    row = _row(dollar_p50_usd=2_000_000)
    weights = _calc_weights(brief)
    out = _score_candidate(row, brief, weights)
    assert out is not None
    assert out["deal_range_high"] < row["dollar_p50_usd"]


def test_low_budget_filters_out_activation_overpriced_candidate():
    brief = _brief(budget=50_000)
    row = _row(position="QB", dollar_p50_usd=21_900_000, brand_score=96, risk_score=10)
    weights = _calc_weights(brief)
    assert _score_candidate(row, brief, weights) is None


def test_scored_candidate_has_extended_fields():
    brief = _brief(excluded_categories=["gambling"])
    row = _row(deal_categories=["apparel", "gambling"])
    weights = _calc_weights(brief)
    out = _score_candidate(row, brief, weights)
    assert out is not None
    assert "match_breakdown" in out
    assert "recommended_structure" in out
    assert "exclusion_flags" in out
    assert "gambling" in out["exclusion_flags"]


def test_recommended_structure_uses_inverted_risk_orientation():
    brief = _brief()
    weights = _calc_weights(brief)

    safer = _score_candidate(
        _row(risk_score=10.0, verified_deals_count=6, instagram_engagement_rate=4.0),
        brief,
        weights,
    )
    assert safer is not None
    assert safer["recommended_structure"] == "FIXED"

    riskier = _score_candidate(
        _row(risk_score=45.0, verified_deals_count=2, instagram_engagement_rate=4.0),
        brief,
        weights,
    )
    assert riskier is not None
    assert riskier["recommended_structure"] == "PERFORMANCE_WEIGHTED"


def test_sports_map_includes_mens_and_womens_basketball_slugs():
    assert "ncaab_mens" in _sports_to_db_slugs(["NCAAB"])
    assert "mcbb" in _sports_to_db_slugs(["NCAAB"])
    assert "ncaab_womens" in _sports_to_db_slugs(["NCAAW"])
    assert _sports_to_db_slugs(["CFB"]) == ["cfb"]


def test_conference_region_substring_and_full_names():
    assert "southeast" in _conference_regions("SEC")
    assert "southeast" in _conference_regions("Atlantic Coast Conference")
    assert "midwest" in _conference_regions("Big Ten")


def test_default_400k_apparel_southeast_scores_sec_athlete():
    brief = _brief(budget=400_000, category="apparel", geography=["Southeast"])
    weights = _calc_weights(brief)
    out = _score_candidate(_row(), brief, weights)
    assert out is not None
    assert out["match_score"] >= 50


def test_non_se_conference_gets_partial_geo_credit_not_hard_zero():
    brief = _brief(budget=400_000, category="apparel", geography=["Southeast"])
    weights = _calc_weights(brief)
    # Big Ten has no Southeast overlap; soft national credit should keep mid-brand
    # athletes above the floor even with thin social.
    out = _score_candidate(
        _row(
            conference="Big Ten",
            brand_score=70.0,
            instagram_followers=0,
            twitter_followers=0,
            tiktok_followers=0,
            instagram_engagement_rate=0,
        ),
        brief,
        weights,
    )
    assert out is not None
    assert out["match_breakdown"]["geography_overlap"] > 0
