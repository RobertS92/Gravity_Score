"""Tests for sport-specific athlete pipeline wiring."""

from __future__ import annotations

from gravity_api.services.sport_pipeline.config import ALL_SPORT_PIPELINES, get_sport_pipeline_config
from gravity_api.services.sport_pipeline.raw_payload import flatten_bpxvr_for_ml, merge_raw_with_bpxvr
from gravity_api.feature_engineering.engine import FeatureEngineeringEngine


def test_all_sports_have_pipeline_config():
    assert len(ALL_SPORT_PIPELINES) == 8
    for sport in ("cfb", "nfl", "nba", "ncaa_volleyball"):
        cfg = get_sport_pipeline_config(sport)
        assert cfg.model_key.startswith("gravity_athlete_")
        assert f"/score/athlete/{sport}" == cfg.ml_endpoint


def test_bpxvr_flatten_for_ml():
    engine = FeatureEngineeringEngine()
    snap = engine.build_snapshot(
        entity_id="test",
        sport="cfb",
        position="QB",
        season_year=2025,
        raw={
            "pass_yards": 3000,
            "pass_td": 25,
            "passer_rating": 140,
            "qbr": 65,
            "completion_pct": 62,
            "pass_int": 9,
            "rush_yards": 100,
            "games_played_season": 10,
            "cohort_performance_index_values": [float(i) for i in range(40)],
            "cohort_stat_means": {
                "pass_yards": 2800,
                "pass_td": 22,
                "passer_rating": 135,
                "qbr": 62,
                "completion_pct": 60,
                "pass_int": 12,
                "rush_yards": 120,
            },
            "cohort_stat_stds": {
                "pass_yards": 600,
                "pass_td": 8,
                "passer_rating": 15,
                "qbr": 10,
                "completion_pct": 5,
                "pass_int": 4,
                "rush_yards": 80,
            },
        },
    )
    flat = flatten_bpxvr_for_ml(snap)
    assert "proof_performance_index_pctile" in flat or "proof_performance_index_raw" in flat
    merged = merge_raw_with_bpxvr({"sport": "cfb"}, snap)
    assert "bpxvr" in merged
    assert merged["proof_trajectory_class"]
