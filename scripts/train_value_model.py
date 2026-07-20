#!/usr/bin/env python3
"""Train a per-sport athlete value model from observed market-value labels.

Generalizes scripts/train_cfb_value_v1.py to any sport by sourcing the training
target from athlete_value_labels (real contracts/salaries) instead of the
CFB-only raw_data.nil_valuation field. Target = log1p(value_usd).

The bundle format, feature discovery, split, augmentation, and gating mirror the
CFB champion exactly, so the produced bundles are drop-in for the scorer.

Usage:
  PYTHONPATH=. .venv/bin/python scripts/train_value_model.py --sport nfl --version 1.0.0
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import sys
from datetime import datetime, timezone
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


async def fetch_value_rows(sport: str, *, limit: int | None = None) -> list[dict]:
    """Load athletes for a sport with an observed market-value label.

    Picks the highest-value label per athlete (a player's headline contract /
    salary) as the training target.
    """
    conn = await asyncpg.connect(get_settings().pg_dsn, statement_cache_size=0, timeout=90, command_timeout=600)
    rows_out: list[dict] = []
    try:
        # This training read joins raw_athlete_data + gravity_feature_snapshots
        # per athlete; for large rosters (NFL ~2.8k) it exceeds the server's
        # default statement_timeout. Lift it for this read-only session.
        await conn.execute("SET statement_timeout = 0")
        sql = """
            SELECT a.id, a.name, a.school, a.current_team AS team, a.position, a.sport,
                   r.raw_data, r.scraped_at,
                   s.features AS snapshot_features,
                   lbl.value_usd, lbl.label_type, lbl.confidence
            FROM athletes a
            JOIN LATERAL (
              SELECT value_usd, label_type, confidence FROM athlete_value_labels
              WHERE athlete_id = a.id ORDER BY value_usd DESC LIMIT 1
            ) lbl ON TRUE
            JOIN LATERAL (
              SELECT raw_data, scraped_at FROM raw_athlete_data
              WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
            ) r ON TRUE
            LEFT JOIN LATERAL (
              SELECT features FROM gravity_feature_snapshots
              WHERE entity_id::text = a.id::text ORDER BY as_of DESC NULLS LAST LIMIT 1
            ) s ON TRUE
            WHERE a.sport = $1
              AND COALESCE(a.is_active, TRUE) = TRUE
              AND lbl.value_usd > 0
            ORDER BY r.scraped_at DESC NULLS LAST
        """
        if limit:
            sql += f" LIMIT {int(limit)}"
        db_rows = await conn.fetch(sql, sport)
        for row in db_rows:
            raw = row["raw_data"]
            if isinstance(raw, str):
                raw = json.loads(raw)
            if not isinstance(raw, dict):
                continue
            value_usd = float(row["value_usd"] or 0)
            if value_usd <= 0:
                continue
            snap = row["snapshot_features"]
            if isinstance(snap, str):
                snap = json.loads(snap)
            flat_snap = flatten_snapshot_features(snap if isinstance(snap, dict) else None)
            merged = {**flat_snap, **flatten_raw_data_export(raw), **flatten_raw_data(raw), **raw}
            training_row = build_training_row(
                entity_id=str(row["id"]),
                entity_type="athlete",
                sport=sport,
                as_of=str(row["scraped_at"] or ""),
                identity={
                    "name": row["name"],
                    "school": row["school"],
                    "team": row["team"],
                    "position": row["position"],
                },
                raw_data=raw,
                snapshot_features=snap if isinstance(snap, dict) else None,
            )
            training_row.update({k: v for k, v in merged.items() if k not in training_row})
            training_row["target"] = math.log1p(value_usd)
            training_row["target_log_nil_usd"] = training_row["target"]
            training_row["target_nil_usd"] = value_usd
            training_row["label_weight"] = float(row["confidence"] or 0.8)
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


def train_value_bundle(
    rows: list[dict],
    *,
    sport: str,
    model_key: str,
    version: str,
    out_root: Path,
    label_type: str,
    augment: bool = True,
) -> tuple[Path | None, dict]:
    if len(rows) < 30:
        return None, {"error": "insufficient rows", "rows": len(rows)}
    feature_names = discover_value_nil_features(rows)
    train_rows, val_rows, test_rows = chronological_split(rows)

    if augment:
        import random

        rng = random.Random(42)
        aug_train = list(train_rows)
        for _ in range(len(train_rows)):
            src = train_rows[rng.randrange(len(train_rows))]
            boot = dict(src)
            boot["entity_id"] = f"aug-{boot.get('entity_id', 'x')}-{rng.randrange(10000)}"
            boot["label_weight"] = float(boot.get("label_weight") or 0.8) * 0.95
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
        "training_source": f"observed_{label_type}",
        "labeled_rows": len(rows),
        "augmented": augment,
        "feature_count": len(feature_names),
    }

    out_dir = out_root / model_key / version
    save_bundle(
        out_dir,
        model=model,
        vectorizer=vectorizer,
        entity_type="athlete",
        sport=sport,
        objective="value",
        version=version,
        metrics=metrics,
        row_count=len(rows),
    )
    manifest_path = out_dir / "training_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["training_source"] = f"observed_{label_type}"
    manifest["label_target"] = f"{label_type}_usd"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    logger.info("Saved bundle %s metrics=%s", out_dir, metrics)
    return out_dir, metrics


def update_index(out_root: Path, model_key: str, version: str) -> None:
    index_path = out_root / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"champions": {}}
    index.setdefault("champions", {})[model_key] = version
    index["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train per-sport value model from observed labels")
    parser.add_argument("--sport", required=True)
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--min-rows", type=int, default=80)
    parser.add_argument("--min-spearman", type=float, default=0.35, help="Test Spearman gate for promotion")
    parser.add_argument("--no-promote", action="store_true", help="Train + evaluate but do not update champions")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    rows = asyncio.run(fetch_value_rows(args.sport, limit=args.limit))
    logger.info("Fetched %d %s rows with observed value labels", len(rows), args.sport)
    if len(rows) < args.min_rows:
        raise SystemExit(f"Need >= {args.min_rows} labeled rows, got {len(rows)}")

    label_type = "contract_apy" if args.sport == "nfl" else "salary_annual"
    model_key = f"gravity_athlete_{args.sport}_value_v1"
    out_root = ROOT / "models" / "bundles"
    out_dir, metrics = train_value_bundle(
        rows,
        sport=args.sport,
        model_key=model_key,
        version=args.version,
        out_root=out_root,
        label_type=label_type,
    )
    if not out_dir:
        raise SystemExit(f"Training failed: {metrics}")

    test_sp = float(metrics.get("test", {}).get("spearman") or 0.0)
    logger.info("=== %s test Spearman=%.4f (gate=%.2f) ===", model_key, test_sp, args.min_spearman)
    if args.no_promote:
        logger.info("--no-promote set; bundle written but NOT promoted to champion")
    elif test_sp >= args.min_spearman:
        update_index(out_root, model_key, args.version)
        logger.info("PROMOTED %s -> champions[%s]", model_key, args.version)
    else:
        logger.warning(
            "NOT promoted: test Spearman %.4f below gate %.2f. Bundle saved at %s for inspection.",
            test_sp,
            args.min_spearman,
            out_dir,
        )


if __name__ == "__main__":
    main()
