"""Time-based evaluation harness (SCORING_ML_FIX_SPEC §3 F4).

- Splits only by ``as_of`` (train < T, test ≥ T). No random row splits.
- Paired bootstrap (1,000 resamples) CIs for metric differences vs baseline.
- Writes ``metrics.json`` + markdown report under ``gravity_ml/reports/``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

DEFAULT_BOOTSTRAP_SAMPLES = 1000
REPORTS_ROOT = Path(__file__).resolve().parents[1] / "reports"


@dataclass
class EvalResult:
    model_key: str
    split_at: str
    n_train: int
    n_test: int
    metrics: dict[str, float]
    baseline_metrics: dict[str, float] = field(default_factory=dict)
    deltas: dict[str, Any] = field(default_factory=dict)
    report_path: str | None = None
    metrics_path: str | None = None


def time_split(
    frame: pd.DataFrame,
    *,
    split_at: datetime | str,
    as_of_col: str = "as_of",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (train, test) where train as_of < split_at ≤ test as_of."""
    if as_of_col not in frame.columns:
        raise KeyError(f"Missing {as_of_col!r} column for time split")
    threshold = pd.Timestamp(split_at)
    if threshold.tzinfo is None:
        threshold = threshold.tz_localize("UTC")
    as_of = pd.to_datetime(frame[as_of_col], utc=True)
    train = frame.loc[as_of < threshold].copy()
    test = frame.loc[as_of >= threshold].copy()
    return train, test


def _spearman(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) < 3:
        return float("nan")
    # Rank correlation without requiring scipy.
    rt = pd.Series(y_true).rank().to_numpy()
    rp = pd.Series(y_pred).rank().to_numpy()
    if np.std(rt) == 0 or np.std(rp) == 0:
        return float("nan")
    return float(np.corrcoef(rt, rp)[0, 1])


def _mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if ss_tot == 0:
        return float("nan")
    return 1.0 - ss_res / ss_tot


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "n": float(len(y_true)),
        "mae": round(_mae(y_true, y_pred), 6),
        "rmse": round(_rmse(y_true, y_pred), 6),
        "r2": round(_r2(y_true, y_pred), 6),
        "spearman": round(_spearman(y_true, y_pred), 6),
    }


def paired_bootstrap_delta(
    y_true: np.ndarray,
    y_candidate: np.ndarray,
    y_baseline: np.ndarray,
    *,
    metric_fn: Callable[[np.ndarray, np.ndarray], float],
    n_boot: int = DEFAULT_BOOTSTRAP_SAMPLES,
    seed: int = 7,
    higher_is_better: bool = True,
) -> dict[str, float]:
    """Paired bootstrap CI for (candidate − baseline) metric difference."""
    rng = np.random.default_rng(seed)
    n = len(y_true)
    if n == 0:
        return {"delta": float("nan"), "ci_low": float("nan"), "ci_high": float("nan"), "excludes_zero": False}

    point = metric_fn(y_true, y_candidate) - metric_fn(y_true, y_baseline)
    deltas = np.empty(n_boot, dtype=np.float64)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        deltas[i] = metric_fn(y_true[idx], y_candidate[idx]) - metric_fn(
            y_true[idx], y_baseline[idx]
        )
    ci_low, ci_high = np.quantile(deltas, [0.025, 0.975])
    if higher_is_better:
        excludes_zero = bool(ci_low > 0 or ci_high < 0) and not (ci_low <= 0 <= ci_high)
        # Prefer clear "beats baseline": CI entirely above 0.
        excludes_zero = bool(ci_low > 0)
    else:
        # Lower is better (MAE/RMSE): CI entirely below 0 means candidate better.
        excludes_zero = bool(ci_high < 0)
    return {
        "delta": round(float(point), 6),
        "ci_low": round(float(ci_low), 6),
        "ci_high": round(float(ci_high), 6),
        "excludes_zero": excludes_zero,
    }


def run_eval(
    *,
    model_key: str,
    frame: pd.DataFrame,
    feature_cols: Sequence[str],
    label_col: str,
    split_at: datetime | str,
    predict_fn: Callable[[pd.DataFrame], np.ndarray],
    baseline_predict_fn: Callable[[pd.DataFrame], np.ndarray] | None = None,
    as_of_col: str = "as_of",
    n_boot: int = DEFAULT_BOOTSTRAP_SAMPLES,
    reports_root: Path | None = None,
) -> EvalResult:
    """Evaluate ``predict_fn`` on a held-out time window and write artifacts."""
    train, test = time_split(frame, split_at=split_at, as_of_col=as_of_col)
    if test.empty:
        raise ValueError("Test split is empty — choose an earlier split_at")
    missing = [c for c in feature_cols if c not in frame.columns]
    if missing:
        raise KeyError(f"Missing feature columns: {missing}")
    if label_col not in frame.columns:
        raise KeyError(f"Missing label column: {label_col}")

    y_true = test[label_col].to_numpy(dtype=np.float64)
    y_pred = np.asarray(predict_fn(test), dtype=np.float64)
    if len(y_pred) != len(y_true):
        raise ValueError("predict_fn must return one prediction per test row")

    metrics = regression_metrics(y_true, y_pred)
    baseline_metrics: dict[str, float] = {}
    deltas: dict[str, Any] = {}

    if baseline_predict_fn is not None:
        y_base = np.asarray(baseline_predict_fn(test), dtype=np.float64)
        baseline_metrics = regression_metrics(y_true, y_base)
        deltas = {
            "spearman": paired_bootstrap_delta(
                y_true, y_pred, y_base, metric_fn=_spearman, n_boot=n_boot, higher_is_better=True
            ),
            "mae": paired_bootstrap_delta(
                y_true, y_pred, y_base, metric_fn=_mae, n_boot=n_boot, higher_is_better=False
            ),
            "rmse": paired_bootstrap_delta(
                y_true, y_pred, y_base, metric_fn=_rmse, n_boot=n_boot, higher_is_better=False
            ),
        }

    result = EvalResult(
        model_key=model_key,
        split_at=str(split_at),
        n_train=int(len(train)),
        n_test=int(len(test)),
        metrics=metrics,
        baseline_metrics=baseline_metrics,
        deltas=deltas,
    )
    metrics_path, report_path = write_eval_artifacts(result, reports_root=reports_root)
    result.metrics_path = str(metrics_path)
    result.report_path = str(report_path)
    return result


def write_eval_artifacts(
    result: EvalResult,
    *,
    reports_root: Path | None = None,
    timestamp: str | None = None,
) -> tuple[Path, Path]:
    root = reports_root or REPORTS_ROOT
    ts = timestamp or datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = root / result.model_key
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = out_dir / f"{ts}.metrics.json"
    report_path = out_dir / f"{ts}.md"

    payload = asdict(result)
    metrics_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# Eval report — `{result.model_key}`",
        "",
        f"- Split at: `{result.split_at}`",
        f"- Train rows: {result.n_train}",
        f"- Test rows: {result.n_test}",
        "",
        "## Candidate metrics",
        "",
        "```json",
        json.dumps(result.metrics, indent=2),
        "```",
        "",
    ]
    if result.baseline_metrics:
        lines += [
            "## Baseline metrics",
            "",
            "```json",
            json.dumps(result.baseline_metrics, indent=2),
            "```",
            "",
            "## Paired bootstrap deltas (candidate − baseline)",
            "",
            "```json",
            json.dumps(result.deltas, indent=2),
            "```",
            "",
        ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return metrics_path, report_path
