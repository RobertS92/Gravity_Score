"""Tests for gravity-ml sport scoring (inference layer)."""

from __future__ import annotations

import pytest

from gravity_ml.inference import SUPPORTED_SPORTS, score_athlete
from gravity_ml.schemas import ScoreAthleteRequest


def test_supported_sports_count():
    assert len(SUPPORTED_SPORTS) == 8


@pytest.mark.parametrize("sport", SUPPORTED_SPORTS)
def test_score_heuristic_per_sport(sport: str):
    req = ScoreAthleteRequest(
        athlete_id="test-uuid",
        sport=sport,
        raw_data={
            "instagram_followers": 50000,
            "news_count_30d": 12,
            "google_trends_score": 65,
            "proof_performance_index_pctile": 88.0,
            "proof_trajectory_class": "improving_stable",
        },
        model_key=f"gravity_athlete_{sport}_v1",
    )
    out = score_athlete(req)
    assert 0 <= out.gravity_score <= 100
    assert out.sport == sport
    assert out.proof_score >= 15


@pytest.mark.parametrize("sport", ["cfb", "nba", "ncaa_volleyball"])
def test_bpxvr_boosts_proof(sport: str):
    base_req = ScoreAthleteRequest(
        athlete_id="x",
        sport=sport,
        raw_data={"instagram_followers": 10000, "news_count_30d": 5},
    )
    high_req = ScoreAthleteRequest(
        athlete_id="x",
        sport=sport,
        raw_data={
            "instagram_followers": 10000,
            "news_count_30d": 5,
            "proof_performance_index_pctile": 95.0,
            "proof_trajectory_class": "ascending",
        },
    )
    base = score_athlete(base_req).proof_score
    high = score_athlete(high_req).proof_score
    assert high >= base


def test_sport_routes_registered():
    pytest.importorskip("fastapi")
    from gravity_ml.app import create_app

    app = create_app()
    paths = {getattr(r, "path", None) for r in app.routes}
    for sport in SUPPORTED_SPORTS:
        assert f"/score/athlete/{sport}" in paths
