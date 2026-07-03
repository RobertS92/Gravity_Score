from gravity_ml.inference.promotion_policy import (
    allow_ml_quality_models,
    beta_ranker_config,
    bundle_inference_allowed,
    is_blocked_inference_model,
    is_synthetic_training_manifest,
    production_gates,
)


def test_quality_models_blocked_by_default():
    assert allow_ml_quality_models() is False
    assert is_blocked_inference_model("gravity_athlete_cfb_quality_v1") is True
    assert is_blocked_inference_model("gravity_athlete_cfb_value_v1") is False


def test_cfb_value_beta_ranker_config():
    cfg = beta_ranker_config("gravity_athlete_cfb_value_v1")
    assert cfg is not None
    assert cfg.get("output_mode") == "rank_only"
    assert cfg.get("suppress_dollar_calibration") is True


def test_production_gates_defined():
    gates = production_gates("gravity_athlete_cfb_value_v1")
    assert gates["required"]["test_spearman_min"] == 0.65
    assert gates["required"]["labeled_rows_min"] == 800


def test_synthetic_manifest_blocked():
    assert is_synthetic_training_manifest({"row_count": 200}) is True
    assert is_synthetic_training_manifest({"training_source": "synthetic"}) is True
    assert is_synthetic_training_manifest(
        {"row_count": 361, "training_source": "observed_nil_valuation"}
    ) is False


def test_bundle_inference_allowed_real_cfb():
    assert bundle_inference_allowed(
        "gravity_athlete_cfb_value_v1",
        manifest={"row_count": 361, "training_source": "observed_nil_valuation"},
    ) is True
    assert bundle_inference_allowed(
        "gravity_athlete_cfb_value_v1",
        manifest={"row_count": 200},
    ) is False
