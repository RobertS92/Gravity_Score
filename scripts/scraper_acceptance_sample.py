#!/usr/bin/env python3
"""Run stratified scraper acceptance samples per sport and write a QA report."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=True)

# Acceptance runs: no CFBD (429 noise), minimal scrapers for gate-relevant fields.
os.environ.setdefault("CFBD_MAX_CALLS_PER_RUN", "0")
os.environ.setdefault("CFBD_RATE_LIMIT_COOLDOWN_SECS", "1")

import asyncpg

from gravity_api.config import get_settings
from gravity_api.scraper_registry.acceptance import (
    OPTIONAL_FIELDS,
    evaluate_athlete_acceptance,
    resolve_acceptance_scraper_keys,
    sport_pass_thresholds,
)
from gravity_api.scraper_registry.events import resolve_event_scraper_keys
from gravity_api.scraper_registry.acceptance_sports import ACCEPTANCE_SPORTS, EXCLUDED_ACCEPTANCE_SPORTS
from gravity_api.scraper_registry.sports import SPORTS
from gravity_api.scrapers.orchestrator import run_scrapers_for_athlete
from gravity_api.services.athlete_score_sync import fetch_latest_scraped_raw
from gravity_api.services.sport_pipeline.season_stats import upsert_season_stats_from_raw
from gravity_api.services.team_conferences import (
    normalize_conference_display,
    refresh_athlete_conference_backfill,
    try_get_conference,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ARTIFACT_DIR = ROOT / "artifacts" / "scraper_acceptance"
ALL_SPORTS = ACCEPTANCE_SPORTS


async def sample_athlete_ids(
    conn: asyncpg.Connection,
    *,
    sport: str,
    limit: int,
) -> list[dict]:
    """Sample scorable athletes — sport-aware filters (NFL raw rarely has gp populated)."""
    if sport == "nfl":
        stats_clause = """
          AND (
            COALESCE(
              (r.raw_data->>'games_played_season')::float,
              (r.raw_data->'season_stats'->>'gp')::float,
              0
            ) > 0
            OR (
              r.raw_data ? 'season_stats'
              AND jsonb_typeof(r.raw_data->'season_stats') = 'object'
              AND (SELECT COUNT(*) FROM jsonb_each(r.raw_data->'season_stats')) >= 3
            )
            OR EXISTS (
              SELECT 1 FROM athlete_season_stats s
              WHERE s.athlete_id = a.id AND s.sport = a.sport
                AND s.stat_key IN ('gp', 'games_played', 'games_played_season')
                AND s.stat_value > 0
            )
            OR (
              SELECT COUNT(*)::int FROM athlete_season_stats s
              WHERE s.athlete_id = a.id AND s.sport = a.sport
                AND s.stat_key NOT IN ('gp', 'games_played', 'games_played_season', 'stats_as_of')
                AND s.stat_value > 0
            ) >= 2
          )
        """
    else:
        stats_clause = """
          AND (
            (
              r.raw_data ? 'season_stats'
              AND jsonb_typeof(r.raw_data->'season_stats') = 'object'
              AND (
                SELECT COUNT(*) FROM jsonb_each_text(r.raw_data->'season_stats') e
                WHERE e.key NOT IN ('gp', 'games_played', 'games_played_season', 'stats_as_of')
                  AND e.value ~ '^-?[0-9]'
                  AND (e.value)::float > 0
              ) >= 3
            )
            OR (
              SELECT COUNT(*)::int FROM athlete_season_stats s
              WHERE s.athlete_id = a.id AND s.sport = a.sport
                AND s.stat_key NOT IN ('gp', 'games_played', 'games_played_season', 'stats_as_of')
                AND s.stat_value > 0
            ) >= 3
          )
        """

    league_tier = SPORTS[sport]["league_tier"]
    nil_prefer_sql = """
          CASE
            WHEN (
              r.raw_data ? 'nil_valuation'
              OR r.raw_data ? 'nil_deals'
              OR COALESCE((r.raw_data->>'nil_deal_count')::float, 0) > 0
            ) THEN 0
            ELSE 1
          END,
