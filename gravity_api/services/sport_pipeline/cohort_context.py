"""Load cohort baselines and peer distributions for feature engineering."""

from __future__ import annotations

from typing import Any

import asyncpg

from gravity_api.feature_engineering.composites import compute_performance_index
from gravity_api.feature_engineering.positions import SPORT_LEAGUE, derive_position_group
from gravity_api.feature_engineering.sport_specs import get_position_spec
from gravity_api.feature_engineering.transforms import baseline_distribution
from gravity_api.feature_engineering.types import CohortBaseline
from gravity_api.services.sport_pipeline.season_stats import _current_season_year


async def load_cohort_baselines_map(
    conn: asyncpg.Connection,
    *,
    league: str,
    sport: str,
    position_group: str,
    season_year: int,
) -> dict[str, CohortBaseline]:
    rows = await conn.fetch(
        """SELECT * FROM gravity_cohort_baselines
           WHERE league = $1 AND sport = $2 AND position_group = $3
             AND (season_year = $4 OR season_year IS NULL)
           ORDER BY metric_key, cohort_level""",
        league,
        sport,
        position_group,
        season_year,
    )
    out: dict[str, CohortBaseline] = {}
    for row in rows:
        key = f"{row['metric_key']}:{row['cohort_level']}"
        out[key] = CohortBaseline(
            league=row["league"],
            sport=row["sport"],
            position_group=row["position_group"],
            season_year=row["season_year"],
            window_key=row["window_key"],
            metric_key=row["metric_key"],
            cohort_level=row["cohort_level"],
            n=int(row["n"] or 0),
            mean=float(row["mean_value"]) if row["mean_value"] is not None else None,
            std=float(row["std_value"]) if row["std_value"] is not None else None,
            p50=float(row["p50"]) if row["p50"] is not None else None,
            p75=float(row["p75"]) if row["p75"] is not None else None,
            p80=float(row["p80"]) if row["p80"] is not None else None,
            p90=float(row["p90"]) if row["p90"] is not None else None,
            p95=float(row["p95"]) if row["p95"] is not None else None,
            p99=float(row["p99"]) if row["p99"] is not None else None,
        )
    return out


async def load_cohort_stat_distributions(
    conn: asyncpg.Connection,
    *,
    sport: str,
    position_group: str,
    season_year: int,
    stat_keys: tuple[str, ...],
) -> tuple[dict[str, float], dict[str, float], dict[str, list[float]]]:
    """Peer stat means/stds and raw value lists from athlete_season_stats."""
    means: dict[str, float] = {}
    stds: dict[str, float] = {}
    value_lists: dict[str, list[float]] = {}
    if not stat_keys:
        return means, stds, value_lists

    rows = await conn.fetch(
        """SELECT stat_key, stat_value FROM athlete_season_stats
           WHERE sport = $1 AND position_group = $2 AND season_year = $3
             AND stat_key = ANY($4::text[])""",
        sport,
        position_group,
        season_year,
        list(stat_keys),
    )
    for r in rows:
        key = str(r["stat_key"])
        value_lists.setdefault(key, []).append(float(r["stat_value"]))
    for stat_key, values in value_lists.items():
        if not values:
            continue
        dist = baseline_distribution(values)
        if dist["mean"] is not None:
            means[stat_key] = float(dist["mean"])
        if dist["std"] is not None:
            stds[stat_key] = float(dist["std"]) if float(dist["std"]) > 0 else 1.0

    return means, stds, value_lists


async def load_cohort_performance_indices(
    conn: asyncpg.Connection,
    *,
    sport: str,
    position_group: str,
    season_year: int,
) -> list[float]:
    """Compute performance_index for all peers with stats in cohort."""
    try:
        pos_spec = get_position_spec(sport, position_group)
    except KeyError:
        return []

    stat_keys = tuple(sw.stat_key for sw in pos_spec.performance_stats)
    means, stds, _ = await load_cohort_stat_distributions(
        conn, sport=sport, position_group=position_group, season_year=season_year, stat_keys=stat_keys
    )
    if not means:
        return []

    rows = await conn.fetch(
        """SELECT athlete_id, stat_key, stat_value FROM athlete_season_stats
           WHERE sport = $1 AND position_group = $2 AND season_year = $3
             AND stat_key = ANY($4::text[])""",
        sport,
        position_group,
        season_year,
        list(stat_keys),
    )
    by_athlete: dict[Any, dict[str, float]] = {}
    for row in rows:
        bucket = by_athlete.setdefault(row["athlete_id"], {})
        bucket[str(row["stat_key"])] = float(row["stat_value"])

    indices: list[float] = []
    for season_stats in by_athlete.values():
        idx = compute_performance_index(
            sport=sport,
            position_group=position_group,
            season_stats=season_stats,
            cohort_means=means,
            cohort_stds=stds,
        )
        if idx is not None:
            indices.append(idx)
    return indices


async def build_cohort_context(
    conn: asyncpg.Connection,
    *,
    sport: str,
    position: str | None,
    season_year: int | None = None,
) -> dict[str, Any]:
    season_year = season_year or _current_season_year()
    position_group = derive_position_group(position, sport) or "UNKNOWN"
    league = SPORT_LEAGUE.get(sport, "ncaa")

    stat_keys: tuple[str, ...] = ()
    try:
        stat_keys = tuple(sw.stat_key for sw in get_position_spec(sport, position_group).performance_stats)
    except KeyError:
        pass

    means, stds, _ = await load_cohort_stat_distributions(
        conn, sport=sport, position_group=position_group, season_year=season_year, stat_keys=stat_keys
    )
    perf_indices = await load_cohort_performance_indices(
        conn, sport=sport, position_group=position_group, season_year=season_year
    )
    baselines = await load_cohort_baselines_map(
        conn, league=league, sport=sport, position_group=position_group, season_year=season_year
    )

    return {
        "season_year": season_year,
        "position_group": position_group,
        "league": league,
        "cohort_stat_means": means,
        "cohort_stat_stds": stds,
        "cohort_performance_index_values": perf_indices,
        "baselines": baselines,
    }
