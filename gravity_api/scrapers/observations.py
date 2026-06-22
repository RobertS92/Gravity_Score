"""Write scraper fields to gravity_observations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import asyncpg

from gravity_api.scrapers.types import ScraperResult


async def _source_id(conn: asyncpg.Connection, source_key: str) -> str | None:
    row = await conn.fetchrow(
        "SELECT id FROM gravity_data_sources WHERE source_key = $1 AND active = TRUE",
        source_key,
    )
    return str(row["id"]) if row else None


async def persist_observations(
    conn: asyncpg.Connection,
    *,
    athlete_id: str,
    result: ScraperResult,
    collection_run_id: str | None = None,
) -> int:
    source_id = await _source_id(conn, result.source_key)
    if not source_id:
        source_id = await _source_id(conn, "espn")
    if not source_id:
        return 0

    observed_at = datetime.now(tz=timezone.utc)
    written = 0
    for key, value in result.fields.items():
        if value is None or value == "":
            continue
        numeric = text = json_val = None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            numeric = float(value)
        elif isinstance(value, (dict, list)):
            json_val = value
        else:
            text = str(value)

        await conn.execute(
            """INSERT INTO gravity_observations (
                 entity_type, entity_id, feature_key, numeric_value, text_value,
                 json_value, observed_at, source_id, source_record_id, confidence,
                 verification_status, collection_run_id, metadata
               ) VALUES (
                 'athlete', $1::uuid, $2, $3, $4, $5::jsonb, $6, $7::uuid, $8, $9,
                 'single_source', $10, $11::jsonb
               )""",
            athlete_id,
            key,
            numeric,
            text,
            json.dumps(json_val) if json_val is not None else None,
            observed_at,
            source_id,
            result.scraper_key,
            result.confidence,
            collection_run_id,
            json.dumps({"scraper_key": result.scraper_key}),
        )
        written += 1
    return written


async def merge_raw_athlete_data(
    conn: asyncpg.Connection,
    *,
    athlete_id: str,
    fields: dict[str, Any],
) -> None:
    if not fields:
        return
    row = await conn.fetchrow(
        """SELECT raw_data FROM raw_athlete_data
           WHERE athlete_id = $1::uuid
           ORDER BY scraped_at DESC NULLS LAST LIMIT 1""",
        athlete_id,
    )
    merged: dict[str, Any] = dict(row["raw_data"]) if row and row["raw_data"] else {}
    if isinstance(merged, str):
        merged = json.loads(merged)
    merged.update(fields)
    merged["collection_timestamp"] = datetime.now(tz=timezone.utc).isoformat()
    await conn.execute(
        """INSERT INTO raw_athlete_data (athlete_id, raw_data, scraped_at, source)
           VALUES ($1::uuid, $2::jsonb, NOW(), 'gravity_api_scrapers')""",
        athlete_id,
        json.dumps(merged, default=str),
    )
