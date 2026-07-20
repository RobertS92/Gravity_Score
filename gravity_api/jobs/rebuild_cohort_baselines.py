"""
Rebuild gravity_cohort_baselines from athlete_season_stats and athlete_metric_history.

Run:
  PYTHONPATH=. python3 -m gravity_api.jobs.rebuild_cohort_baselines
  PYTHONPATH=. python3 -m gravity_api.jobs.rebuild_cohort_baselines --sport cfb
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()

import asyncpg

from gravity_api.feature_engineering.composites import compute_performance_index
from gravity_api.feature_engineering.positions import SPORT_LEAGUE
from gravity_api.feature_engineering.sport_specs import ALL_SPORT_SPECS, get_position_spec
from gravity_api.feature_engineering.transforms import baseline_distribution
from gravity_api.services.sport_pipeline.config import ALL_SPORT_PIPELINES
from gravity_api.services.sport_pipeline.season_stats import _current_season_year

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def rebuild_for_cohort(
    conn: asyncpg.Connection,
    *,
    league: str,
    sport: str,
    position_group: str,
    season_year: int,
) -> int:
    written = 0
    try:
        pos_spec = get_position_spec(sport, position_group)
    except KeyError:
        return 0

    stat_keys = [sw.stat_key for sw in pos_spec.performance_stats]
    for stat_key in stat_keys:
        rows = await conn.fetch(
            """SELECT stat_value FROM athlete_season_stats
               WHERE sport = $1 AND position_group = $2 AND season_year = $3 AND stat_key = $4""",
            sport,
            position_group,
            season_year,
            stat_key,
        )
        values = [float(r["stat_value"]) for r in rows]
        if not values:
            continue
        dist = baseline_distribution(values)
        await conn.execute(
            """INSERT INTO gravity_cohort_baselines (
                 league, sport, position_group, season_year, window_key, metric_key,
                 cohort_level, n, mean_value, std_value, p50, p75, p80, p90, p95, p99
               ) VALUES ($1,$2,$3,$4,'season',$5,'primary',$6,$7,$8,$9,$10,$11,$12,$13,$14)
               ON CONFLICT (league, sport, position_group, season_year, window_key, metric_key, cohort_level)
               DO UPDATE SET n=EXCLUDED.n, mean_value=EXCLUDED.mean_value, std_value=EXCLUDED.std_value,
                 p50=EXCLUDED.p50, p75=EXCLUDED.p75, p80=EXCLUDED.p80, p90=EXCLUDED.p90,
                 p95=EXCLUDED.p95, p99=EXCLUDED.p99, updated_at=NOW()""",
            league,
            sport,
            position_group,
            season_year,
            f"proof.stat.{stat_key}",
            dist["n"],
            dist["mean"],
            dist["std"],
            dist["p50"],
            dist["p75"],
            dist["p80"],
            dist["p90"],
            dist["p95"],
            dist["p99"],
        )
        written += 1

    # Performance index baseline. Fetch the whole cohort's stats in ONE query
    # and group per athlete in Python — the previous per-athlete query loop was
    # an N+1 that made a full rebuild take many minutes to hours.
    cohort_rows = await conn.fetch(
        """SELECT athlete_id, stat_key, stat_value FROM athlete_season_stats
           WHERE sport = $1 AND position_group = $2 AND season_year = $3""",
        sport,
        position_group,
        season_year,
    )
    per_athlete: dict[Any, dict[str, float]] = {}
    per_stat_values: dict[str, list[float]] = {k: [] for k in stat_keys}
    for r in cohort_rows:
        key = str(r["stat_key"])
        val = float(r["stat_value"])
        per_athlete.setdefault(r["athlete_id"], {})[key] = val
        if key in per_stat_values:
            per_stat_values[key].append(val)

    means: dict[str, float] = {}
    stds: dict[str, float] = {}
    for stat_key, vals in per_stat_values.items():
        if vals:
            d = baseline_distribution(vals)
            if d["mean"] is not None:
                means[stat_key] = float(d["mean"])
            if d["std"] is not None:
                stds[stat_key] = max(float(d["std"]), 1e-6)

    indices: list[float] = []
    for season_stats in per_athlete.values():
        idx = compute_performance_index(
            sport=sport,
            position_group=position_group,
            season_stats=season_stats,
            cohort_means=means,
            cohort_stds=stds,
        )
        if idx is not None:
            indices.append(idx)

    if indices:
        dist = baseline_distribution(indices)
        await conn.execute(
            """INSERT INTO gravity_cohort_baselines (
                 league, sport, position_group, season_year, window_key, metric_key,
                 cohort_level, n, mean_value, std_value, p50, p75, p80, p90, p95, p99
               ) VALUES ($1,$2,$3,$4,'season','proof.performance_index','primary',$5,$6,$7,$8,$9,$10,$11,$12,$13)
               ON CONFLICT (league, sport, position_group, season_year, window_key, metric_key, cohort_level)
               DO UPDATE SET n=EXCLUDED.n, mean_value=EXCLUDED.mean_value, std_value=EXCLUDED.std_value,
                 p50=EXCLUDED.p50, p75=EXCLUDED.p75, p80=EXCLUDED.p80, p90=EXCLUDED.p90,
                 p95=EXCLUDED.p95, p99=EXCLUDED.p99, updated_at=NOW()""",
            league,
            sport,
            position_group,
            season_year,
            dist["n"],
            dist["mean"],
            dist["std"],
            dist["p50"],
            dist["p75"],
            dist["p80"],
            dist["p90"],
            dist["p95"],
            dist["p99"],
        )
        written += 1

    return written


async def run(*, sport_filter: str | None = None) -> None:
    dsn = os.environ["PG_DSN"]
    season_year = _current_season_year()
    conn = await asyncpg.connect(dsn)
    try:
        total = 0
        specs = ALL_SPORT_SPECS
        if sport_filter:
            specs = [s for s in specs if s.sport == sport_filter]
        for spec in specs:
            league = SPORT_LEAGUE.get(spec.sport, spec.league)
            for pg in spec.position_groups:
                n = await rebuild_for_cohort(
                    conn,
                    league=league,
                    sport=spec.sport,
                    position_group=pg.position_group,
                    season_year=season_year,
                )
                total += n
                logger.info("%s/%s season=%s baselines=%s", spec.sport, pg.position_group, season_year, n)
        logger.info("Total baseline rows upserted: %s", total)
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sport", default=None)
    args = parser.parse_args()
    asyncio.run(run(sport_filter=args.sport))


if __name__ == "__main__":
    main()
