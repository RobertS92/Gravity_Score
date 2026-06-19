from gravity_api.services.athlete_score_sync import _heuristic_score_from_raw


def test_fallback_without_nil_caps_at_two_million():
    raw = {
        "instagram_followers": 5_000,
        "twitter_followers": 1_000,
        "tiktok_followers": 2_000,
        "news_count_30d": 1,
        "google_trends_score": 50,
        "data_quality_score": 0.5,
    }
    out = _heuristic_score_from_raw(raw, "cfb")
    assert out["model_version"] == "heuristic_fallback_v1"
    assert out["dollar_p50_usd"] <= 2_000_000.0
    assert out["dollar_confidence"]["nil_anchored"] is False


def test_fallback_anchors_to_elite_nil_valuation():
    # Elite signal + a sanitized $21.9M NIL anchor must lift the heuristic
    # P50 well above the old $2M ceiling so the score row agrees with the
    # media-anchored CSC benchmark instead of contradicting it.
    raw = {
        "instagram_followers": 1_200_000,
        "twitter_followers": 400_000,
        "tiktok_followers": 600_000,
        "recruiting_stars": 5,
        "google_trends_score": 80,
        "news_count_30d": 10,
        "data_quality_score": 0.7,
        "nil_valuation": 21_900_000,
    }
    out = _heuristic_score_from_raw(raw, "cfb")
    assert out["dollar_confidence"]["nil_anchored"] is True
    # Blended toward the anchor: comfortably above the legacy cap.
    assert out["dollar_p50_usd"] > 5_000_000.0
    assert out["dollar_p50_usd"] <= 75_000_000.0
    assert out["dollar_p10_usd"] < out["dollar_p50_usd"] < out["dollar_p90_usd"]
    assert out["dollar_confidence"]["quality"] == "moderate"
