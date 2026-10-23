from gravity_ml.inference.promotion_policy import (
    allow_ml_quality_models,
    beta_ranker_config,
    bundle_inference_allowed,
    clear_policy_cache,
    is_blocked_inference_model,
    is_synthetic_training_manifest,
    metrics_satisfy_gates,
    production_gates,
)


def setup_function():
    clear_policy_cache()


def test_quality_models_blocked_by_default():
    assert allow_ml_quality_models() is False
    assert is_blocked_inference_model("gravity_athlete_cfb_quality_v1") is True
    assert is_blocked_inference_model("gravity_athlete_cfb_value_v1") is False


def test_cfb_value_beta_ranker_config():
    cfg = beta_ranker_config("gravity_athlete_cfb_value_v1")
    assert cfg is not None
    assert cfg.get("output_mode") == "rank_only"
    assert cfg.get("suppress_dollar_calibration") is True
    # F5: formula-label min_spearman gate removed.
    assert "min_spearman_for_rank" not in cfg


def test_production_gates_defined():
    gates = production_gates("gravity_athlete_cfb_value_v1")
    assert gates["required"]["test_spearman_min"] == 0.65
    assert gates["required"]["labeled_rows_min"] == 800
    assert gates["required"]["circularity_holdout_r2_max"] == 0.95


def test_impact_and_gravity_v2_gates_present():
    impact = production_gates("gravity_athlete_ncaab_mens_impact_v2")
    assert impact["required"]["circularity_holdout_r2_max"] == 0.95
    assert impact["required"]["beats_v0_on_G_I1_and_G_I2"] is True
    gravity = production_gates("gravity_athlete_cfb_gravity_v2")
    assert gravity["required"]["calibration_ece_max"] == 0.05
    assert gravity["required"]["test_positives_min"] == 30


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


def test_v2_bundle_refused_without_satisfying_metrics():
    assert (
        bundle_inference_allowed(
            "gravity_athlete_ncaab_mens_impact_v2",
            manifest={"row_count": 500, "training_source": "games_margins"},
            metrics={},
        )
        is False
    )


def test_v2_bundle_refused_on_circularity():
    metrics = {
        "test_rows": 250,
        "test_games": 250,
        "game_margin_rmse_beats_team_baseline": True,
        "game_margin_rmse_delta_ci_excludes_zero": True,
        "next_season_winpct_beats_prior_winpct": True,
        "yoy_impact_rate_corr_beats_raw_box": True,
        "beats_v0_on_G_I1_and_G_I2": True,
        "circularity_holdout_r2": 0.99,
    }
    ok, failures = metrics_satisfy_gates("gravity_athlete_ncaab_mens_impact_v2", metrics)
    assert ok is False
    assert any("circularity" in f for f in failures)
    assert (
        bundle_inference_allowed(
            "gravity_athlete_ncaab_mens_impact_v2",
            manifest={"row_count": 500, "training_source": "game_margins"},
            metrics=metrics,
        )
        is False
    )


def test_legacy_bundle_refused_when_circularity_metric_present():
    assert (
        bundle_inference_allowed(
            "gravity_athlete_cfb_value_v1",
            manifest={"row_count": 900, "training_source": "observed_nil_valuation"},
            metrics={"circularity_holdout_r2": 0.99, "test_spearman": 0.7, "test_rows": 200},
        )
        is False
    )


def test_banned_label_source_fails_gates():
    ok, failures = metrics_satisfy_gates(
        "gravity_athlete_cfb_value_v1",
        {"label_source": "athlete_gravity_scores", "test_spearman": 0.9, "labeled_rows": 1000},
    )
    assert ok is False
    assert any("banned_label_source" in f for f in failures)
