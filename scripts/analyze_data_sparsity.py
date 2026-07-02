#!/usr/bin/env python3
"""Analyze stats/NIL sparsity: scraper gap vs natural sparsity."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg


async def main() -> None:
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise SystemExit("PG_DSN required")

    conn = await asyncpg.connect(dsn, command_timeout=120)

    print("=" * 70)
    print("CFB: STATS & NIL SPARSITY")
    print("=" * 70)
    row = await conn.fetchrow(
        """
        WITH r AS (
          SELECT a.id, COALESCE(r.raw_data, '{}'::jsonb) raw
          FROM athletes a
          LEFT JOIN LATERAL (
            SELECT raw_data FROM raw_athlete_data
            WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
          ) r ON TRUE
          WHERE a.sport = 'cfb' AND COALESCE(a.is_active, TRUE)
        )
        SELECT COUNT(*) active_n,
          COUNT(*) FILTER (
            WHERE COALESCE((raw->>'games_played_season')::float, 0) > 0
               OR COALESCE((raw->'season_stats'->>'gp')::float, 0) > 0
          ) has_gp,
          COUNT(*) FILTER (
            WHERE raw ? 'season_stats'
              AND jsonb_typeof(raw->'season_stats') = 'object'
              AND (SELECT COUNT(*) FROM jsonb_each(raw->'season_stats')) >= 3
          ) stats3,
          COUNT(*) FILTER (WHERE COALESCE(raw->>'nil_valuation_observed', '0') = '1') nil_observed,
          COUNT(*) FILTER (WHERE COALESCE((raw->>'nil_valuation')::float, 0) > 0) nil_any,
          COUNT(*) FILTER (WHERE COALESCE(raw->>'instagram_handle', '') <> '') ig_handle
        FROM r
        """
    )
    n = row["active_n"]
    for key in ("has_gp", "stats3", "nil_observed", "nil_any", "ig_handle"):
        print(f"  {key}: {row[key]} ({round(100 * row[key] / n, 1)}%)")
    print(f"  active_n: {n}")

    print("\nCFB by position (n>=50):")
    rows = await conn.fetch(
        """
        WITH r AS (
          SELECT UPPER(COALESCE(a.position, 'UNK')) pos, COALESCE(r.raw_data, '{}'::jsonb) raw
          FROM athletes a
          LEFT JOIN LATERAL (
            SELECT raw_data FROM raw_athlete_data
            WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
          ) r ON TRUE
          WHERE a.sport = 'cfb' AND COALESCE(a.is_active, TRUE)
        )
        SELECT pos, COUNT(*) n,
          ROUND(100.0 * COUNT(*) FILTER (
            WHERE raw ? 'season_stats'
              AND (SELECT COUNT(*) FROM jsonb_each(raw->'season_stats')) >= 3
          ) / NULLIF(COUNT(*), 0), 1) stats3_pct,
          ROUND(100.0 * COUNT(*) FILTER (
            WHERE COALESCE(raw->>'nil_valuation_observed', '0') = '1'
          ) / NULLIF(COUNT(*), 0), 1) nil_obs_pct
        FROM r GROUP BY 1 HAVING COUNT(*) >= 50 ORDER BY n DESC LIMIT 12
        """
    )
    for r in rows:
        print(
            f"  {r['pos']:6} n={r['n']:4} stats3={r['stats3_pct']:5}% nil_obs={r['nil_obs_pct']:5}%"
        )

    print("\nScrape coverage vs stats (CFB, has espn_id):")
    row = await conn.fetchrow(
        """
        WITH r AS (
          SELECT r.scraped_at, COALESCE(r.raw_data, '{}'::jsonb) raw
          FROM athletes a
          JOIN LATERAL (
            SELECT raw_data, scraped_at FROM raw_athlete_data
            WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
          ) r ON TRUE
          WHERE a.sport = 'cfb' AND COALESCE(a.is_active, TRUE) AND a.espn_id IS NOT NULL
        )
        SELECT COUNT(*) FILTER (WHERE scraped_at IS NOT NULL) scraped,
          COUNT(*) FILTER (
            WHERE scraped_at IS NOT NULL
              AND NOT (raw ? 'season_stats' AND (SELECT COUNT(*) FROM jsonb_each(raw->'season_stats')) >= 3)
              AND NOT COALESCE((raw->>'games_played_season')::float, 0) > 0
          ) scraped_no_stats
        FROM r
        """
    )
    pct = round(100 * row["scraped_no_stats"] / max(row["scraped"], 1), 1)
    print(f"  scraped={row['scraped']} scraped_no_stats={row['scraped_no_stats']} ({pct}%)")

    row = await conn.fetchrow(
        """
        SELECT
          COUNT(*) FILTER (WHERE NOT EXISTS (
            SELECT 1 FROM raw_athlete_data r WHERE r.athlete_id = a.id
          )) never_scraped,
          COUNT(*) FILTER (WHERE EXISTS (
            SELECT 1 FROM raw_athlete_data r WHERE r.athlete_id = a.id
          )) ever_scraped
        FROM athletes a WHERE a.sport = 'cfb' AND COALESCE(a.is_active, TRUE)
        """
    )
    print(f"  never_scraped={row['never_scraped']} ever_scraped={row['ever_scraped']}")

    print("\nNIL observed vs imputed (CFB):")
    row = await conn.fetchrow(
        """
        WITH r AS (
          SELECT COALESCE(r.raw_data, '{}'::jsonb) raw FROM athletes a
          LEFT JOIN LATERAL (
            SELECT raw_data FROM raw_athlete_data
            WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
          ) r ON TRUE
          WHERE a.sport = 'cfb' AND COALESCE(a.is_active, TRUE)
        )
        SELECT
          COUNT(*) FILTER (WHERE COALESCE(raw->>'nil_valuation_observed', '0') = '1') observed,
          COUNT(*) FILTER (
            WHERE COALESCE(raw->>'nil_valuation_observed', '0') = '0'
              AND COALESCE((raw->>'nil_valuation')::float, 0) > 0
          ) imputed_only,
          COUNT(*) FILTER (WHERE COALESCE((raw->>'nil_valuation')::float, 0) = 2500) placeholder_2500
        FROM r
        """
    )
    print(dict(row))

    print("\nNIL source (CFB):")
    rows = await conn.fetch(
        """
        WITH r AS (
          SELECT COALESCE(r.raw_data, '{}'::jsonb) raw FROM athletes a
          LEFT JOIN LATERAL (
            SELECT raw_data FROM raw_athlete_data
            WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
          ) r ON TRUE
          WHERE a.sport = 'cfb' AND COALESCE(a.is_active, TRUE)
        )
        SELECT COALESCE(NULLIF(raw->>'nil_valuation_source', ''), '(none)') src,
          COUNT(*) n,
          COUNT(*) FILTER (WHERE COALESCE(raw->>'nil_valuation_observed', '0') = '1') obs
        FROM r GROUP BY 1 ORDER BY n DESC LIMIT 10
        """
    )
    for r in rows:
        print(f"  {str(r['src'])[:28]:28} n={r['n']:5} observed={r['obs']}")

    print("\nathlete_season_stats (CFB):")
    row = await conn.fetchrow(
        """
        SELECT
          (SELECT COUNT(DISTINCT athlete_id) FROM athlete_season_stats WHERE sport = 'cfb') athletes,
          (SELECT COUNT(DISTINCT athlete_id) FROM athlete_season_stats
             WHERE sport = 'cfb' AND stat_key IN ('gp','games_played','games_played_season') AND stat_value > 0) with_gp
        """
    )
    print(dict(row))

    ass3 = await conn.fetchval(
        """
        SELECT COUNT(*) FROM (
          SELECT athlete_id FROM athlete_season_stats
          WHERE sport = 'cfb'
          GROUP BY athlete_id
          HAVING COUNT(*) FILTER (WHERE stat_value > 0) >= 3
        ) t
        """
    )
    print(f"  ass_stats3_plus athletes: {ass3}")

    row = await conn.fetchrow(
        """
        WITH latest AS (
          SELECT a.id, COALESCE(r.raw_data, '{}'::jsonb) raw
          FROM athletes a
          LEFT JOIN LATERAL (
            SELECT raw_data FROM raw_athlete_data
            WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
          ) r ON TRUE
          WHERE a.sport = 'cfb' AND COALESCE(a.is_active, TRUE)
        ), ass AS (
          SELECT athlete_id, COUNT(*) FILTER (WHERE stat_value > 0) AS pos_stats
          FROM athlete_season_stats WHERE sport = 'cfb' GROUP BY athlete_id
        )
        SELECT
          COUNT(*) FILTER (WHERE ass.pos_stats >= 3) ass_has_3,
          COUNT(*) FILTER (
            WHERE ass.pos_stats >= 3
              AND NOT (l.raw ? 'season_stats'
                AND (SELECT COUNT(*) FROM jsonb_each(l.raw->'season_stats')) >= 3)
          ) ass3_not_in_raw
        FROM latest l
        LEFT JOIN ass ON ass.athlete_id = l.id
        """
    )
    print(f"  ass>=3: {row['ass_has_3']}, ass>=3 but raw<3: {row['ass3_not_in_raw']}")

    labels = await conn.fetchrow(
        """
        SELECT COUNT(*) total, COUNT(*) FILTER (WHERE target_value > 0) positive
        FROM gravity_training_labels l
        JOIN athletes a ON a.id = l.entity_id::uuid
        WHERE a.sport = 'cfb' AND l.entity_type = 'athlete'
          AND l.target_key = 'nil_valuation_usd'
        """
    )
    print(f"  training labels nil positive: {labels['positive']}/{labels['total']}")

    row = await conn.fetchrow(
        """
        WITH r AS (
          SELECT COALESCE(r.raw_data, '{}'::jsonb) raw FROM athletes a
          JOIN LATERAL (
            SELECT raw_data FROM raw_athlete_data
            WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
          ) r ON TRUE
          WHERE a.sport = 'cfb'
        )
        SELECT
          COUNT(*) FILTER (WHERE raw ? 'season_stats') has_key,
          COUNT(*) FILTER (
            WHERE raw ? 'season_stats'
              AND jsonb_typeof(raw->'season_stats') = 'object'
              AND (SELECT COUNT(*) FROM jsonb_each(raw->'season_stats')) = 0
          ) empty_obj,
          COUNT(*) FILTER (WHERE raw->>'stats_source' ILIKE '%sports_reference%') sr_source
        FROM r
        """
    )
    print(f"  season_stats patterns: {dict(row)}")

    print("\nSkill vs line positions (stats3):")
    rows = await conn.fetch(
        """
        WITH r AS (
          SELECT UPPER(COALESCE(a.position, 'UNK')) pos, COALESCE(r.raw_data, '{}'::jsonb) raw
          FROM athletes a
          LEFT JOIN LATERAL (
            SELECT raw_data FROM raw_athlete_data
            WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
          ) r ON TRUE
          WHERE a.sport = 'cfb' AND COALESCE(a.is_active, TRUE)
        )
        SELECT pos, COUNT(*) n,
          COUNT(*) FILTER (
            WHERE raw ? 'season_stats'
              AND (SELECT COUNT(*) FROM jsonb_each(raw->'season_stats')) >= 3
          ) s3
        FROM r
        WHERE pos IN ('QB', 'WR', 'RB', 'TE', 'OL', 'DL', 'LB', 'DB')
        GROUP BY 1 ORDER BY n DESC
        """
    )
    for r in rows:
        print(f"  {r['pos']:3} {r['s3']:4}/{r['n']:4} = {round(100*r['s3']/r['n'],1)}%")

    print("\nCROSS-SPORT:")
    for sport in ("cfb", "ncaab_mens", "ncaab_womens", "nfl", "nba", "wnba"):
        row = await conn.fetchrow(
            """
            WITH r AS (
              SELECT COALESCE(r.raw_data, '{}'::jsonb) raw FROM athletes a
              LEFT JOIN LATERAL (
                SELECT raw_data FROM raw_athlete_data
                WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
              ) r ON TRUE
              WHERE a.sport = $1 AND COALESCE(a.is_active, TRUE)
            )
            SELECT COUNT(*) n,
              ROUND(100.0 * COUNT(*) FILTER (
                WHERE raw ? 'season_stats'
                  AND (SELECT COUNT(*) FROM jsonb_each(raw->'season_stats')) >= 3
              ) / NULLIF(COUNT(*), 0), 1) stats3,
              ROUND(100.0 * COUNT(*) FILTER (
                WHERE COALESCE(raw->>'nil_valuation_observed', '0') = '1'
              ) / NULLIF(COUNT(*), 0), 1) nil_obs
            FROM r
            """,
            sport,
        )
        print(f"  {sport:14} n={row['n']:5} stats3={row['stats3']:5}% nil_obs={row['nil_obs']:5}%")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
