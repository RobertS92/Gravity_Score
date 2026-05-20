"""Lightweight shape checks (no database)."""

from gravity_api.services.compatibility import compatibility_score


def test_compatibility_score_shape():
    out = compatibility_score(
        {
            "brand_score": 60,
            "proof_score": 55,
            "proximity_score": 50,
            "velocity_score": 50,
            "risk_score": 20,
        },
        {
            "reach_score": 70,
            "authenticity_score": 60,
            "value_score": 65,
            "fit_score": 70,
            "stability_score": 80,
        },
        {},
    )
    assert "compatibility_score" in out
    assert "subscores" in out
    assert 0 <= float(out["compatibility_score"]) <= 100


def test_compatibility_risk_alignment_prefers_high_safety_score():
    safe = compatibility_score(
        {"brand_score": 60, "proof_score": 55, "proximity_score": 50, "velocity_score": 50, "risk_score": 80},
        {"stability_score": 80},
        {},
    )
    risky = compatibility_score(
        {"brand_score": 60, "proof_score": 55, "proximity_score": 50, "velocity_score": 50, "risk_score": 20},
        {"stability_score": 80},
        {},
    )
    assert safe["subscores"]["alignment_risk_stability"] > risky["subscores"]["alignment_risk_stability"]


def test_csc_report_keys_minimal():
    sample = {
        "value": {
            "total_benchmark": 10000,
            "range_low": 7000,
            "range_high": 15000,
            "tier_tag": "Mid-tier",
            "confidence_tag": "Moderate Confidence",
        },
        "explanation": {
            "executive_summary": "x",
            "key_value_drivers": [],
            "driver_takeaway": "y",
        },
        "validation": {
            "market_context": "z",
            "comparable_tier": "t",
            "example_comparables": [],
            "takeaway": "k",
        },
        "confidence_risk": {
            "confidence_level": "Moderate",
            "confidence_note": "c",
            "risk_level": "Moderate",
            "risk_note": "r",
        },
        "detail": {
            "shap_attribution": "s",
            "methodology": "m",
            "inputs": "i",
        },
    }
    required = set(sample.keys())
    assert required == {
        "value",
        "explanation",
        "validation",
        "confidence_risk",
        "detail",
    }
    assert sample["confidence_risk"]["confidence_level"] in {"High", "Moderate", "Low"}
    assert sample["confidence_risk"]["risk_level"] in {"High", "Moderate", "Low"}
