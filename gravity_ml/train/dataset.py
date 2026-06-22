"""Training dataset utilities."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from gravity_ml.inference.vectorizer import FeatureVectorizer, build_feature_manifest, stacked_features


def rows_to_xy(
    rows: list[dict[str, Any]],
    *,
    objective: str = "value",
    target_key: str = "target",
    label_weight_key: str = "label_weight",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, FeatureVectorizer]:
    feature_names = build_feature_manifest(objective)
    vectorizer = FeatureVectorizer(feature_names)
    X_list: list[np.ndarray] = []
    y_list: list[float] = []
    w_list: list[float] = []

    for row in rows:
        target = row.get(target_key)
        if target is None:
            continue
        try:
            y_val = float(target)
        except (TypeError, ValueError):
            continue
        if math.isnan(y_val) or math.isinf(y_val):
            continue
        values, mask = vectorizer.vectorize(row)
        X_list.append(stacked_features(values, mask))
        y_list.append(y_val)
        w_list.append(float(row.get(label_weight_key) or row.get("label_confidence") or 1.0))

    if not X_list:
        raise ValueError("No training rows with valid targets")
    return np.vstack(X_list), np.array(y_list), np.array(w_list), vectorizer


def chronological_split(
    rows: list[dict[str, Any]],
    *,
    train_frac: float = 0.7,
    val_frac: float = 0.15,
) -> tuple[list[dict], list[dict], list[dict]]:
    sorted_rows = sorted(rows, key=lambda r: str(r.get("as_of") or ""))
    n = len(sorted_rows)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))
    return sorted_rows[:train_end], sorted_rows[train_end:val_end], sorted_rows[val_end:]
