"""Training dataset utilities."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from gravity_ml.inference.vectorizer import FeatureVectorizer, build_feature_manifest, stacked_features

VALUE_NIL_LEAK_TOKENS = ("nil_valuation", "nil_deal", "log1p_nil")
META_SKIP = frozenset({
    "entity_id",
    "entity_type",
    "sport",
    "as_of",
    "name",
    "school",
    "position",
    "conference",
    "class_year",
    "target",
    "target_log_nil_usd",
    "target_nil_usd",
    "label_weight",
    "raw_data_json",
})


def discover_value_nil_features(rows: list[dict[str, Any]]) -> list[str]:
    """Leakage-safe numeric feature discovery (matches notebook value_nil rules)."""
    if not rows:
        return build_feature_manifest("value", sport="cfb")
    min_nonnull = max(10, int(len(rows) * 0.02))
    columns: set[str] = set()
    for row in rows:
        columns.update(row.keys())
    numeric: list[str] = []
    for col in sorted(columns):
        if col in META_SKIP or col.startswith("target_") or col.startswith("label_"):
            continue
        if col.endswith("_observed") or col.endswith("_imputed_from") or col.endswith("_raw"):
            continue
        lower = col.lower()
        if any(tok in lower for tok in VALUE_NIL_LEAK_TOKENS):
            continue
        if lower.startswith("json_") and not lower.startswith("json_stat_"):
            continue
        count = 0
        for row in rows:
            val = row.get(col)
            if val is None or val == "":
                continue
            try:
                f = float(val)
            except (TypeError, ValueError):
                continue
            if not math.isnan(f) and not math.isinf(f):
                count += 1
        if count >= min_nonnull:
            numeric.append(col)
    mask_cols = sorted(
        c
        for c in columns
        if c.endswith("_observed")
        and c[:-9] in numeric
        and not any(tok in c.lower() for tok in VALUE_NIL_LEAK_TOKENS)
    )
    return numeric + mask_cols


def rows_to_xy(
    rows: list[dict[str, Any]],
    *,
    objective: str = "value",
    target_key: str = "target",
    label_weight_key: str = "label_weight",
    feature_names: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, FeatureVectorizer]:
    if feature_names is None:
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
