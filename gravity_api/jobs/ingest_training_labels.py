"""Ingest NIL and contract labels into gravity_training_labels."""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timezone

import asyncpg

from gravity_api.config import get_settings

logger = logging.getLogger(__name__)


async def ingest_nil_labels(conn: asyncpg.Connection) -> int:
    rows = await conn.fetch(
        """
        SELECT athlete_id, deal_value, deal_date, verified, brand_name, source
        FROM athlete_nil_deals
        WHERE deal_value IS NOT NULL AND deal_value > 0 AND athlete_id IS NOT NULL
        """
    )
    count = 0
    for row in rows:
        start = row["deal_date"] or datetime.now(tz=timezone.utc).date()
        available = datetime.now(tz=timezone.utc)
        await conn.execute(
            """
            INSERT INTO gravity_training_labels (
              entity_type, entity_id, target_key, target_value,
              label_start_at, available_at, confidence, verified, metadata
            ) VALUES (
              'athlete', $1, 'nil_deal_value_usd', $2,
              $3::timestamptz, $4, $5, $6,
              jsonb_build_object('brand', $7, 'source', $8)
            )
            """,
            row["athlete_id"],
            float(row["deal_value"]),
            datetime.combine(start, datetime.min.time()).replace(tzinfo=timezone.utc),
            available,
            0.9 if row["verified"] else 0.65,
            bool(row["verified"]),
            row["brand_name"],
            row["source"],
        )
        count += 1
    return count


async def ingest_valuation_labels(conn: asyncpg.Connection) -> int:
    rows = await conn.fetch(
        """
        SELECT id AS athlete_id, nil_valuation, updated_at
        FROM athletes
        WHERE nil_valuation IS NOT NULL AND nil_valuation > 0
        """
    )
    count = 0
    for row in rows:
        await conn.execute(
            """
            INSERT INTO gravity_training_labels (
              entity_type, entity_id, target_key, target_value,
              label_start_at, available_at, confidence, verified, metadata
            ) VALUES (
              'athlete', $1, 'nil_valuation_usd', $2,
              $3, $3, 0.6, FALSE, '{"source":"athletes.nil_valuation"}'::jsonb
            )
            """,
            row["athlete_id"],
            float(row["nil_valuation"]),
            row["updated_at"] or datetime.now(tz=timezone.utc),
        )
        count += 1
    return count


async def main() -> None:
    conn = await asyncpg.connect(get_settings().pg_dsn, statement_cache_size=0)
    try:
        deals = await ingest_nil_labels(conn)
        vals = await ingest_valuation_labels(conn)
        logger.info("Ingested %d deal labels, %d valuation labels", deals, vals)
    finally:
        await conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
