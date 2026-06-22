"""Tests for brand partnership scoring."""

from __future__ import annotations

from gravity_ml.brand.taxonomy import (
    enrich_raw_with_partnerships,
    get_taxonomy,
    score_athlete_partnerships,
)
from gravity_ml.inference.predict import score_athlete
from gravity_ml.schemas import ScoreAthleteRequest


def test_taxonomy_loads_categories():
    tax = get_taxonomy()
    assert len(tax.categories()) >= 10
    assert tax.match_brand("Nike") is not None
    assert tax.match_brand("Gatorade") is not None


def test_partnership_scoring_nike_gatorade():
    raw = {
        "nil_deals": [
            {"brand": "Nike", "verified": True, "value": 250000},
            {"brand": "Gatorade", "verified": True},
        ]
    }
    result = score_athlete_partnerships(raw)
    assert result.partnership_brand_score > 80
    assert result.partnership_proof_boost > 0
    assert result.verified_deal_count == 2


def test_enrich_raw_adds_fields():
    raw = enrich_raw_with_partnerships({"nil_deals": [{"brand": "Apple", "verified": True}]})
    assert "partnership_brand_score" in raw
    assert raw["partnership_brand_score"] > 70


def test_score_athlete_with_partnerships():
    req = ScoreAthleteRequest(
        athlete_id="test",
        sport="cfb",
        raw_data={
            "instagram_followers": 100000,
            "nil_deals": [{"brand": "Nike", "verified": True, "value": 500000}],
            "proof_performance_index_pctile": 88,
        },
    )
    out = score_athlete(req)
    assert out.gravity_score > 0
    assert out.partnership_brand_score is not None
    assert out.quality_score is not None
