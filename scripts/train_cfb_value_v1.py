#!/usr/bin/env python3
"""Train gravity_athlete_cfb_value_v1 from observed NIL valuation labels."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg
import numpy as np

from gravity_api.config import get_settings
from gravity_api.services.training_export import (
    build_training_row,
    flatten_raw_data,
    flatten_raw_data_export,
    flatten_snapshot_features,
)
from gravity_ml.train.dataset import chronological_split, discover_value_nil_features, rows_to_xy
from gravity_ml.train.regressor import train_regressor
from gravity_ml.train.train_champion import evaluate_regression, save_bundle

logger = logging.getLogger(__name__)


async def fetch_cfb_value_rows(*, limit: int | None = None) -> list[dict]:
    """Load CFB athletes with observed NIL valuations (nil_valuation_observed=1)."""
    conn = await asyncpg.connect(get_settings().pg_dsn, statement_cache_size=0)
    rows_out: list[dict] = []
    try:
        sql = """
            SELECT a.id, a.name, a.school, a.position, a.sport,
                   r.raw_data, r.scraped_at,
                   s.features AS snapshot_features
            FROM athletes a
            JOIN LATERAL (
              SELECT raw_data, scraped_at FROM raw_athlete_data
              WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
            ) r ON TRUE
            LEFT JOIN LATERAL (
              SELECT features FROM gravity_feature_snapshots
              WHERE entity_id::text = a.id::text ORDER BY as_of DESC NULLS LAST LIMIT 1
            ) s ON TRUE
            WHERE a.sport = 'cfb'
              AND COALESCE(a.is_active, TRUE) = TRUE
              AND (r.raw_data->>'nil_valuation')::double precision > 0
              AND COALESCE((r.raw_data->>'nil_valuation_observed')::int, 0) = 1
            ORDER BY r.scraped_at DESC NULLS LAST
        """
        if limit:
            sql += f" LIMIT {int(limit)}"
        db_rows = await conn.fetch(sql)
        for row in db_rows:
            raw = row["raw_data"]
            if isinstance(raw, str):
                raw = json.loads(raw)
            if not isinstance(raw, dict):
                continue
            nil_usd = float(raw.get("nil_valuation") or 0)
            if nil_usd <= 0:
                continue
            snap = row["snapshot_features"]
            if isinstance(snap, str):
                snap = json.loads(snap)
            flat_snap = flatten_snapshot_features(snap if isinstance(snap, dict) else None)
            merged = {**flat_snap, **flatten_raw_data_export(raw), **flatten_raw_data(raw), **raw}
            training_row = build_training_row(
                entity_id=str(row["id"]),
                entity_type="athlete",
                sport="cfb",
                as_of=str(row["scraped_at"] or ""),
                identity={
                    "name": row["name"],
                    "school": row["school"],
                    "position": row["position"],
                },
                raw_data=raw,
                snapshot_features=snap if isinstance(snap, dict) else None,
            )
            training_row.update({k: v for k, v in merged.items() if k not in training_row})
            training_row["target"] = math.log1p(nil_usd)
            training_row["target_log_nil_usd"] = training_row["target"]
            training_row["target_nil_usd"] = nil_usd
            training_row["label_weight"] = float(
                raw.get("data_quality_score") or raw.get("nil_valuation_confidence") or 0.7
            )
            rows_out.append(training_row)
    finally:
        await conn.close()
    return rows_out


def _spearman(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) < 3:
        return 0.0
    ranks_true = np.argsort(np.argsort(y_true))
    ranks_pred = np.argsort(np.argsort(y_pred))
    corr = np.corrcoef(ranks_true, ranks_pred)[0, 1]
    return float(corr) if not np.isnan(corr) else 0.0


def train_cfb_value_bundle(
    rows: list[dict],
    *,
    version: str,
    out_root: Path,
    augment: bool = True,
) -> Path | None:
    if len(rows) < 30:
        return None
    feature_names = discover_value_nil_features(rows)
    train_rows, val_rows, test_rows = chronological_split(rows)

    if augment:
        import random

        rng = random.Random(42)
        aug_train: list[dict] = list(train_rows)
        for _ in range(len(train_rows)):
            src = train_rows[rng.randrange(len(train_rows))]
            boot = dict(src)
            boot["entity_id"] = f"aug-{boot.get('entity_id', 'x')}-{rng.randrange(10000)}"
            boot["label_weight"] = float(boot.get("label_weight") or 0.7) * 0.95
            aug_train.append(boot)
        train_rows = aug_train

    X_train, y_train, w_train, vectorizer = rows_to_xy(
        train_rows, objective="value", feature_names=feature_names
    )
    model = train_regressor(X_train, y_train, w_train)

    X_val, y_val, _, _ = rows_to_xy(val_rows, objective="value", feature_names=feature_names)
    X_test, y_test, _, _ = rows_to_xy(test_rows, objective="value", feature_names=feature_names)
    val_pred = model.predict(X_val)
    test_pred = model.predict(X_test)

    val_metrics = evaluate_regression(y_val, val_pred)
    test_metrics = evaluate_regression(y_test, test_pred)
    val_metrics["spearman"] = round(_spearman(y_val, val_pred), 4)
    test_metrics["spearman"] = round(_spearman(y_test, test_pred), 4)
    val_metrics["n"] = len(val_rows)
    test_metrics["n"] = len(test_rows)

    metrics = {
        "validation": val_metrics,
        "test": test_metrics,
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "test_rows": len(test_rows),
        "training_source": "observed_nil_valuation",
        "labeled_rows": len(rows),
        "augmented": augment,
        "feature_count": len(feature_names),
    }

    out_dir = out_root / "gravity_athlete_cfb_value_v1" / version
    save_bundle(
        out_dir,
        model=model,
        vectorizer=vectorizer,
        entity_type="athlete",
        sport="cfb",
        objective="value",
        version=version,
        metrics=metrics,
        row_count=len(rows),
    )
    manifest_path = out_dir / "training_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["training_source"] = "observed_nil_valuation"
    manifest["label_target"] = "nil_valuation_usd"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    logger.info("Saved bundle %s metrics=%s", out_dir, metrics)
    return out_dir


def update_index(out_root: Path, model_key: str, version: str) -> None:
    index_path = out_root / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        index = {"champions": {}}
    index.setdefault("champions", {})[model_key] = version
    from datetime import datetime, timezone

    index["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train CFB value_v1 on observed NIL labels")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--version", default="1.1.0-beta")
    parser.add_argument("--min-rows", type=int, default=80)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    rows = asyncio.run(fetch_cfb_value_rows(limit=args.limit))
    logger.info("Fetched %d CFB rows with observed NIL labels", len(rows))
    if len(rows) < args.min_rows:
        raise SystemExit(f"Need >= {args.min_rows} observed NIL rows, got {len(rows)}")

    out_root = ROOT / "models" / "bundles"
    out_dir = train_cfb_value_bundle(rows, version=args.version, out_root=out_root)
    if not out_dir:
        raise SystemExit("Training failed — insufficient rows after split")
    update_index(out_root, "gravity_athlete_cfb_value_v1", args.version)
    logger.info("Bundle written: %s", out_dir)


if __name__ == "__main__":
    main()
