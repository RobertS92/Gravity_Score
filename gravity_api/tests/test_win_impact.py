"""Tests for CFB win-impact feature engineering."""

from __future__ import annotations

from gravity_api.services.win_impact import (
    compute_participation_index,
    compute_win_impact_features,
    compute_win_impact_score_v0,
    merge_win_impact_into_raw,
)
from gravity_ml.inference.vectorizer import build_feature_manifest


def test_participation_index_weights_gs():
    part, gs_rate = compute_participation_index(
        {"games_played_season": 12, "games_started": 10},
        expected_games=12,
    )
    assert abs(gs_rate - 10 / 12) < 0.001
    assert part > 0.7


def test_win_impact_spreads_with_proof_and_team():
    low = compute_win_impact_score_v0(
        {
            "games_played_season": 4,
            "games_started": 1,
            "proof_composite_pctile": 30,
            "team_win_pct_percentile": 40,
        },
        sport="cfb",
    )
    high = compute_win_impact_score_v0(
        {
            "games_played_season": 13,
            "games_started": 12,
            "proof_composite_pctile": 88,
            "team_win_pct_percentile": 85,
            "external_quality_score_observed": 1,
            "external_quality_score": 78,
        },
        sport="cfb",
    )
    assert high > low
    assert high > 50
    assert low < 40


def test_proof_residual_team():
    feats = compute_win_impact_features(
        {
            "proof_composite_pctile": 80,
            "team_win_pct_percentile": 90,
            "games_played_season": 12,
            "games_started": 11,
        },
        sport="cfb",
    )
    assert feats["proof_residual_team"] == -10.0
    assert feats["proof_x_participation"] > 0


def test_merge_win_impact_into_raw():
    out = merge_win_impact_into_raw(
        {
            "games_played_season": 12,
            "games_started": 10,
            "proof_composite_pctile": 70,
            "team_win_pct": 0.75,
            "team_win_pct_percentile": 80,
        },
        sport="cfb",
    )
    assert "win_impact_score" in out
    assert "target_impact_score" in out
    assert out["participation_index"] > 0


def test_impact_feature_manifest_has_core_keys():
    names = build_feature_manifest("impact", sport="cfb")
    for key in (
        "games_played_season",
        "games_started",
        "team_win_pct",
        "proof_x_participation",
        "participation_index",
    ):
        assert key in names
    assert "win_impact_score_v0" not in names
    assert "nil_valuation" not in names
