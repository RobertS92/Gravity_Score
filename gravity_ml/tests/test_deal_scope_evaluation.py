from datetime import date, timedelta

import pytest

from gravity_ml.train.deal_scope_evaluation import (
    calibrate_log_intervals,
    temporal_athlete_purged_split,
)


def _rows(n: int = 120):
    start = date(2024, 1, 1)
    return [
        {
            "transaction_id": f"tx-{i}",
            "athlete_id": f"athlete-{i % 70}",
            "available_at": (start + timedelta(days=i)).isoformat(),
            "amount_usd": 10_000 + i * 100,
        }
        for i in range(n)
    ]


def test_temporal_split_purges_athletes_and_keeps_test_later():
    train, test = temporal_athlete_purged_split(_rows())
    assert max(row["available_at"] for row in train) < min(row["available_at"] for row in test)
    assert {row["athlete_id"] for row in train}.isdisjoint({row["athlete_id"] for row in test})
    assert {row["transaction_id"] for row in train}.isdisjoint({row["transaction_id"] for row in test})


def test_duplicate_transaction_is_rejected():
    rows = _rows(30)
    rows[-1]["transaction_id"] = rows[0]["transaction_id"]
    with pytest.raises(ValueError, match="duplicate transaction"):
        temporal_athlete_purged_split(rows)


def test_interval_calibration_reports_empirical_coverage_and_error():
    rows = _rows(40)
    metrics = calibrate_log_intervals(rows, lambda row: row["amount_usd"] * .9)
    assert metrics["validation_transactions"] == 40
    assert 0 <= metrics["empirical_coverage"] <= 1
    assert metrics["median_absolute_percentage_error"] == pytest.approx(.1)


def test_calibration_rejects_tiny_validation_sample():
    with pytest.raises(ValueError, match="at least 20"):
        calibrate_log_intervals(_rows(19), lambda row: row["amount_usd"])
