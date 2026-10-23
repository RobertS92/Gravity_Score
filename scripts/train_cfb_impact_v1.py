#!/usr/bin/env python3
"""Legacy CFB impact_v1 trainer — formula-label path gated (M4/M5).

Production Impact training: ``python -m gravity_ml.impact.train_impact --league cfb``.
This script refuses to train/promote on ``compute_win_impact_score_v0`` /
``target_impact_score`` unless ``--allow-formula-labels`` is set (research only;
never writes champions).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logger = logging.getLogger(__name__)

FORMULA_LABEL_SOURCES = frozenset(
    {
        "compute_win_impact_score_v0",
        "compute_target_impact_score",
        "target_impact_score",
        "win_impact_score",
        "win_impact_score_v0",
    }
)


async def fetch_cfb_training_rows(limit: int | None = None) -> list[dict]:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    import asyncpg

    from gravity_api.config import get_settings
    from gravity_api.services.training_export import (
        build_training_row,
        flatten_raw_data,
        flatten_snapshot_features,
    )
    from gravity_api.services.win_impact import merge_win_impact_into_raw

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
            # Formula label path (banned for promotion).
            target = merged.get("win_impact_score_v0") or merged.get("win_impact_score")
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
            # Do not set target_impact_score as a feature; keep label lineage explicit.
            training_row["target"] = float(target)
            training_row["label_source"] = "compute_win_impact_score_v0"
            rows_out.append(training_row)
    finally:
        await conn.close()
    return rows_out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Legacy CFB impact_v1 (formula labels). Prefer gravity_ml.impact.train_impact."
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument(
        "--allow-formula-labels",
        action="store_true",
        help="Research-only: train on compute_win_impact_score_v0 (never promotes)",
    )
    parser.add_argument(
        "--min-spearman",
        type=float,
        default=None,
        help=argparse.SUPPRESS,  # removed M5 formula gate; kept hidden to catch old CI flags
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if args.min_spearman is not None:
        logger.error(
            "M5: --min-spearman against formula labels is removed. "
            "Use gravity_ml.impact.train_impact + G-I1..G-I5 outcome gates."
        )
        raise SystemExit(2)

    if not args.allow_formula_labels:
        logger.error(
            "Refusing formula-label CFB impact train (M4/M5). "
            "Run: python -m gravity_ml.impact.train_impact --league cfb "
            "(needs WP10 games/box; use --fixture for skeleton). "
            "Pass --allow-formula-labels only for offline research (cannot promote)."
        )
        raise SystemExit(2)

    from gravity_ml.train.promotion_gate import PromotionRefused, assert_label_source_allowed
    from gravity_ml.train.train_champion import train_from_rows

    logger.warning(
        "FORMULA LABEL PATH ENABLED — training on compute_win_impact_score_v0; "
        "promotion is hard-disabled"
    )
    try:
        assert_label_source_allowed("compute_win_impact_score_v0")
    except PromotionRefused:
        pass  # expected; we still allow research train without promote
    else:
        raise SystemExit("invariant broken: formula label source was allowed")

    rows = asyncio.run(fetch_cfb_training_rows(limit=args.limit))
    if len(rows) < 30:
        raise SystemExit(f"Need >=30 labeled rows, got {len(rows)}")
    logger.info("Research-only impact train on %d CFB rows (no promote)", len(rows))

    out_dir = train_from_rows(
        rows,
        entity_type="athlete",
        sport="cfb",
        objective="impact",
        version=args.version,
        out_root=ROOT / "models" / "bundles",
        label_source="compute_win_impact_score_v0",
        allow_promote=False,
    )
    if not out_dir:
        raise SystemExit("Training failed — insufficient rows after split")
    logger.info("Bundle written (not promoted): %s", out_dir)
    # Ensure champions index is NOT updated for this model key.
    index_path = ROOT / "models" / "bundles" / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        champs = index.get("champions") or {}
        if champs.get("gravity_athlete_cfb_impact_v1") == args.version:
            logger.error(
                "Refusing to leave formula bundle as champion; clear index entry manually if needed"
            )


if __name__ == "__main__":
    main()
