"""DB sync and query helpers for scraper_registry."""

from __future__ import annotations

import json
from typing import Any

import asyncpg

from gravity_api.scraper_registry import build_registry, registry_by_key
from gravity_api.scraper_registry.events import resolve_event_scraper_keys


async def sync_registry_to_db(conn: asyncpg.Connection) -> dict[str, int]:
    """Upsert all manifest scrapers into scraper_registry."""
    registry = build_registry()
    upserted = 0
    for defn in registry:
        await conn.execute(
            """INSERT INTO scraper_registry (
                 scraper_key, display_name, sport, league_tier, dimension,
                 source, source_type, description, feature_keys, status,
                 terminal_visible, required_for_scoring, sla_days,
                 default_confidence, circuit_breaker_source, priority, metadata
               ) VALUES (
                 $1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10,
                 $11, $12, $13, $14, $15, $16, $17::jsonb
               )
               ON CONFLICT (scraper_key) DO UPDATE SET
                 display_name = EXCLUDED.display_name,
                 sport = EXCLUDED.sport,
                 league_tier = EXCLUDED.league_tier,
                 dimension = EXCLUDED.dimension,
                 source = EXCLUDED.source,
                 source_type = EXCLUDED.source_type,
                 description = EXCLUDED.description,
                 feature_keys = EXCLUDED.feature_keys,
                 status = EXCLUDED.status,
                 terminal_visible = EXCLUDED.terminal_visible,
                 required_for_scoring = EXCLUDED.required_for_scoring,
                 sla_days = EXCLUDED.sla_days,
                 default_confidence = EXCLUDED.default_confidence,
                 circuit_breaker_source = EXCLUDED.circuit_breaker_source,
                 priority = EXCLUDED.priority,
                 metadata = EXCLUDED.metadata,
                 updated_at = NOW()""",
            defn.scraper_key,
            defn.display_name,
            defn.sport,
            defn.league_tier,
            defn.dimension,
            defn.source,
            defn.source_type,
            defn.description,
            json.dumps(list(defn.feature_keys)),
            defn.status,
            defn.terminal_visible,
            defn.required_for_scoring,
            defn.sla_days,
            defn.default_confidence,
            defn.circuit_breaker_source,
            defn.priority,
            json.dumps(defn.metadata),
        )
        upserted += 1
    return {"upserted": upserted, "total_manifest": len(registry)}


async def list_registry(
    conn: asyncpg.Connection,
    *,
    sport: str | None = None,
    league_tier: str | None = None,
    dimension: str | None = None,
    terminal_only: bool = False,
) -> list[dict[str, Any]]:
    conditions = ["active = TRUE"]
    params: list[Any] = []
    idx = 1
    if sport:
        conditions.append(f"(sport = ${idx} OR sport = '*')")
        params.append(sport)
        idx += 1
    if league_tier:
        conditions.append(f"league_tier = ${idx}")
        params.append(league_tier)
        idx += 1
    if dimension:
        conditions.append(f"dimension = ${idx}")
        params.append(dimension)
        idx += 1
    if terminal_only:
        conditions.append("terminal_visible = TRUE")
    where = " AND ".join(conditions)
    rows = await conn.fetch(
        f"""SELECT * FROM scraper_registry WHERE {where}
            ORDER BY sport, priority, scraper_key""",
        *params,
    )
    return [dict(r) for r in rows]


async def record_run_result(
    conn: asyncpg.Connection,
    *,
    scraper_key: str,
    status: str,
    athlete_id: str | None = None,
    job_id: str | None = None,
    sport: str | None = None,
    fields_written: list[str] | None = None,
    fields_failed: list[str] | None = None,
    error_message: str | None = None,
    duration_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    if scraper_key not in registry_by_key():
        raise ValueError(f"Unknown scraper_key: {scraper_key}")
    run_id = await conn.fetchval(
        """INSERT INTO scraper_run_results (
             scraper_key, athlete_id, job_id, sport, status,
             fields_written, fields_failed, error_message, duration_ms, metadata
           ) VALUES (
             $1, $2::uuid, $3::uuid, $4, $5,
             $6::jsonb, $7::jsonb, $8, $9, $10::jsonb
           ) RETURNING id::text""",
        scraper_key,
        athlete_id,
        job_id,
        sport,
        status,
        json.dumps(fields_written or []),
        json.dumps(fields_failed or []),
        error_message,
        duration_ms,
        json.dumps(metadata or {}),
    )
    return str(run_id)


async def scraper_health_summary(conn: asyncpg.Connection, *, hours: int = 24) -> list[dict[str, Any]]:
    """Success rate per scraper over the last N hours."""
    rows = await conn.fetch(
        """SELECT r.scraper_key,
                  sr.display_name,
                  sr.sport,
                  sr.dimension,
                  COUNT(*)::int AS runs,
                  COUNT(*) FILTER (WHERE r.status = 'success')::int AS successes,
                  COUNT(*) FILTER (WHERE r.status = 'failed')::int AS failures,
                  MAX(r.observed_at) AS last_run_at
           FROM scraper_run_results r
           JOIN scraper_registry sr ON sr.scraper_key = r.scraper_key
           WHERE r.observed_at > NOW() - ($1::text || ' hours')::interval
           GROUP BY r.scraper_key, sr.display_name, sr.sport, sr.dimension
           ORDER BY failures DESC, r.scraper_key""",
        str(hours),
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        runs = int(d["runs"] or 0)
        successes = int(d["successes"] or 0)
        d["success_rate"] = round(successes / runs, 4) if runs else None
        if d.get("last_run_at"):
            d["last_run_at"] = d["last_run_at"].isoformat()
        out.append(d)
    return out


def manifest_summary() -> dict[str, Any]:
    reg = build_registry()
    by_sport: dict[str, int] = {}
    by_dimension: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    achievements = 0
    required = 0
    for d in reg:
        by_sport[d.sport] = by_sport.get(d.sport, 0) + 1
        by_dimension[d.dimension] = by_dimension.get(d.dimension, 0) + 1
        by_tier[d.league_tier] = by_tier.get(d.league_tier, 0) + 1
        if d.dimension == "achievements":
            achievements += 1
        if d.required_for_scoring:
            required += 1
    return {
        "total": len(reg),
        "by_sport": by_sport,
        "by_dimension": by_dimension,
        "by_league_tier": by_tier,
        "achievements_scrapers": achievements,
        "required_for_scoring": required,
    }


__all__ = [
    "sync_registry_to_db",
    "list_registry",
    "record_run_result",
    "scraper_health_summary",
    "manifest_summary",
    "resolve_event_scraper_keys",
]
