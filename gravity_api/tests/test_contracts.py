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


def test_csc_report_keys_minimal():
    sample = {
        "executive_summary": "x",
        "gravity_score_table": "y",
        "comparables_analysis": [],
        "nil_range_note": "z",
        "shap_narrative": "s",
        "risk_assessment": "r",
        "methodology": "m",
    }
    required = set(sample.keys())
    assert required == {
        "executive_summary",
        "gravity_score_table",
        "comparables_analysis",
        "nil_range_note",
        "shap_narrative",
        "risk_assessment",
        "methodology",
    }
