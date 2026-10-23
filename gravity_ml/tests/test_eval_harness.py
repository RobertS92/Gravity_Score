"""F4 — time-split eval harness + bootstrap deltas."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gravity_ml.eval.harness import run_eval, time_split


def _frame(n: int = 80) -> pd.DataFrame:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = []
    rng = np.random.default_rng(0)
    for i in range(n):
        as_of = start + timedelta(days=i * 7)
        x = float(i)
        rows.append(
            {
                "as_of": as_of,
                "feat_a": x + rng.normal(0, 0.5),
                "feat_b": rng.normal(),
                "label": x + rng.normal(0, 1.0),
            }
        )
    return pd.DataFrame(rows)


def test_time_split_is_strictly_temporal():
    df = _frame(40)
    split_at = datetime(2024, 6, 1, tzinfo=timezone.utc)
    train, test = time_split(df, split_at=split_at)
    assert (pd.to_datetime(train["as_of"], utc=True) < pd.Timestamp(split_at)).all()
    assert (pd.to_datetime(test["as_of"], utc=True) >= pd.Timestamp(split_at)).all()
    assert len(train) + len(test) == len(df)


def test_run_eval_writes_metrics_and_report(tmp_path: Path):
    df = _frame(60)
    split_at = datetime(2024, 8, 1, tzinfo=timezone.utc)

    def predict(test: pd.DataFrame) -> np.ndarray:
        return test["feat_a"].to_numpy(dtype=float)

    def baseline(test: pd.DataFrame) -> np.ndarray:
        return np.full(len(test), float(test["label"].mean()))

    result = run_eval(
        model_key="unit_test_model",
        frame=df,
        feature_cols=["feat_a", "feat_b"],
        label_col="label",
        split_at=split_at,
        predict_fn=predict,
        baseline_predict_fn=baseline,
        n_boot=50,
        reports_root=tmp_path,
    )
    assert result.n_test > 0
    assert result.metrics_path and Path(result.metrics_path).exists()
    assert result.report_path and Path(result.report_path).exists()
    assert "spearman" in result.deltas
    report = Path(result.report_path).read_text(encoding="utf-8")
    assert "Eval report" in report


def test_rejects_empty_test_split():
    df = _frame(10)
    with pytest.raises(ValueError, match="Test split is empty"):
        run_eval(
            model_key="empty",
            frame=df,
            feature_cols=["feat_a"],
            label_col="label",
            split_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
            predict_fn=lambda t: t["feat_a"].to_numpy(),
            reports_root=Path("/tmp"),
        )