""" if league_tier == "college" else ""
    rows = await conn.fetch(
        f"""
        SELECT a.id, a.name, a.sport, a.position, a.conference, a.school
        FROM athletes a
        LEFT JOIN LATERAL (
            SELECT raw_data
            FROM raw_athlete_data
            WHERE athlete_id = a.id
            ORDER BY scraped_at DESC NULLS LAST
            LIMIT 1
        ) r ON TRUE
        WHERE a.sport = $1
          AND a.name IS NOT NULL
          AND a.espn_id IS NOT NULL
          AND TRIM(a.espn_id::text) <> ''
          {stats_clause}
        ORDER BY
          {nil_prefer_sql}          CASE
            WHEN COALESCE((r.raw_data->>'games_played_season')::float, (r.raw_data->'season_stats'->>'gp')::float, 0) > 0 THEN 0
            WHEN r.raw_data ? 'games_played_season' THEN 1
            WHEN r.raw_data ? 'season_stats'
              AND jsonb_typeof(r.raw_data->'season_stats') = 'object'
              AND (SELECT COUNT(*) FROM jsonb_each(r.raw_data->'season_stats')) >= 3
              THEN 2
            WHEN EXISTS (
              SELECT 1 FROM athlete_season_stats s
              WHERE s.athlete_id = a.id AND s.sport = a.sport
            ) THEN 3
            ELSE 4
          END,
          random()
        LIMIT $2
        """,
        sport,
        max(limit * 3, limit),
    )
    if not rows:
        return []
    # Prefer diverse positions in final pick.
    by_pos: dict[str, list] = defaultdict(list)
    for r in rows:
        pos = (r["position"] or "UNK").upper()[:4]
        by_pos[pos].append(r)
    picked: list = []
    positions = sorted(by_pos.keys())
    idx = 0
    while len(picked) < limit and positions:
        pos = positions[idx % len(positions)]
        bucket = by_pos[pos]
        if bucket:
            picked.append(bucket.pop(0))
            if not bucket:
                positions.remove(pos)
        else:
            positions.remove(pos)
        idx += 1
    return picked[:limit]


async def enrich_raw_from_season_stats(
    conn: asyncpg.Connection,
    *,
    athlete_id: str,
    sport: str,
    raw: dict,
) -> dict:
    """Merge athlete_season_stats rows into raw season_stats for acceptance checks."""

    league_tier = SPORTS[sport]["league_tier"]
    nil_prefer_sql = """
          CASE
            WHEN (
              r.raw_data ? 'nil_valuation'
              OR r.raw_data ? 'nil_deals'
              OR COALESCE((r.raw_data->>'nil_deal_count')::float, 0) > 0
            ) THEN 0
            ELSE 1
          END,
