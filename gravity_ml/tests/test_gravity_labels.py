"""G1 label builders + banned-source enforcement."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gravity_ml.gravity.labels import (
    build_l_attention_90,
    build_l_deal_180,
    build_l_dollars,
    build_l_game_margin,
    build_l_unavail_180,
    make_deal_label_fixture,
    register_gravity_builders,
)
from gravity_ml.labels.registry import get_label, validate_registry
from gravity_ml.train.promotion_gate import PromotionRefused, assert_label_source_allowed


def test_registry_builders_are_real_callables():
    register_gravity_builders(overwrite=True)
    validate_registry()
    assert get_label("L_deal_180").builder is build_l_deal_180
    assert get_label("L_game_margin").builder is build_l_game_margin


def test_l_deal_180_window_and_coverage():
    snapshots, deals = make_deal_label_fixture()
    out = build_l_deal_180(snapshots, deals)
    # a1 @ 2025-01-01 → deal 2025-03-15 in window
    row = out[(out.athlete_id == "a1") & (out.as_of == snapshots.loc[0, "as_of"])].iloc[0]
    assert int(row["L_deal_180"]) == 1
    assert bool(row["coverage_ok"]) is True
    # a2 deal is before as_of → 0
    row2 = out[out.athlete_id == "a2"].iloc[0]
    assert int(row2["L_deal_180"]) == 0


def test_l_attention_90():
    snapshots = pd.DataFrame(
        {
            "athlete_id": ["a1"],
            "as_of": pd.to_datetime(["2025-01-01"], utc=True),
            "trusted_social_reach": [1000.0],
        }
    )
    future = pd.DataFrame(
        {
            "athlete_id": ["a1"],
            "as_of": pd.to_datetime(["2025-04-01"], utc=True),
            "trusted_social_reach": [2000.0],
        }
    )
    out = build_l_attention_90(snapshots, future)
    assert abs(float(out.iloc[0]["L_attention_90"]) - np.log(2.0)) < 1e-9


def test_l_dollars_rejects_on3_column():
    snapshots = pd.DataFrame(
        {"athlete_id": ["a1"], "as_of": pd.to_datetime(["2025-01-01"], utc=True)}
    )
    bad = pd.DataFrame(
        {
            "athlete_id": ["a1"],
            "deal_date": pd.to_datetime(["2024-06-01"], utc=True),
            "amount_usd": [1000],
            "nil_valuation": [999],
        }
    )
    with pytest.raises(ValueError, match="non-verified"):
        build_l_dollars(snapshots, bad)


def test_l_unavail_and_game_margin():
    snapshots = pd.DataFrame(
        {"athlete_id": ["a1"], "as_of": pd.to_datetime(["2025-01-01"], utc=True)}
    )
    events = pd.DataFrame(
        {
            "athlete_id": ["a1"],
            "event_date": pd.to_datetime(["2025-02-01"], utc=True),
            "event_type": ["transfer_portal"],
        }
    )
    u = build_l_unavail_180(snapshots, events)
    assert int(u.iloc[0]["L_unavail_180"]) == 1
    games = pd.DataFrame({"home_score": [80, 70], "away_score": [70, 75]})
    margins = build_l_game_margin(games)
    assert list(margins) == [10.0, -5.0]


def test_banned_label_sources_cannot_promote():
    with pytest.raises(PromotionRefused, match="banned"):
        assert_label_source_allowed("athlete_gravity_scores")
    with pytest.raises(PromotionRefused, match="banned"):
        assert_label_source_allowed("compute_win_impact_score_v0")
    with pytest.raises(PromotionRefused, match="banned"):
        assert_label_source_allowed("raw_composite_score")
