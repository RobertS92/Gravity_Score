"""Persist position-relevant stats from scraper raw fields."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import asyncpg

from gravity_api.feature_engineering.positions import derive_position_group
from gravity_api.feature_engineering.sport_specs import get_position_spec, get_sport_spec
from gravity_api.scrapers.parsers.stat_catalog import all_stat_keys_for_sport
from gravity_api.scrapers.parsers.stat_normalizer import flatten_raw_for_stats
from gravity_api.services.sport_pipeline.config import get_sport_pipeline_config

_SPLIT_SEASON_RE = re.compile(r"(20\d{2})\s*[-/]\s*(\d{4}|\d{2})")


async def upsert_season_stats_from_raw(
    conn: asyncpg.Connection,
    *,
    athlete_id: str,
    sport: str,
    position: str | None,
    raw: dict[str, Any],
    season_year: int | None = None,
) -> int:
    """Write numeric stat fields into athlete_season_stats under their true years.

    Never relabel a prior season as ``current_year``. Scoring callers that need an
    offseason fallback must *read* the latest completed year via
    ``resolve_scoring_season_year`` — not by copying those rows into the current key.
    """
    try:
        get_sport_spec(sport)
    except KeyError:
        return 0

    position_group = derive_position_group(position, sport)
    if not position_group:
        return 0

    try:
        get_position_spec(sport, position_group)
    except KeyError:
        return 0

    league = get_sport_pipeline_config(sport).league
    written = 0
    store_keys = all_stat_keys_for_sport(sport)

    async def _write_season(
        stats: dict[str, float],
        year: int,
        *,
        source_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        count = 0
        games = int(stats.get("games_played_season") or stats.get("gp") or 0) or None
        meta = {
            "source_season_year": year,
            **(metadata or {}),
        }
        for key in store_keys:
            if key not in stats:
                continue
            val = stats[key]
            try:
                await conn.execute(
                    """INSERT INTO athlete_season_stats (
                         athlete_id, sport, league, season_year, position_group,
                         stat_key, stat_value, games_played, source_key, observed_at,
                         metadata
                       ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb)
                       ON CONFLICT (athlete_id, sport, season_year, stat_key)
                       DO UPDATE SET
                         stat_value = EXCLUDED.stat_value,
                         position_group = EXCLUDED.position_group,
                         games_played = EXCLUDED.games_played,
                         observed_at = EXCLUDED.observed_at,
                         metadata = EXCLUDED.metadata""",
                    athlete_id,
                    sport,
                    league,
                    year,
                    position_group,
                    key,
                    float(val),
                    games,
                    source_key,
                    datetime.now(tz=timezone.utc),
                    json.dumps(meta),
                )
                count += 1
            except asyncpg.PostgresError:
                continue
        return count

    current_year = season_year or _current_season_year(sport)

    history = raw.get("season_stats_history")
    history_years: dict[int, dict[str, float]] = {}
    if isinstance(history, dict):
        for season_label, season_blob in history.items():
            if not isinstance(season_blob, dict):
                continue
            year = _parse_season_year(season_label, fallback=current_year)
            normalized = flatten_raw_for_stats({"season_stats": season_blob}, sport)
            if not normalized:
                continue
            history_years[year] = normalized
            written += await _write_season(
                normalized,
                year,
                source_key=str(raw.get("stats_source") or "espn_history"),
            )

    # Persist the scraper's current-season blob under the true current year only
    # when history did not already provide that year (avoid overwriting a clean
    # per-season split with career-cumulative leakage from top-level scalars).
    wrote_current = False
    if current_year not in history_years:
        flattened = flatten_raw_for_stats(raw, sport)
        if flattened and _season_has_games(flattened):
            written += await _write_season(
                flattened,
                current_year,
                source_key=str(raw.get("stats_source") or "scraper"),
                metadata={"anchor_policy": "in_progress_current"},
            )
            wrote_current = True

    # Clear legacy pollution: old code copied prior seasons into current_year.
    # If this scrape has real history but no true current-year split (and we did
    # not write a fresh in-progress current), drop those mislabeled rows so the
    # read resolver falls back to the latest completed *true* year.
    if history_years and current_year not in history_years and not wrote_current:
        try:
            await conn.execute(
                """DELETE FROM athlete_season_stats
                   WHERE athlete_id = $1::uuid AND sport = $2 AND season_year = $3""",
                athlete_id,
                sport,
                current_year,
            )
        except asyncpg.PostgresError:
            pass

    return written


def resolve_scoring_season_year(
    available_years: list[int] | set[int],
    *,
    current_year: int | None = None,
    sport: str | None = None,
    games_by_year: dict[int, int] | None = None,
) -> dict[str, Any]:
    """Pick which ASS season_year should drive scoring features.

    Prefers the in-progress / current year when it has games; otherwise the
    latest completed year. Never invents a year that is not in ``available_years``.
    """
    current = current_year if current_year is not None else _current_season_year(sport)
    years = sorted({int(y) for y in available_years})
    games_by_year = games_by_year or {}

    def _games(y: int) -> int:
        return int(games_by_year.get(y) or 0)

    if current in years and _games(current) > 0:
        return {
            "season_year": current,
            "source_season_year": current,
            "is_partial": True,
            "policy": "current_in_progress",
        }
    if current in years:
        # Row exists but no games yet (early season / empty) — still prefer it
        # over silently labeling prior as current when callers only have the key.
        completed = [y for y in years if y < current and _games(y) > 0]
        if completed:
            src = max(completed)
            return {
                "season_year": src,
                "source_season_year": src,
                "is_partial": False,
                "policy": "latest_completed",
            }
        return {
            "season_year": current,
            "source_season_year": current,
            "is_partial": True,
            "policy": "current_empty",
        }

    completed = [y for y in years if y < current]
    if completed:
        # Prefer a completed year that actually has games when known.
        with_games = [y for y in completed if _games(y) > 0]
        src = max(with_games or completed)
        return {
            "season_year": src,
            "source_season_year": src,
            "is_partial": False,
            "policy": "latest_completed",
        }
    if years:
        src = max(years)
        return {
            "season_year": src,
            "source_season_year": src,
            "is_partial": src >= current,
            "policy": "latest_available",
        }
    return {
        "season_year": current,
        "source_season_year": current,
        "is_partial": True,
        "policy": "fallback_current",
    }


def _season_has_games(stats: dict[str, float]) -> bool:
    gp = stats.get("games_played_season") or stats.get("gp") or 0
    try:
        return float(gp) > 0
    except (TypeError, ValueError):
        return False


def _parse_season_year(label: str | int, *, fallback: int) -> int:
    """Normalize season labels to a single INT year.

    Split labels like ``2024-25`` / ``2024-2025`` use the **ending** year so
    NBA/NCAAB seasons align with ESPN ``season.year`` and do not understate
    by one (which stacked with a stale history floor produced ~2-year lag).
    """
    if isinstance(label, int):
        return label
    text = str(label).strip()
    m = _SPLIT_SEASON_RE.search(text)
    if m:
        start = int(m.group(1))
        end_raw = m.group(2)
        end = int(end_raw) if len(end_raw) == 4 else 2000 + int(end_raw)
        if end >= start:
            return end
    for token in text.replace("-", " ").replace("/", " ").split():
        if token.isdigit() and len(token) == 4:
            return int(token)
    return fallback


def _current_season_year(sport: str | None = None) -> int:
    """Calendar heuristic for the active stats season start/end key.

    Football / most sports: July→December uses calendar year; Jan→June uses
    prior year. Basketball (NBA/NCAAB/WNBA): Oct→June spans two years and is
    keyed by the **ending** calendar year (2025-26 → 2026).
    """
    now = datetime.now(tz=timezone.utc)
    sport_l = (sport or "").lower().strip()
    basketball = sport_l in {
        "nba",
        "wnba",
        "ncaab_mens",
        "ncaab_womens",
        "mcbb",
        "wcbb",
        "mens-college-basketball",
        "womens-college-basketball",
    }
    if basketball:
        # Oct–Dec: new season ending next calendar year; Jan–Jun: ending this year;
        # Jul–Sep: offseason → just-completed ending year (== calendar year).
        if now.month >= 10:
            return now.year + 1
        return now.year
    return now.year if now.month >= 7 else now.year - 1
