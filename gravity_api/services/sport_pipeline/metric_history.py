"""Sync social and metric history for velocity / YoY features."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import asyncpg


def _social_reach(row: asyncpg.Record) -> float | None:
    parts = [
        row.get("instagram_followers"),
        row.get("tiktok_followers"),
        row.get("twitter_followers"),
        row.get("youtube_subscribers"),
    ]
    nums = [float(p) for p in parts if p is not None]
    if not nums:
        return None
    return sum(nums)


async def sync_metric_history_from_social(
    conn: asyncpg.Connection,
    athlete_id: str,
    *,
    limit: int = 12,
) -> int:
    """Copy social_snapshots into athlete_metric_history for reach + platform metrics."""
    rows = await conn.fetch(
        """SELECT * FROM social_snapshots
           WHERE athlete_id = $1::uuid
           ORDER BY scraped_at DESC
           LIMIT $2""",
        athlete_id,
        limit,
    )
    if not rows:
        return 0

    written = 0
    metrics = (
        ("brand.social_reach_total", _social_reach),
        ("brand.instagram_followers", lambda r: r.get("instagram_followers")),
        ("brand.tiktok_followers", lambda r: r.get("tiktok_followers")),
    )
    for row in rows:
        period_start = row["scraped_at"]
        for metric_key, extractor in metrics:
            val = extractor(row)
            if val is None:
                continue
            try:
                await conn.execute(
                    """INSERT INTO athlete_metric_history (
                         athlete_id, metric_key, period_start, window_key,
                         numeric_value, source_key, confidence, observed_at
                       ) VALUES ($1::uuid, $2, $3, '30d', $4, 'social_snapshots', 0.9, $3)
                       ON CONFLICT (athlete_id, metric_key, period_start, window_key)
                       DO UPDATE SET numeric_value = EXCLUDED.numeric_value""",
                    athlete_id,
                    metric_key,
                    period_start,
                    float(val),
                )
                written += 1
            except asyncpg.PostgresError:
                continue
    return written


async def load_metric_histories(
    conn: asyncpg.Connection,
    athlete_id: str,
    metric_keys: tuple[str, ...],
    *,
    limit: int = 8,
) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for key in metric_keys:
        rows = await conn.fetch(
            """SELECT numeric_value FROM athlete_metric_history
               WHERE athlete_id = $1::uuid AND metric_key = $2
               ORDER BY period_start ASC
               LIMIT $3""",
            athlete_id,
            key,
            limit,
        )
        if rows:
            out[key] = [float(r["numeric_value"]) for r in rows]
    return out
