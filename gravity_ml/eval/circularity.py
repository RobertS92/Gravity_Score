"""Circularity detector (SCORING_ML_FIX_SPEC §3 F3).

Fit HistGradientBoostingRegressor features → label; holdout R² ≥ 0.95 means the
label is (near-)deterministic from the feature set — the failure mode behind
M1, M3, and M4.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split


def circularity_holdout_r2(
    X: np.ndarray,
    y: np.ndarray,
    *,
    test_size: float = 0.25,
    seed: int = 42,
    max_iter: int = 80,
) -> float:
    """Return holdout R² of a small HGBR fit. High values imply label leakage."""
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if len(y) < 20:
        raise ValueError("Need ≥20 rows for circularity holdout check")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed
    )
    model = HistGradientBoostingRegressor(
        max_depth=4,
        max_iter=max_iter,
        learning_rate=0.08,
        random_state=seed,
    )
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    return float(r2_score(y_test, pred))


def assert_not_circular(
    X: np.ndarray,
    y: np.ndarray,
    *,
    max_r2: float = 0.95,
    label: str = "objective",
    **kwargs: Any,
) -> float:
    """Raise AssertionError if holdout R² ≥ max_r2."""
    r2 = circularity_holdout_r2(X, y, **kwargs)
    if r2 >= max_r2:
        raise AssertionError(
            f"Circularity gate failed for {label}: holdout R²={r2:.4f} ≥ {max_r2}. "
            "Label is too predictable from features (see M1/M3/M4)."
        )
    return r2
