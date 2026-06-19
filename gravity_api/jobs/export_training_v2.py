"""Export leakage-safe Gravity v2 training rows from Postgres."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import asyncpg

from gravity_api.config import get_settings


async def export_rows(entity_type: str, target_key: str) -> list[dict]:
    conn = await asyncpg.connect(get_settings().pg_dsn, statement_cache_size=0)
    try:
        rows = await conn.fetch(
            """SELECT
                 s.entity_id, s.as_of, s.features, s.missingness,
                 s.data_quality_score, l.target_value, l.target_class,
                 l.label_start_at, l.label_end_at, l.available_at,
                 l.confidence AS label_confidence, l.verified
               FROM gravity_feature_snapshots s
               JOIN gravity_training_labels l
                 ON l.entity_type = s.entity_type
                AND l.entity_id = s.entity_id
                AND l.target_key = $2
               WHERE s.entity_type = $1
                 -- The snapshot may only use information ingested by as_of.
                 -- The outcome must occur after the prediction point.
                 AND l.label_start_at >= s.as_of
                 AND l.available_at >= l.label_start_at
               ORDER BY s.as_of, s.entity_id""",
            entity_type,
            target_key,
        )
        output = []
        for row in rows:
            features = dict(row["features"] or {})
            features.update(
                {
                    "entity_id": str(row["entity_id"]),
                    "as_of": row["as_of"].isoformat(),
                    "data_quality_score": float(row["data_quality_score"] or 0),
                    "target_value": (
                        float(row["target_value"])
                        if row["target_value"] is not None
                        else None
                    ),
                    "target_class": row["target_class"],
                    "label_confidence": float(row["label_confidence"] or 0),
                    "label_verified": bool(row["verified"]),
                }
            )
            output.append(features)
        return output
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("entity_type", choices=["athlete", "team", "brand", "relationship"])
    parser.add_argument("target_key")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = asyncio.run(export_rows(args.entity_type, args.target_key))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=2, default=str))
    print(f"Wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