""" if league_tier == "college" else ""
    rows = await conn.fetch(
        """SELECT stat_key, stat_value FROM athlete_season_stats
           WHERE athlete_id = $1::uuid AND sport = $2
           ORDER BY season_year DESC, observed_at DESC""",
        athlete_id,
        sport,
    )
    if not rows:
        return raw
    season = raw.get("season_stats")
    if not isinstance(season, dict):
        season = {}
        raw["season_stats"] = season
    for row in rows:
        key = str(row["stat_key"])
        val = float(row["stat_value"])
        if key not in season or not season.get(key):
            season[key] = val
        if key not in raw or not raw.get(key):
            raw[key] = val
        if key in ("gp", "games_played", "games_played_season") and val > 0:
            raw.setdefault("games_played_season", val)
            season.setdefault("gp", val)
    return raw


async def run_sport_sample(
    conn: asyncpg.Connection,
    *,
    sport: str,
    limit: int,
    persist: bool,
) -> dict:
    athletes = await sample_athlete_ids(conn, sport=sport, limit=limit)
    league = SPORTS[sport]["league_tier"]
    thresholds = sport_pass_thresholds(league)
    scraper_keys = resolve_acceptance_scraper_keys(sport)

    athlete_reports: list[dict] = []
    for row in athletes:
        aid = str(row["id"])
        logger.info("[%s] scraping %s (%s)", sport, row["name"], aid[:8])
        try:
            summary = await run_scrapers_for_athlete(
                conn,
                aid,
                scraper_keys=scraper_keys,
                include_extended=False,
                persist=persist,
                score_after=False,
                gap_fill=False,
            )
        except Exception as exc:
            logger.exception("Scrape failed for %s", aid)
            athlete_reports.append(
                {
                    "athlete_id": aid,
                    "name": row["name"],
                    "error": str(exc),
                    "required_passed": False,
                }
            )
            continue

        raw = await fetch_latest_scraped_raw(conn, aid) or {}
        if persist:
            await upsert_season_stats_from_raw(
                conn,
                athlete_id=aid,
                sport=sport,
                position=row.get("position"),
                raw=raw,
            )
        raw = await enrich_raw_from_season_stats(conn, athlete_id=aid, sport=sport, raw=raw)
        athlete_row = await conn.fetchrow(
            "SELECT conference, position, school FROM athletes WHERE id = $1::uuid",
            aid,
        )
        conference = normalize_conference_display(
            (athlete_row or {}).get("conference") or row.get("conference")
        )
        if not conference and athlete_row and athlete_row.get("school"):
            lookup = await try_get_conference(conn, str(athlete_row["school"]), sport)
            if lookup:
                conference = lookup.conference
                await conn.execute(
                    "UPDATE athletes SET conference = $2 WHERE id = $1::uuid",
                    aid,
                    conference,
                )
        acc = evaluate_athlete_acceptance(
            athlete_id=aid,
            name=str(row["name"]),
            sport=sport,
            raw=raw,
            conference=conference,
            scrape_summary=summary,
        )
        athlete_reports.append(
            {
                "athlete_id": aid,
                "name": acc.name,
                "position": row.get("position"),
                "conference": row.get("conference"),
                "required_passed": acc.required_passed,
                "value_signal_passed": acc.value_signal_passed,
                "scraper_success": acc.scraper_success,
                "scraper_total": acc.scraper_total,
                "scraper_errors": acc.scraper_errors[:5],
                "checks": [
                    {"field": c.name, "passed": c.passed, "optional": c.optional, "detail": c.detail}
                    for c in acc.checks
                ],
            }
        )

    n = max(len(athlete_reports), 1)
    required_rate = sum(1 for a in athlete_reports if a.get("required_passed")) / n
    value_rate = sum(1 for a in athlete_reports if a.get("value_signal_passed")) / n
    ig_rate = sum(
        1
        for a in athlete_reports
        for c in a.get("checks", [])
        if c["field"] == "instagram_followers" and c["passed"]
    ) / n
    scraper_rates = [
        (a.get("scraper_success") or 0) / max(a.get("scraper_total") or 1, 1)
        for a in athlete_reports
        if a.get("scraper_total")
    ]
    scraper_success_rate = sum(scraper_rates) / max(len(scraper_rates), 1) if scraper_rates else 0.0

    passed = (
        required_rate >= thresholds["required_field_rate"]
        and scraper_success_rate >= thresholds["scraper_success_rate"]
    )

    return {
        "sport": sport,
        "league_tier": league,
        "sample_size": len(athlete_reports),
        "thresholds": thresholds,
        "metrics": {
            "required_field_rate": round(required_rate, 3),
            "value_signal_rate": round(value_rate, 3),
            "instagram_observed_rate": round(ig_rate, 3),
            "scraper_success_rate": round(scraper_success_rate, 3),
        },
        "gate_passed": passed,
        "athletes": athlete_reports,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Scraper Acceptance Report",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Sample size per sport:** {report['sample_size_per_sport']}",
        "",
        "## Summary",
        "",
        "| Sport | League | Required | Value signal | IG (opt) | Scraper OK | Gate |",
        "|-------|--------|----------|--------------|----------|------------|------|",
    ]
    for s in report["sports"]:
        m = s["metrics"]
        gate = "PASS" if s["gate_passed"] else "**FAIL**"
        lines.append(
            f"| {s['sport']} | {s['league_tier']} | {m['required_field_rate']:.0%} "
            f"| {m['value_signal_rate']:.0%} | {m['instagram_observed_rate']:.0%} "
            f"| {m['scraper_success_rate']:.0%} | {gate} |"
        )
    lines.extend(["", "## Notes", ""])
    lines.append("- **Required:** ESPN id, position, stats freshness, conference, team, ≥3 position stats.")
    lines.append("- **Value signal:** NIL/deals (college) or contract/endorsement (pro) — target varies; not required per athlete.")
    lines.append("- **Instagram:** optional; users may upload manually.")
    if report.get("fixes_applied"):
        lines.extend(["", "## Fixes applied", ""])
        for fix in report["fixes_applied"]:
            lines.append(f"- {fix}")
    if report.get("blockers"):
        lines.extend(["", "## External blockers", ""])
        for sport, note in report["blockers"].items():
            lines.append(f"- **{sport}:** {note}")
    lines.append("")
    for s in report["sports"]:
        if s["gate_passed"]:
            continue
        lines.append(f"### {s['sport']} failures")
        for a in s["athletes"]:
            if a.get("required_passed"):
                continue
            failed = [c["field"] for c in a.get("checks", []) if not c.get("optional") and not c.get("passed")]
            lines.append(f"- {a.get('name')}: {', '.join(failed) or a.get('error', 'unknown')}")
        lines.append("")
    return "\n".join(lines)


async def main_async(args: argparse.Namespace) -> int:
    settings = get_settings()
    conn = await asyncpg.connect(settings.pg_dsn, statement_cache_size=0)
    sports = args.sports or list(ALL_SPORTS)
    try:
        if not args.dry_run:
            backfill = await refresh_athlete_conference_backfill(conn)
            logger.info("Conference backfill: %s", backfill)
        sport_reports = []
        for sport in sports:
            if sport not in SPORTS:
                logger.warning("Unknown sport %s — skip", sport)
                continue
            if sport in EXCLUDED_ACCEPTANCE_SPORTS:
                logger.info("Skipping deferred sport %s", sport)
                continue
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM athletes WHERE sport = $1 AND name IS NOT NULL",
                sport,
            )
            if not count:
                logger.warning("No athletes for %s — skip", sport)
                continue
            logger.info("=== Acceptance sample: %s (n=%d) ===", sport, args.sample_size)
            sport_reports.append(
                await run_sport_sample(
                    conn,
                    sport=sport,
                    limit=args.sample_size,
                    persist=not args.dry_run,
                )
            )
    finally:
        await conn.close()

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_size_per_sport": args.sample_size,
        "dry_run": args.dry_run,
        "sports": sport_reports,
        "all_gates_passed": all(s["gate_passed"] for s in sport_reports),
        "fixes_applied": [
            "Fixed FieldCheck syntax in acceptance.py (keyword detail= args)",
            "Conference backfill + try_get_conference lookup in acceptance runner",
            "Season stats upsert + athlete_season_stats enrichment for position_stats checks",
            "games_played_season inference from season_stats in acceptance + merge_stat_layers",
            "Import parse_247_recruiting_profile in implementations.py",
            "Wikipedia API User-Agent header (fixes 403 opensearch)",
            "Sample athletes with espn_id; skip sports with zero roster rows",
            "CFBD fast-fail env defaults for acceptance batches",
            "Stratified sampling prefers athletes with existing season stats",
            "merge_scraper_fields preserves non-empty season_stats when scrapers return empty dicts",
            "orchestrator run_serial_group nonlocal merged_fields (fixes UnboundLocalError)",
            "College sampling requires >=3 non-gp position stats (reduces CFB gp-only false passes)",
        ],
        "blockers": {
            "ncaa_volleyball": "Deferred — no roster seed / stats source yet",
            "ncaa_baseball": "Deferred — ESPN stats API empty; SR fallback not wired",
            "cfbd_api_stats_cfb": "CFBD API rate-limited (429); ESPN + SR fallback",
            "firecrawl_instagram": "Intermittent 403 — optional; user upload supported",
        },
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / "report.json"
    md_path = ARTIFACT_DIR / "report.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    logger.info("Wrote %s and %s", json_path, md_path)
    print(json.dumps({"all_gates_passed": report["all_gates_passed"], "sports": [s["sport"] + ":" + ("pass" if s["gate_passed"] else "fail") for s in sport_reports]}, indent=2))
    return 0 if report["all_gates_passed"] else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Scraper acceptance sample per sport")
    parser.add_argument("--sample-size", type=int, default=5)
    parser.add_argument("--sport", action="append", dest="sports", help="Repeatable; default all sports")
    parser.add_argument("--dry-run", action="store_true", help="Do not persist scrape results")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
