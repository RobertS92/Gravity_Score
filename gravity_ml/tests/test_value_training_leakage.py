"""Leakage guards for commercial value-model feature discovery."""

from gravity_ml.train.dataset import discover_value_nil_features


def test_observed_market_labels_and_contract_fields_are_never_features():
    rows = [
        {
            "entity_id": str(i),
            "target": 15.0 + i,
            "games_played_season": 10 + i,
            "contract_aav_usd": 1_000_000 + i,
            "salary_annual": 2_000_000 + i,
            "observed_market_value_usd": 3_000_000 + i,
        }
        for i in range(20)
    ]
    features = discover_value_nil_features(rows)
    assert "games_played_season" in features
    assert "contract_aav_usd" not in features
    assert "salary_annual" not in features
    assert "observed_market_value_usd" not in features
