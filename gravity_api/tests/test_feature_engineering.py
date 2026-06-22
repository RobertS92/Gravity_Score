"""Tests for BPXVR feature engineering — all sports, all positions."""

from __future__ import annotations

import pytest

from gravity_api.feature_engineering.composites import (
    blend_proof_with_recruiting_prior,
    compute_performance_index,
)
from gravity_api.feature_engineering.engine import FeatureEngineeringEngine
from gravity_api.feature_engineering.positions import (
    BASEBALL_POSITIONS,
    BASKETBALL_POSITIONS,
    FOOTBALL_POSITIONS,
    VOLLEYBALL_POSITIONS,
    derive_position_group,
)
from gravity_api.feature_engineering.profile_card import build_proof_profile_card
from gravity_api.feature_engineering.sport_specs import (
    ALL_SPORT_SPECS,
    all_position_groups,
    export_specs_json,
    get_position_spec,
    get_sport_spec,
)
from gravity_api.feature_engineering.trajectory import classify_trajectory
from gravity_api.feature_engineering.transforms import percentile_rank, tier_from_percentile
from gravity_api.feature_engineering.types import TierLabel, TrajectoryClass


EXPECTED_SPORTS = (
    "cfb",
    "ncaab_mens",
    "ncaab_womens",
    "ncaa_baseball",
    "ncaa_volleyball",
    "nfl",
    "nba",
    "wnba",
)


@pytest.mark.parametrize("sport", EXPECTED_SPORTS)
def test_sport_spec_has_all_positions(sport: str):
    spec = get_sport_spec(sport)
    groups = all_position_groups(sport)
    assert len(groups) >= 5
    if sport in ("cfb", "nfl"):
        assert set(groups) == set(FOOTBALL_POSITIONS)
    elif sport in ("ncaab_mens", "ncaab_womens", "nba", "wnba"):
        assert set(groups) == set(BASKETBALL_POSITIONS)
    elif sport == "ncaa_baseball":
        assert set(groups) == set(BASEBALL_POSITIONS)
    elif sport == "ncaa_volleyball":
        assert set(groups) == set(VOLLEYBALL_POSITIONS)


@pytest.mark.parametrize("sport", EXPECTED_SPORTS)
def test_every_position_has_performance_stats(sport: str):
    spec = get_sport_spec(sport)
    for pg in spec.position_groups:
        assert pg.performance_stats, f"{sport}/{pg.position_group} missing stats"
        total_w = sum(s.weight for s in pg.performance_stats)
        assert 0.99 <= total_w <= 1.15, f"{sport}/{pg.position_group} weights={total_w}"


@pytest.mark.parametrize("sport", EXPECTED_SPORTS)
def test_bpxvr_metrics_defined(sport: str):
    spec = get_sport_spec(sport)
    assert len(spec.brand_metrics) >= 5
    assert len(spec.proximity_metrics) >= 3
    assert len(spec.velocity_metrics) >= 5
    assert len(spec.risk_metrics) >= 4


def test_pro_sports_have_college_bridge():
    for sport in ("nfl", "nba", "wnba"):
        assert get_sport_spec(sport).college_pro_bridge is True
    for sport in ("cfb", "ncaab_mens", "ncaa_baseball"):
        assert get_sport_spec(sport).college_pro_bridge is False


def test_total_position_group_count():
    manifest = export_specs_json()
    total = sum(len(s["position_groups"]) for s in manifest["sports"].values())
    # 9 football × 2 + 5 basketball × 4 + 6 baseball + 5 volleyball = 18 + 20 + 6 + 5 = 49
    assert total == 49


def test_derive_position_group_baseball_volleyball():
    assert derive_position_group("SS", "ncaa_baseball") == "IF"
    assert derive_position_group("CL", "ncaa_baseball") == "RP"
    assert derive_position_group("LIB", "ncaa_volleyball") == "LIB"
    assert derive_position_group("OH", "ncaa_volleyball") == "OH"


