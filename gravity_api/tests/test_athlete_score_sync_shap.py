from gravity_api.services.athlete_score_sync import shap_values_from_ml


def test_shap_values_from_ml_supports_legacy_shap_prefixed_fields():
    payload = {
        "shap_brand": 0.42,
        "shap_proof": "0.19",
        "shap_velocity": -0.07,
        "gravity_score": 77.1,
    }
    out = shap_values_from_ml(payload)
    assert out == {
        "brand": 0.42,
        "proof": 0.19,
        "velocity": -0.07,
    }


def test_shap_values_from_ml_supports_nested_explainability_payload():
    payload = {
        "gravity_score": 79.3,
        "explainability": {
            "shap_values": {
                "brand_score": {"value": 0.38},
                "proof_score": {"contribution": 0.22},
                "risk_score": {"impact": -0.11},
            }
        },
    }
    out = shap_values_from_ml(payload)
    assert out["brand"] == 0.38
    assert out["proof"] == 0.22
    assert out["risk"] == -0.11


def test_shap_values_from_ml_accepts_top_level_shap_values_map():
    payload = {
        "gravity_score": 73.0,
        "shap_values": {
            "brand": 0.28,
            "proximity": "0.14",
            "custom_signal_alpha": 0.05,
        },
    }
    out = shap_values_from_ml(payload)
    assert out["brand"] == 0.28
    assert out["proximity"] == 0.14
    assert out["custom_signal_alpha"] == 0.05
