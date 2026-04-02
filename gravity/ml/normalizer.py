"""Fit-once MinMaxScaler (0–1) for Gravity feature matrix."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.preprocessing import MinMaxScaler

from gravity.ml.feature_engineer import N_FEATURE_COLUMNS


class GravityNormalizer:
    def __init__(self) -> None:
        self._scaler = MinMaxScaler(feature_range=(0.0, 1.0), clip=True)

    def fit(self, X: np.ndarray) -> GravityNormalizer:
        if X.ndim != 2 or X.shape[1] != N_FEATURE_COLUMNS:
            raise ValueError(f"Expected (n, {N_FEATURE_COLUMNS}), got {X.shape}")
        self._scaler.fit(X)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        return self._scaler.transform(X).astype(np.float32)

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        return self.fit(X).transform(X)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"scaler": self._scaler, "n_features": N_FEATURE_COLUMNS}, path)

    @classmethod
    def load(cls, path: str | Path) -> GravityNormalizer:
        data: dict[str, Any] = joblib.load(path)
        g = cls()
        g._scaler = data["scaler"]
        return g


__all__ = ["GravityNormalizer"]