def test_percentile_and_tier():
    values = list(range(1, 101))
    assert percentile_rank(values, 95) == 95.0
    assert tier_from_percentile(92) == TierLabel.ELITE
    assert tier_from_percentile(96) == TierLabel.GENERATIONAL
    assert tier_from_percentile(82) == TierLabel.HIGH


def test_trajectory_improving_stable():
    cls = classify_trajectory(yoy_pct=0.15, history=[1.0, 1.1, 1.25])
    assert cls in (TrajectoryClass.IMPROVING, TrajectoryClass.IMPROVING_STABLE, TrajectoryClass.ASCENDING)


def test_trajectory_unstable():
    cls = classify_trajectory(yoy_pct=0.20, history=[1.0, 2.5, 0.8, 2.2])
    assert cls in (TrajectoryClass.UNSTABLE, TrajectoryClass.IMPROVING_UNSTABLE)


def test_proof_profile_card_with_cohort():
    cohort = [float(i) for i in range(50)]
    card = build_proof_profile_card(
        performance_index=45.0,
        index_history=[30.0, 38.0, 45.0],
        cohort_index_values=cohort,
        games_played=10,
        min_games=4,
    )
    assert card.level_pctile is not None
    assert card.level_pctile >= 85
    assert card.delta_yoy_pct is not None
    assert card.level_tier in (TierLabel.ELITE, TierLabel.GENERATIONAL, TierLabel.HIGH)


def test_performance_index_cfb_qb():
    pos = get_position_spec("cfb", "QB")
    stats = {
        "pass_yards": 3500,
        "pass_td": 30,
        "passer_rating": 155,
        "qbr": 75,
        "completion_pct": 65,
        "pass_int": 8,
        "rush_yards": 200,
    }
    means = {s.stat_key: stats[s.stat_key] * 0.8 for s in pos.performance_stats}
    stds = {s.stat_key: stats[s.stat_key] * 0.2 for s in pos.performance_stats}
    idx = compute_performance_index(
        sport="cfb",
        position_group="QB",
        season_stats=stats,
        cohort_means=means,
        cohort_stds=stds,
    )
    assert idx is not None
    assert idx > 0


def test_recruiting_blend():
    blended = blend_proof_with_recruiting_prior(60.0, 90.0, games_played=2, expected_games=12)
    assert blended is not None
    assert blended > 60.0


def test_engine_builds_full_snapshot():
    engine = FeatureEngineeringEngine()
    raw = {
        "pass_yards": 3200,
        "pass_td": 28,
        "passer_rating": 148,
        "qbr": 70,
        "completion_pct": 63,
        "pass_int": 10,
        "rush_yards": 150,
        "games_played_season": 11,
        "instagram_followers": 120000,
        "tiktok_followers": 80000,
        "engagement_quality": 0.05,
        "nil_valuation": 500000,
        "nil_deal_count": 3,
        "cohort_performance_index_values": [float(x) for x in range(40)],
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
        "proof.performance_index_history": [0.5, 0.8, 1.1],
    }
    snap = engine.build_snapshot(
        entity_id="test-id",
        sport="cfb",
        position="QB",
        season_year=2025,
        raw=raw,
    )
    assert snap.proof.composite_index is not None
    assert snap.proof.profile_cards["proof.performance_index"].level_tier != TierLabel.UNKNOWN
    assert snap.brand.profile_cards
    assert snap.league == "ncaa"
    d = snap.to_dict()
    assert "proof" in d
    assert d["entity"]["position_group"] == "QB"


@pytest.mark.parametrize("sport,position", [
    ("nfl", "DE"),
    ("nba", "PG"),
    ("wnba", "C"),
    ("ncaa_baseball", "SP"),
    ("ncaa_volleyball", "OH"),
    ("ncaab_womens", "SF"),
])
def test_engine_accepts_all_sport_positions(sport: str, position: str):
    engine = FeatureEngineeringEngine()
    snap = engine.build_snapshot(
        entity_id="x",
        sport=sport,
        position=position,
        season_year=2025,
        raw={"games_played_season": 20, "pts": 15, "ast": 5, "reb": 4},
    )
    assert snap.position_group == derive_position_group(position, sport)
