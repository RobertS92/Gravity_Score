"""Materialize BPXVR feature snapshots into gravity_feature_snapshots."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import asyncpg

from gravity_api.feature_engineering.constants import FEATURE_SCHEMA_VERSION
from gravity_api.feature_engineering.engine import FeatureEngineeringEngine


async def materialize_bpxvr_snapshot(
    conn: asyncpg.Connection,
    *,
    entity_id: str,
    sport: str,
    position: str | None,
    season_year: int,
    raw: dict[str, Any],
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Build BPXVR snapshot and persist to gravity_feature_snapshots."""
    as_of = as_of or datetime.now(tz=timezone.utc)
    engine = FeatureEngineeringEngine()
    snapshot = engine.build_snapshot(
        entity_id=entity_id,
        sport=sport,
        position=position,
        season_year=season_year,
        raw=raw,
        as_of=as_of,
    )
    payload = snapshot.to_dict()
    row = await conn.fetchrow(
        """INSERT INTO gravity_feature_snapshots (
             entity_type, entity_id, as_of, feature_schema_version, features,
             missingness, provenance_summary, freshness_summary, data_quality_score
           ) VALUES ('athlete', $1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb, $7::jsonb, $8)
           ON CONFLICT (entity_type, entity_id, as_of, feature_schema_version)
           DO UPDATE SET
             features = EXCLUDED.features,
             missingness = EXCLUDED.missingness,
             data_quality_score = EXCLUDED.data_quality_score
           RETURNING *""",
        entity_id,
        as_of,
        FEATURE_SCHEMA_VERSION,
        json.dumps(payload, default=str),
        json.dumps(snapshot.missingness),
        json.dumps({"source": "feature_engineering_engine", "sport": sport}),
        json.dumps({}),
        _quality_from_missingness(snapshot.missingness),
    )
    return dict(row) if row else payload


def _quality_from_missingness(missingness: dict[str, bool]) -> float:
    if not missingness:
        return 0.0
    observed = sum(1 for v in missingness.values() if not v)
    return observed / len(missingness)
