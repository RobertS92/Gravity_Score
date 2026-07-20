"""Tests for heuristic_gravity_v1 and scoring stack tier logic."""

from gravity_api.services.heuristic_gravity import compute_heuristic_gravity_v1
from gravity_api.services.scoring_stack import (
    apply_tier2_fallback_if_needed,
    finalize_score_metadata,
    is_weak_ml_score,
    overlay_commercial_viability,
)


def test_heuristic_gravity_spreads_scores_not_flat_77():
    low = compute_heuristic_gravity_v1(
        {"recruiting_stars": 2, "instagram_followers": 500, "news_count_30d": 0},
        "nfl",
    )
    high = compute_heuristic_gravity_v1(
        {
            "recruiting_stars": 5,
            "instagram_followers": 2_000_000,
            "games_played_season": 12,
            "news_count_30d": 15,
            "nil_valuation": 5_000_000,
            "nil_valuation_observed": 1,
        },
        "cfb",
    )
    assert high["gravity_score"] > low["gravity_score"]
    assert high["model_version"] == "heuristic_gravity_v1"
    assert high["score_tier"] == 2
    assert not (76.85 <= low["gravity_score"] <= 77.35 and 76.85 <= high["gravity_score"] <= 77.35)


def test_is_weak_ml_detects_composite_fallback():
    assert is_weak_ml_score({"model_version": "composite_fallback_v0", "gravity_score": 77.1})
    assert is_weak_ml_score({"fallback_used": True, "gravity_score": 80.0})
    assert not is_weak_ml_score(
        {"model_version": "1.0.0-beta", "gravity_score": 82.0, "fallback_used": False}
    )


def test_apply_tier2_replaces_flat_composite():
    weak = {
        "gravity_score": 77.1,
        "model_version": "composite_fallback_v0",
        "fallback_used": True,
        "confidence": 0.55,
        "model_key": "gravity_athlete_nfl_v1",
    }
    raw = {
        "recruiting_stars": 4,
        "instagram_followers": 800_000,
        "games_played_season": 16,
        "news_count_30d": 8,
    }
    out = apply_tier2_fallback_if_needed(weak, raw, "nfl")
    assert out["model_version"] == "heuristic_gravity_v1"
    assert out["gravity_score"] != 77.1
    assert out.get("replaced_model_version") == "composite_fallback_v0"


def test_overlay_commercial_viability_promotes_cv_to_gravity():
    score = {"gravity_score": 70.0, "dollar_confidence": {}, "fallback_used": True}
    cv = {
        "commercial_viability_score": 88.0,
        "commercial_viability_index": 72.0,
        "nil_signal_source": "estimated",
        "nil_dollar_p10": 100_000,
        "nil_dollar_p50": 250_000,
        "nil_dollar_p90": 500_000,
    }
    out = overlay_commercial_viability(score, {}, cv, "cfb")
    assert out["gravity_score"] == 88.0
    assert out["gravity_source"] == "commercial_viability"
    assert out["dollar_confidence"]["commercial_viability_score"] == 88.0
    assert out["dollar_p50_usd"] == 250_000


def test_overlay_commercial_viability_attaches_metadata():
    score = {
        "gravity_score": 70.0,
        "dollar_confidence": {},
        "fallback_used": False,
        "dollar_p50_usd": 1_000_000,
        "gravity_source": "commercial_ml",
    }
    cv = {
        "commercial_viability_score": 88.0,
        "commercial_viability_index": 72.0,
        "nil_signal_source": "estimated",
        "nil_dollar_p10": 100_000,
        "nil_dollar_p50": 250_000,
        "nil_dollar_p90": 500_000,
    }
    out = overlay_commercial_viability(score, {}, cv, "cfb")
    assert out["dollar_confidence"]["commercial_viability_score"] == 88.0
    # Commercial ML wins — CV does not overwrite G.
    assert out["gravity_score"] == 70.0
    assert out.get("gravity_source") == "commercial_ml"


def test_finalize_preserves_college_commercial_viability_score():
    score = {
        "gravity_score": 87.0,
        "brand_score": 45.0,
        "dollar_confidence": {"gravity_source": "commercial_viability"},
        "fallback_used": False,
        "gravity_source": "commercial_viability",
    }
    out = finalize_score_metadata(
        score,
        raw={
            "instagram_followers": 3_000,
            "twitter_followers": 1_050,
            "nil_valuation": 16_743_000,
            "nil_valuation_observed": 1,
        },
        sport="cfb",
    )
    assert out["gravity_score"] == 87.0
    assert "global_commercial_calibration" not in out
    assert out["dollar_confidence"]["gravity_source"] == "commercial_viability"
