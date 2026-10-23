"""I1 APM ridge skeleton — fixtures only (no live WP10 claim)."""

from __future__ import annotations

import numpy as np
import pytest

from gravity_ml.impact.apm import (
    ImpactDataBlocked,
    assert_live_games_available,
    build_apm_design,
    fit_apm,
    make_fixture_games,
    participation_share,
)
from gravity_ml.impact.fuse import precision_weighted_fuse
from gravity_ml.impact.train_impact import LEAGUE_MODEL_KEYS, run_skeleton
from gravity_ml.train.promotion_gate import PromotionRefused, assert_bundle_promotable


def test_participation_share_basketball():
    import pandas as pd

    row = pd.Series({"minutes": 40.0})
    share, observed = participation_share(row, mode="basketball_minutes", team_minutes=200.0)
    assert observed is True
    assert abs(share - 1.0) < 1e-9  # 40 / (200/5) = 1.0


def test_fit_apm_on_fixture():
    games, box = make_fixture_games(n_games=10, n_players_per_team=5, seed=1)
    result = fit_apm(games, box, mode="basketball_minutes")
    assert result.n_games == 10
    assert result.n_players > 0
    assert len(result.betas) == result.n_players
    assert result.alpha > 0
    assert np.isfinite(result.betas.to_numpy()).all()


def test_build_design_signs():
    games, box = make_fixture_games(n_games=2, n_players_per_team=3, seed=2)
    X, y, names, meta = build_apm_design(games, box, mode="basketball_minutes")
    assert X.shape[0] == 2
    assert "home_court" in names
    assert len(y) == 2
    assert len(meta) == 2


def test_live_games_blocked_when_empty():
    import pandas as pd

    with pytest.raises(ImpactDataBlocked):
        assert_live_games_available(pd.DataFrame(), pd.DataFrame())


def test_fuse_precision_weighted():
    import pandas as pd

    prior = pd.Series({"a": 1.0, "b": 2.0})
    prior_sd = pd.Series({"a": 1.0, "b": 1.0})
    obs = pd.Series({"a": 3.0, "b": np.nan})
    obs_sd = pd.Series({"a": 1.0, "b": 1.0})
    fused = precision_weighted_fuse(prior, prior_sd, obs, obs_sd)
    assert abs(fused.posterior_mean["a"] - 2.0) < 1e-9  # equal precision → mean
    assert fused.posterior_mean["b"] == 2.0


def test_train_impact_fixture_refuses_promote(tmp_path):
    out = run_skeleton(
        league="ncaab_mens",
        version="0.0.1-test",
        out_root=tmp_path,
        promote=False,
        use_fixture=True,
        games_csv=None,
        box_csv=None,
    )
    assert (out / "apm_betas.csv").exists()
    assert (out / "metrics.json").exists()
    import json

    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["label_source"] == "fixture_game_margins"
    model_key = LEAGUE_MODEL_KEYS["ncaab_mens"]
    with pytest.raises(PromotionRefused):
        assert_bundle_promotable(model_key, metrics, label_source="fixture_game_margins")
