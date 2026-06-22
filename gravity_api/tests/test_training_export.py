"""Tests for training CSV export flatten helpers."""

from __future__ import annotations

from gravity_api.services.training_export import (
    build_training_row,
    flatten_raw_data,
    flatten_snapshot_features,
    rows_to_csv,
)


def test_flatten_raw_extracts_followers():
    raw = {"instagram_followers": 50000, "nil_deals": [{"brand": "Nike", "value": 100000, "verified": True}]}
    flat = flatten_raw_data(raw)
    assert flat["instagram_followers"] == 50000
    assert flat["nil_deal_count_raw"] == 1
    assert flat["nil_deal_max_usd"] == 100000


def test_flatten_snapshot_composite_pctile():
    features = {
        "proof": {
            "composite_pctile": 88.5,
            "composite_tier": "high",
            "trajectory_class": "improving_stable",
            "profile_cards": {
                "proof.performance_index": {
                    "level_raw": 1.2,
                    "level_pctile": 88.5,
                    "masked": False,
                }
            },
        }
    }
    flat = flatten_snapshot_features(features)
    assert flat["proof_composite_pctile"] == 88.5
    assert flat["proof_performance_index_pctile"] == 88.5


def test_build_row_proxy_targets():
    row = build_training_row(
        entity_id="abc",
        entity_type="athlete",
        sport="cfb",
        as_of="2026-01-01",
        scores={"dollar_p50_usd": 200_000, "proof_score": 75, "gravity_score": 80},
    )
    assert row["target_nil_usd"] == 200_000
    assert row["target_log_nil_usd"] is not None
    assert row["target_quality"] == 75


def test_rows_to_csv_header():
    csv_text = rows_to_csv([{"entity_id": "a", "sport": "cfb", "gravity_score": 80}])
    assert "entity_id" in csv_text.splitlines()[0]
    assert "cfb" in csv_text
