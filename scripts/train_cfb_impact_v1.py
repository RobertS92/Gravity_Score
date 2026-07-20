#!/usr/bin/env python3
"""Train gravity_athlete_cfb_impact_v1 from DB export rows."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg

from gravity_api.config import get_settings
from gravity_api.services.training_export import build_training_row, flatten_raw_data, flatten_snapshot_features
from gravity_api.services.win_impact import merge_win_impact_into_raw
from gravity_ml.train.train_champion import train_from_rows

logger = logging.getLogger(__name__)


async def fetch_cfb_training_rows(limit: int | None = None) -> list[dict]:
    conn = await asyncpg.connect(get_settings().pg_dsn, statement_cache_size=0, timeout=90, command_timeout=600)
    rows_out: list[dict] = []
    try:
        await conn.execute("SET statement_timeout = 0")
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
            WHERE a.sport = 'cfb' AND COALESCE(a.is_active, TRUE) = TRUE
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
                raw = {}
            snap = row["snapshot_features"]
            if isinstance(snap, str):
                snap = json.loads(snap)
            enriched = merge_win_impact_into_raw(raw, sport="cfb")
            flat_snap = flatten_snapshot_features(snap if isinstance(snap, dict) else None)
            merged = {**flat_snap, **flatten_raw_data(enriched), **enriched}
            target = merged.get("target_impact_score") or merged.get("win_impact_score")
            if target is None:
                continue
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
                raw_data=enriched,
                snapshot_features=snap if isinstance(snap, dict) else None,
            )
            training_row.update({k: v for k, v in merged.items() if k not in training_row})
            training_row["target_impact_score"] = float(target)
            training_row["target"] = float(target)
            rows_out.append(training_row)
    finally:
        await conn.close()
    return rows_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Train CFB impact_v1 bundle")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--min-spearman", type=float, default=0.50)
    parser.add_argument("--no-promote", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    rows = asyncio.run(fetch_cfb_training_rows(limit=args.limit))
    if len(rows) < 30:
        raise SystemExit(f"Need >=30 labeled rows, got {len(rows)}")
    logger.info("Training impact_v1 on %d CFB rows", len(rows))

    out_dir = train_from_rows(
        rows,
        entity_type="athlete",
        sport="cfb",
        objective="impact",
        version=args.version,
        out_root=ROOT / "models" / "bundles",
    )
    if not out_dir:
        raise SystemExit("Training failed — insufficient rows after split")
    logger.info("Bundle written: %s", out_dir)

    metrics_path = Path(out_dir) / "metrics.json"
    gate_sp = 0.0
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        # train_from_rows emits validation metrics; prefer test when present.
        gate_sp = float(
            (metrics.get("test") or {}).get("spearman")
            or (metrics.get("validation") or {}).get("spearman")
            or (metrics.get("validation") or {}).get("pearson")
            or 0.0
        )
        logger.info("holdout Spearman/Pearson=%.4f (gate=%.2f)", gate_sp, args.min_spearman)

    if args.no_promote:
        logger.info("--no-promote set; not updating champions")
        return
    if gate_sp < args.min_spearman:
        logger.warning("NOT promoted: holdout %.4f below gate %.2f", gate_sp, args.min_spearman)
        return

    index_path = ROOT / "models" / "bundles" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"champions": {}}
    index.setdefault("champions", {})["gravity_athlete_cfb_impact_v1"] = args.version
    from datetime import datetime, timezone

    index["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    logger.info("PROMOTED gravity_athlete_cfb_impact_v1 -> %s", args.version)


if __name__ == "__main__":
    main()
