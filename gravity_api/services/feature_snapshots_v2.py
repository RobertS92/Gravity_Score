"""Point-in-time feature snapshots built strictly from observations available by `as_of`."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import asyncpg


async def materialize_feature_snapshot(
    conn: asyncpg.Connection,
    *,
    entity_type: str,
    entity_id: str,
    feature_schema_version: str = "gravity_features_v2",
    as_of: datetime | None = None,
) -> dict[str, Any]:
    as_of = as_of or datetime.now(tz=timezone.utc)
    rows = await conn.fetch(
        """SELECT DISTINCT ON (o.feature_key)
             o.feature_key, o.numeric_value, o.text_value, o.json_value,
             o.observed_at, o.ingested_at, o.confidence, o.verification_status,
             o.freshness_seconds, s.source_key
           FROM gravity_observations o
           LEFT JOIN gravity_data_sources s ON s.id = o.source_id
           WHERE o.entity_type = $1 AND o.entity_id = $2
             AND o.observed_at <= $3
             AND o.ingested_at <= $3
             AND o.verification_status <> 'rejected'
           ORDER BY o.feature_key, o.observed_at DESC, o.ingested_at DESC""",
        entity_type,
        entity_id,
        as_of,
    )
    features: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    freshness: dict[str, Any] = {}
    weighted_quality = 0.0
    for row in rows:
        value = (
            row["numeric_value"]
            if row["numeric_value"] is not None
            else row["text_value"]
            if row["text_value"] is not None
            else row["json_value"]
        )
        key = str(row["feature_key"])
        features[key] = value
        provenance[key] = {
            "source": row["source_key"],
            "confidence": float(row["confidence"]),
            "verification": row["verification_status"],
            "observed_at": row["observed_at"].isoformat(),
        }
        freshness[key] = row["freshness_seconds"]
        weighted_quality += float(row["confidence"])

    quality = weighted_quality / len(rows) if rows else 0.0
    missingness = {"observed_feature_count": len(rows)}
    row = await conn.fetchrow(
        """INSERT INTO gravity_feature_snapshots (
             entity_type, entity_id, as_of, feature_schema_version, features,
             missingness, provenance_summary, freshness_summary, data_quality_score
           ) VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb, $8::jsonb, $9)
           ON CONFLICT (entity_type, entity_id, as_of, feature_schema_version)
           DO UPDATE SET
             features = EXCLUDED.features,
             missingness = EXCLUDED.missingness,
             provenance_summary = EXCLUDED.provenance_summary,
             freshness_summary = EXCLUDED.freshness_summary,
             data_quality_score = EXCLUDED.data_quality_score
           RETURNING *""",
        entity_type,
        entity_id,
        as_of,
        feature_schema_version,
        json.dumps(features, default=str),
        json.dumps(missingness),
        json.dumps(provenance),
        json.dumps(freshness),
        quality,
    )
    return dict(row)


__all__ = ["materialize_feature_snapshot"]
