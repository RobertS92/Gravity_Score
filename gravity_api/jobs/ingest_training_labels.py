"""Ingest NIL, quality, and contract labels into gravity_training_labels."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone

import asyncpg
from dotenv import load_dotenv

load_dotenv()

from gravity_api.config import get_settings
from gravity_api.scrapers.parsers.quality_label import compute_external_quality_score

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
              jsonb_build_object('brand', COALESCE($7::text, ''), 'source', COALESCE($8::text, ''))
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
        SELECT a.id AS athlete_id,
               (r.raw_data->>'nil_valuation')::double precision AS nil_valuation,
               r.scraped_at AS updated_at
        FROM athletes a
        JOIN LATERAL (
          SELECT raw_data, scraped_at FROM raw_athlete_data
          WHERE athlete_id = a.id ORDER BY scraped_at DESC LIMIT 1
        ) r ON TRUE
        WHERE (r.raw_data->>'nil_valuation')::double precision > 0
          AND COALESCE((r.raw_data->>'nil_valuation_observed')::int, 0) = 1
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
              $3, $3, 0.6, FALSE, '{"source":"raw_athlete_data.nil_valuation"}'::jsonb
            )
            """,
            row["athlete_id"],
            float(row["nil_valuation"]),
            row["updated_at"] or datetime.now(tz=timezone.utc),
        )
        count += 1
    return count


async def ingest_external_quality_labels(conn: asyncpg.Connection) -> int:
    """Ingest awards-based external quality scores from latest raw scrape."""
    rows = await conn.fetch(
        """
        SELECT a.id AS athlete_id, r.raw_data, r.scraped_at
        FROM athletes a
        JOIN LATERAL (
          SELECT raw_data, scraped_at FROM raw_athlete_data
          WHERE athlete_id = a.id ORDER BY scraped_at DESC LIMIT 1
        ) r ON TRUE
        WHERE r.raw_data IS NOT NULL
        """
    )
    count = 0
    for row in rows:
        raw = row["raw_data"]
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, dict):
            continue
        if raw.get("external_quality_score_observed") not in (1, 1.0, "1", True):
            score, components = compute_external_quality_score(raw)
            if score <= 42.0 and not components:
                continue
        else:
            score = float(raw.get("external_quality_score") or 0)
            components = raw.get("external_quality_components") or {}
            if score <= 0:
                continue
        scraped_at = row["scraped_at"] or datetime.now(tz=timezone.utc)
        await conn.execute(
            """
            INSERT INTO gravity_training_labels (
              entity_type, entity_id, target_key, target_value,
              label_start_at, available_at, confidence, verified, metadata
            ) VALUES (
              'athlete', $1, 'external_quality_score', $2,
              $3, $3, 0.72, TRUE,
              jsonb_build_object('source', 'awards_honors', 'components', $4::jsonb)
            )
            """,
            row["athlete_id"],
            score,
            scraped_at,
            json.dumps(components),
        )
        count += 1
    return count


async def ingest_impact_labels(conn: asyncpg.Connection) -> int:
    """Persist win_impact_score_v0 as training label for impact_v1 models."""
    rows = await conn.fetch(
        """
        SELECT a.id AS athlete_id,
               (r.raw_data->>'win_impact_score')::double precision AS win_impact_score,
               r.scraped_at AS updated_at
        FROM athletes a
        JOIN LATERAL (
          SELECT raw_data, scraped_at FROM raw_athlete_data
          WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
        ) r ON TRUE
        WHERE a.sport = 'cfb'
          AND (r.raw_data->>'win_impact_score')::double precision > 0
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
              'athlete', $1, 'target_impact_score', $2,
              $3, $3, 0.68, FALSE,
              jsonb_build_object('source', 'win_impact_v0')
            )
            """,
            row["athlete_id"],
            float(row["win_impact_score"]),
            row["updated_at"] or datetime.now(tz=timezone.utc),
        )
        count += 1
    return count


async def main_async(*, include_quality: bool = True) -> None:
    conn = await asyncpg.connect(get_settings().pg_dsn, statement_cache_size=0)
    try:
        deals = await ingest_nil_labels(conn)
        vals = await ingest_valuation_labels(conn)
        quality = await ingest_external_quality_labels(conn) if include_quality else 0
        impact = await ingest_impact_labels(conn)
        logger.info(
            "Ingested %d deal labels, %d valuation labels, %d quality labels, %d impact labels",
            deals,
            vals,
            quality,
            impact,
        )
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest training labels")
    parser.add_argument("--skip-quality", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main_async(include_quality=not args.skip_quality))


if __name__ == "__main__":
    main()
