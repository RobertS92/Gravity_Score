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
    assert high > 75
    assert low < 50


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


def test_nfl_skill_infers_gs_equals_gp_when_starts_missing():
    part_missing, gs_rate_missing = compute_participation_index(
        {"games_played_season": 14, "position": "QB"},
        expected_games=17,
        sport="nfl",
    )
    part_full, gs_rate_full = compute_participation_index(
        {"games_played_season": 14, "games_started": 14, "position": "QB"},
        expected_games=17,
        sport="nfl",
    )
    assert abs(gs_rate_missing - 1.0) < 0.001
    assert abs(part_missing - part_full) < 0.001
    # Old 0.5×gp_ratio prior would be much lower
    assert part_missing > 0.7


def test_nfl_non_skill_infers_starts_for_every_down():
    part, gs_rate = compute_participation_index(
        {"games_played_season": 14, "position": "DE"},
        expected_games=17,
        sport="nfl",
    )
    assert abs(gs_rate - 1.0) < 0.001
    assert part > 0.7


def test_proof_index_fallback_avoids_value_floor():
    """Masked cohort pctile but real performance index → non-floor V."""
    v = compute_win_impact_score_v0(
        {
            "games_played_season": 17,
            "position": "LB",
            "proof_composite_index": 1.2,
            "team_win_pct_percentile": 55,
        },
        sport="nfl",
    )
    assert v > 5.5


def test_mahomes_like_value_rises_with_starts_and_team():
    low = compute_win_impact_score_v0(
        {
            "games_played_season": 14,
            "position": "QB",
            "proof_composite_pctile": 85,
        },
        sport="nfl",
    )
    high = compute_win_impact_score_v0(
        {
            "games_played_season": 14,
            "games_started": 14,
            "position": "QB",
            "proof_composite_pctile": 85,
            "team_win_pct": 0.88,
            "team_win_pct_percentile": 95,
            "team_record_observed": 1,
        },
        sport="nfl",
    )
    # Skill inference alone should already lift vs empty participation prior;
    # team context should lift further.
    inferred = compute_win_impact_score_v0(
        {
            "games_played_season": 14,
            "position": "QB",
            "proof_composite_pctile": 85,
            "team_win_pct": 0.88,
            "team_win_pct_percentile": 95,
            "team_record_observed": 1,
        },
        sport="nfl",
    )
    assert 90 <= inferred <= 98
    assert 90 <= high <= 98
    assert high >= low


def test_elite_receiver_archetype_lands_high_but_not_ceiling():
    score = compute_win_impact_score_v0(
        {
            "games_played_season": 17,
            "games_started": 17,
            "position": "WR",
            "proof_composite_pctile": 95,
        },
        sport="nfl",
    )
    assert 85 <= score <= 92


def test_elite_offensive_lineman_missing_box_proof_is_meaningful():
    score = compute_win_impact_score_v0(
        {
            "games_played_season": 17,
            "position": "G",
        },
        sport="nfl",
    )
    assert 60 <= score <= 80


def test_average_starter_and_depth_player_have_real_spread():
    starter = compute_win_impact_score_v0(
        {
            "games_played_season": 17,
            "games_started": 15,
            "position": "LB",
            "proof_composite_pctile": 52,
            "team_win_pct_percentile": 50,
        },
        sport="nfl",
    )
    depth = compute_win_impact_score_v0(
        {
            "games_played_season": 5,
            "games_started": 0,
            "position": "LB",
            "proof_composite_pctile": 25,
            "team_win_pct_percentile": 50,
        },
        sport="nfl",
    )
    assert 55 <= starter <= 75
    assert 25 <= depth < 50
    assert starter > depth


def test_missing_data_shrinks_to_prior_not_floor():
    score = compute_win_impact_score_v0({"position": "OL"}, sport="nfl")
    assert 40 <= score <= 60


def test_multi_mvp_elite_production_reaches_absolute_value_tail():
    score = compute_win_impact_score_v0(
        {
            "position": "C",
            "games_played_season": 36,
            "games_started": 36,
            "proof_composite_pctile": 96,
            "NBARating": 39.3,
            "avgPoints": 21.7,
            "avgRebounds": 9.3,
            "major_awards_json": [
                {"title": "4x MVP · 3x WNBA Champ · 3x Def. POY", "source": "sports_reference"}
            ],
        },
        sport="wnba",
    )
    assert 95 <= score <= 98


def test_wnba_elite_rebounder_gets_high_impact_floor_without_mvp():
    """Double-digit RPG + starter scoring → ~80 Value without award text."""
    score = compute_win_impact_score_v0(
        {
            "position": "F",
            "games_played_season": 30,
            "games_started": 30,
            "proof_composite_pctile": 76,
            "pts": 440.0,
            "reb": 377.0,
        },
        sport="wnba",
    )
    assert 79.0 <= score <= 85.0
    # MVP path remains strictly higher than the rebound floor.
    mvp = compute_win_impact_score_v0(
        {
            "position": "C",
            "games_played_season": 36,
            "games_started": 36,
            "proof_composite_pctile": 96,
            "avgPoints": 23.4,
            "avgRebounds": 10.2,
            "major_awards_json": [
                {"title": "4x MVP · 3x WNBA Champ · 3x Def. POY", "source": "sports_reference"}
            ],
        },
        sport="wnba",
    )
    assert mvp >= 95.0
    assert mvp > score + 10.0


def test_nba_elite_creator_gets_high_impact_floor():
    """NBA high-usage All-Star creators clear the high-80s Impact band."""
    score = compute_win_impact_score_v0(
        {
            "position": "G",
            "games_played_season": 79,
            "proof_composite_pctile": 79,
            "pts": 2_177,
            "reb": 450,
            "ast": 359,
            "all_star_count": 5,
        },
        sport="nba",
    )
    assert 88.0 <= score <= 92.0


def test_elite_nfl_cb_all_pro_and_dpoy_lands_near_impact_band():
    """Multi All-Pro / DPOY every-down defenders clear ~89 Impact without name gates."""
    all_pro = compute_win_impact_score_v0(
        {
            "position": "CB",
            "games_played_season": 16,
            "games_started": 16,
            "proof_composite_pctile": 74,
            "all_pro_count": 3,
        },
        sport="nfl",
    )
    assert 88.0 <= all_pro <= 93.0

    dpoy = compute_win_impact_score_v0(
        {
            "position": "CB",
            "games_played_season": 16,
            "games_started": 16,
            "proof_composite_pctile": 74,
            "all_pro_count": 2,
            "major_awards_json": [
                {"title": "AP Defensive Player of the Year", "source": "sports_reference"}
            ],
        },
        sport="nfl",
    )
    assert 89.0 <= dpoy <= 93.0
    assert dpoy >= all_pro - 1.0
