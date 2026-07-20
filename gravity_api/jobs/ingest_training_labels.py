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
    """Ingest only governed, scope-specific transactions.

    Legacy ``athlete_nil_deals.verified`` booleans are deliberately not
    accepted: they lack enough provenance to support supervised pricing.
    """
    rows = await conn.fetch(
        """
        SELECT id, athlete_id, deal_scope::text AS deal_scope, amount_usd,
               deal_date, available_at, brand_name, source_url, source_domain,
               source_tier, verification_status, score_snapshot_id
        FROM verified_deal_transactions
        WHERE retracted_at IS NULL
          AND amount_usd > 0
          AND source_url ~ '^https?://[^[:space:]]+$'
          AND verification_status IN ('two_source_verified', 'primary_document_verified')
        """
    )
    count = 0
    for row in rows:
        start = row["deal_date"]
        target_key = f"nil_deal_value_usd:{row['deal_scope']}"
        await conn.execute(
            """
            INSERT INTO gravity_training_labels (
              entity_type, entity_id, target_key, target_value,
              label_start_at, available_at, confidence, verified, metadata
            ) VALUES (
              'athlete', $1, $2, $3,
              $4::timestamptz, $5, 1.0, TRUE,
              jsonb_build_object(
                'transaction_id', $6::text,
                'deal_scope', $7::text,
                'brand', COALESCE($8::text, ''),
                'source_url', $9::text,
                'source_domain', $10::text,
                'source_tier', $11::text,
                'verification_status', $12::text,
                'score_snapshot_id', $13::text
              )
            )
            """,
            row["athlete_id"],
            target_key,
            float(row["amount_usd"]),
            datetime.combine(start, datetime.min.time()).replace(tzinfo=timezone.utc),
            row["available_at"],
            row["id"],
            row["deal_scope"],
            row["brand_name"],
            row["source_url"],
            row["source_domain"],
            row["source_tier"],
            row["verification_status"],
            row["score_snapshot_id"],
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
