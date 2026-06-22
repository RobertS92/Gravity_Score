"""Persist and rebuild cohort baselines from athlete metric populations."""

from __future__ import annotations

from typing import Any, Sequence

import asyncpg

from gravity_api.feature_engineering.cohort import build_cohort_baseline
from gravity_api.feature_engineering.transforms import baseline_distribution


async def upsert_cohort_baseline(
    conn: asyncpg.Connection,
    baseline,
) -> None:
    await conn.execute(
        """INSERT INTO gravity_cohort_baselines (
             league, sport, position_group, season_year, window_key, metric_key,
             cohort_level, n, mean_value, std_value, p50, p75, p80, p90, p95, p99,
             min_value, max_value, updated_at
           ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,NOW())
           ON CONFLICT (league, sport, position_group, season_year, window_key, metric_key, cohort_level)
           DO UPDATE SET
             n = EXCLUDED.n,
             mean_value = EXCLUDED.mean_value,
             std_value = EXCLUDED.std_value,
             p50 = EXCLUDED.p50, p75 = EXCLUDED.p75, p80 = EXCLUDED.p80,
             p90 = EXCLUDED.p90, p95 = EXCLUDED.p95, p99 = EXCLUDED.p99,
             min_value = EXCLUDED.min_value, max_value = EXCLUDED.max_value,
             updated_at = NOW()""",
        baseline.league,
        baseline.sport,
        baseline.position_group,
        baseline.season_year,
        baseline.window_key,
        baseline.metric_key,
        baseline.cohort_level,
        baseline.n,
        baseline.mean,
        baseline.std,
        baseline.p50,
        baseline.p75,
        baseline.p80,
        baseline.p90,
        baseline.p95,
        baseline.p99,
        None,
        None,
    )


async def rebuild_baselines_for_metric(
    conn: asyncpg.Connection,
    *,
    league: str,
    sport: str,
    position_group: str,
    season_year: int | None,
    metric_key: str,
    values: Sequence[float],
    window_key: str = "season",
    cohort_level: str = "primary",
) -> dict[str, Any]:
    baseline = build_cohort_baseline(
        league=league,
        sport=sport,
        position_group=position_group,
        season_year=season_year,
        window_key=window_key,
        metric_key=metric_key,
        values=values,
        cohort_level=cohort_level,
    )
    await upsert_cohort_baseline(conn, baseline)
    return baseline_distribution(values)


async def fetch_baselines_for_cohort(
    conn: asyncpg.Connection,
    *,
    league: str,
    sport: str,
    position_group: str,
    season_year: int | None,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """SELECT * FROM gravity_cohort_baselines
           WHERE league = $1 AND sport = $2 AND position_group = $3
             AND (season_year = $4 OR ($4 IS NULL AND season_year IS NULL))
           ORDER BY metric_key, cohort_level""",
        league,
        sport,
        position_group,
        season_year,
    )
    return [dict(r) for r in rows]
