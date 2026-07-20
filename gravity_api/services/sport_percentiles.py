"""Persist tie-safe within-sport ranks for globally comparable scores."""

from __future__ import annotations

from collections.abc import Iterable

import asyncpg


async def refresh_sport_percentiles(
    conn: asyncpg.Connection,
    athlete_ids: Iterable[str] | None = None,
) -> None:
    """Refresh percentiles from each sport's full active scored cohort.

    Ties receive a midrank. Values are clipped to 1..99 so they remain display
    percentiles rather than implying certainty at 0 or 100.
    """
    ids = [str(value) for value in athlete_ids or []]
    await conn.execute(
        """
        WITH active_scores AS (
          SELECT s.athlete_id, a.sport, s.gravity_score, s.value_score
          FROM athlete_gravity_scores s
          JOIN athletes a ON a.id = s.athlete_id
          WHERE a.is_active IS TRUE
        ),
        ranked AS (
          SELECT athlete_id,
            CASE WHEN gravity_score IS NULL THEN NULL ELSE LEAST(99, GREATEST(1,
              100.0 * (
                RANK() OVER (PARTITION BY sport ORDER BY gravity_score NULLS LAST)
                + (COUNT(*) OVER (PARTITION BY sport, gravity_score) - 1) / 2.0
              ) / NULLIF(COUNT(gravity_score) OVER (PARTITION BY sport), 0)
            )) END AS gravity_pct,
            CASE WHEN value_score IS NULL THEN NULL ELSE LEAST(99, GREATEST(1,
              100.0 * (
                RANK() OVER (PARTITION BY sport ORDER BY value_score NULLS LAST)
                + (COUNT(*) OVER (PARTITION BY sport, value_score) - 1) / 2.0
              ) / NULLIF(COUNT(value_score) OVER (PARTITION BY sport), 0)
            )) END AS value_pct
          FROM active_scores
        )
        UPDATE athlete_gravity_scores s
        SET gravity_sport_percentile = r.gravity_pct,
            value_sport_percentile = r.value_pct
        FROM ranked r
        WHERE s.athlete_id = r.athlete_id
          AND (cardinality($1::uuid[]) = 0 OR s.athlete_id = ANY($1::uuid[]))
        """,
        ids,
    )


__all__ = ["refresh_sport_percentiles"]
