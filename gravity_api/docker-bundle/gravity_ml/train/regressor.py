"""Lightweight regressors — sklearn when available, numpy fallback."""

from __future__ import annotations

from typing import Any

import numpy as np


class NumpyRegressor:
    """Ridge-style linear regressor using numpy lstsq."""

    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = alpha
        self.coef_: np.ndarray | None = None
        self.intercept_: float = 0.0

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> NumpyRegressor:
        n_features = X.shape[1]
        if sample_weight is not None and len(sample_weight) == len(y):
            w = np.sqrt(sample_weight)
            Xw = X * w[:, None]
            yw = y * w
        else:
            Xw, yw = X, y
        X_aug = np.hstack([Xw, np.ones((len(Xw), 1))])
        reg = np.eye(n_features + 1) * self.alpha
        reg[-1, -1] = 0.0
        beta = np.linalg.lstsq(X_aug.T @ X_aug + reg, X_aug.T @ yw, rcond=None)[0]
        self.coef_ = beta[:-1]
        self.intercept_ = float(beta[-1])
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.coef_ is None:
            raise RuntimeError("Model not fit")
        return X @ self.coef_ + self.intercept_


def train_regressor(
    X: np.ndarray,
    y: np.ndarray,
    sample_weight: np.ndarray | None = None,
) -> Any:
    try:
        from sklearn.ensemble import GradientBoostingRegressor

        model = GradientBoostingRegressor(
            n_estimators=120,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.85,
            random_state=42,
        )
        model.fit(X, y, sample_weight=sample_weight)
        return model
    except ImportError:
        model = NumpyRegressor(alpha=0.5)
        model.fit(X, y, sample_weight=sample_weight)
        return model
