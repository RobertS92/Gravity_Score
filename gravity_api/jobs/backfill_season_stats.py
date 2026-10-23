"""Backfill per-season athlete_season_stats from ESPN (SCRAPER_FIX_SPEC WP7).

For each athlete with an ESPN id (active **and** inactive), enumerate seasons,
fetch season-scoped lines, validate completed seasons, and rebuild EAV rows in
one transaction per athlete.

Usage::

  PYTHONPATH=. python3 -m gravity_api.jobs.backfill_season_stats --sport nba --limit 20
  PYTHONPATH=. python3 -m gravity_api.jobs.backfill_season_stats --espn-id 1966 --sport nba
  PYTHONPATH=. python3 -m gravity_api.jobs.backfill_season_stats --refresh-season 2025 --sport nba
  PYTHONPATH=. python3 -m gravity_api.jobs.backfill_season_stats --current-only --sport nba

Defaults: skip completed seasons already ``validation_status='matched'`` unless
``--refresh-season YEAR``; always refresh ``in_progress`` seasons; include
inactive athletes (history matters for departed players).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)

import asyncpg

from gravity_api.scrapers.clients.espn import EspnClient
from gravity_api.scrapers.season_calendar import season_status
from gravity_api.scrapers.types import SeasonStatLine
from gravity_api.services.sport_pipeline.season_stats_store import upsert_season_stat_lines

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_SPORTS = ("nba", "nfl", "cfb", "ncaab_mens", "ncaab_womens")


async def _ensure_checkpoint_table(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS scraper_backfill_checkpoint (
             job_key TEXT NOT NULL,
             sport TEXT NOT NULL,
             athlete_id UUID NOT NULL,
             espn_id TEXT,
             last_season_year INT,
             status TEXT NOT NULL DEFAULT 'ok',
             detail TEXT,
             updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
             PRIMARY KEY (job_key, athlete_id)
           )"""
    )


async def _athletes(
    conn: asyncpg.Connection,
    *,
    sport: str,
    limit: int,
    espn_id: str | None,
    after_athlete_id: str | None,
) -> list[asyncpg.Record]:
    """Include inactive athletes — history matters for departed players."""
    if espn_id:
        return await conn.fetch(
            """SELECT id, espn_id, sport, position, name, is_active
               FROM athletes
               WHERE espn_id = $1 AND sport = $2
               ORDER BY id
               LIMIT $3""",
            str(espn_id),
            sport,
            limit,
        )
    if after_athlete_id:
        return await conn.fetch(
            """SELECT id, espn_id, sport, position, name, is_active
               FROM athletes
               WHERE sport = $1
                 AND espn_id IS NOT NULL
                 AND id > $2::uuid
               ORDER BY id
               LIMIT $3""",
            sport,
            after_athlete_id,
            limit,
        )
    return await conn.fetch(
        """SELECT id, espn_id, sport, position, name, is_active
           FROM athletes
           WHERE sport = $1
             AND espn_id IS NOT NULL
           ORDER BY id
           LIMIT $2""",
        sport,
        limit,
    )


async def _matched_years(
    conn: asyncpg.Connection, athlete_id: str, sport: str
) -> set[int]:
    rows = await conn.fetch(
        """SELECT DISTINCT season_year
           FROM athlete_season_stats
           WHERE athlete_id = $1::uuid
             AND sport = $2
             AND team_id = 'TOT'
             AND season_type = 'regular'
             AND validation_status = 'matched'""",
        athlete_id,
        sport,
    )
    return {int(r["season_year"]) for r in rows}


async def _delete_athlete_season_rows(
    conn: asyncpg.Connection, athlete_id: str, sport: str, *, years: set[int] | None
) -> None:
    """Rebuild scope: delete rows for years being rewritten (or all if years is None)."""
    if years is None:
        await conn.execute(
            """DELETE FROM athlete_season_stats
               WHERE athlete_id = $1::uuid AND sport = $2""",
            athlete_id,
            sport,
        )
        return
    if not years:
        return
    await conn.execute(
        """DELETE FROM athlete_season_stats
           WHERE athlete_id = $1::uuid
             AND sport = $2
             AND season_year = ANY($3::int[])""",
        athlete_id,
        sport,
        sorted(years),
    )


def _with_validation(
    line: SeasonStatLine, status: str
) -> SeasonStatLine:
    # SeasonStatLine is frozen; validation_status is stored by the writer via
    # a parallel channel. We stamp source_key metadata lightly when mismatch.
    if status == "matched":
        return line
    return SeasonStatLine(
        league=line.league,
        season_year=line.season_year,
        season_type=line.season_type,
        team_id=line.team_id,
        team_name=line.team_name,
        is_total=line.is_total,
        stats=line.stats,
        source_key=f"{line.source_key}|{status}",
        source_url=line.source_url,
        stats_as_of=line.stats_as_of,
    )


async def backfill_one(
    conn: asyncpg.Connection,
    row: asyncpg.Record,
    *,
    refresh_years: set[int],
    current_only: bool,
    client: EspnClient | None = None,
) -> dict:
    client = client or EspnClient()
    espn_id = str(row["espn_id"])
    sport = str(row["sport"])
    athlete_id = str(row["id"])
    today = datetime.now(tz=timezone.utc).date()

    seasons = await client.list_stat_seasons(espn_id, sport)
    # Unique years (regular preferred for enumeration).
    years = sorted({y for y, _st, _ref in seasons})
    if not years:
        return {
            "athlete_id": athlete_id,
            "espn_id": espn_id,
            "sport": sport,
            "season_rows": 0,
            "written": 0,
            "skipped_matched": 0,
        }

    matched = await _matched_years(conn, athlete_id, sport)
    lines: list[SeasonStatLine] = []
    skipped_matched = 0
    rewrite_years: set[int] = set()

    for year in years:
        status = season_status(sport, year, today)
        if current_only and status != "in_progress" and year not in refresh_years:
            continue
        if (
            status == "complete"
            and year in matched
            and year not in refresh_years
            and not current_only
        ):
            skipped_matched += 1
            continue

        # Fetch regular (+ postseason when present in log).
        types_for_year = {st for y, st, _ in seasons if y == year} or {"regular"}
        if "regular" not in types_for_year:
            types_for_year.add("regular")
        for stype in sorted(types_for_year, key=lambda s: 0 if s == "regular" else 1):
            season_lines = await client.get_season_stat_lines(
                espn_id, sport, year, stype
            )
            for line in season_lines:
                # Validate completed TOT regular rows when validator is available.
                vstatus = "unvalidated"
                if (
                    status == "complete"
                    and line.is_total
                    and line.season_type == "regular"
                ):
                    try:
                        from gravity_api.services.stat_validation import (
                            fetch_second_source_stats,
                            log_validation_result,
                            validate_completed_season,
                        )

                        second = await fetch_second_source_stats(
                            line,
                            athlete_name=str(row.get("name") or espn_id),
                            position=row.get("position"),
                            team=line.team_name,
                        )
                        result = validate_completed_season(
                            line,
                            second_source_stats=second,
                            position=row.get("position"),
                        )
                        vstatus = getattr(result, "status", None) or "unvalidated"
                        # Spec §4.4: mismatch still stored; log both values to
                        # collection_errors / scraper_jobs channel.
                        log_validation_result(
                            result,
                            athlete_name=str(row.get("name") or espn_id),
                        )
                    except Exception:  # noqa: BLE001
                        vstatus = "unvalidated"
                    line = _with_validation(line, str(vstatus))
                lines.append(line)
            rewrite_years.add(year)

    async with conn.transaction():
        # Rebuild rewritten years inside the athlete transaction.
        await _delete_athlete_season_rows(
            conn, athlete_id, sport, years=rewrite_years
        )
        written = await upsert_season_stat_lines(
            conn,
            athlete_id=athlete_id,
            lines=lines,
            position=row.get("position"),
            sport=sport,
        )

    await conn.execute(
        """INSERT INTO scraper_backfill_checkpoint (
             job_key, sport, athlete_id, espn_id, last_season_year, status, detail, updated_at
           ) VALUES (
             'season_stats', $1, $2::uuid, $3, $4, 'ok', $5, NOW()
           )
           ON CONFLICT (job_key, athlete_id) DO UPDATE SET
             espn_id = EXCLUDED.espn_id,
             last_season_year = EXCLUDED.last_season_year,
             status = EXCLUDED.status,
             detail = EXCLUDED.detail,
             updated_at = NOW()""",
        sport,
        athlete_id,
        espn_id,
        max(rewrite_years) if rewrite_years else (max(years) if years else None),
        f"written={written};skipped_matched={skipped_matched}",
    )

    return {
        "athlete_id": athlete_id,
        "name": row.get("name"),
        "espn_id": espn_id,
        "sport": sport,
        "season_rows": len(lines),
        "written": written,
        "skipped_matched": skipped_matched,
        "is_active": row.get("is_active"),
    }


async def main_async(args: argparse.Namespace) -> int:
    dsn = os.environ.get("PG_DSN", "").strip()
    if not dsn:
        logger.error("PG_DSN is required")
        return 2

    refresh_years = {int(y) for y in (args.refresh_season or [])}
    sports = [args.sport] if args.sport else list(DEFAULT_SPORTS)
    conn = await asyncpg.connect(dsn, command_timeout=180)
    client = EspnClient()
    try:
        await _ensure_checkpoint_table(conn)
        for sport in sports:
            after = args.after_athlete_id
            rows = await _athletes(
                conn,
                sport=sport,
                limit=args.limit,
                espn_id=args.espn_id,
                after_athlete_id=after,
            )
            logger.info("[%s] %d athletes (incl. inactive)", sport, len(rows))
            for row in rows:
                try:
                    summary = await backfill_one(
                        conn,
                        row,
                        refresh_years=refresh_years,
                        current_only=args.current_only,
                        client=client,
                    )
                    logger.info(
                        "[%s] %s seasons=%s written=%s skipped_matched=%s active=%s",
                        sport,
                        summary.get("name") or summary["espn_id"],
                        summary["season_rows"],
                        summary["written"],
                        summary.get("skipped_matched"),
                        summary.get("is_active"),
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[%s] %s failed: %s", sport, row.get("espn_id"), exc
                    )
                    try:
                        await conn.execute(
                            """INSERT INTO scraper_backfill_checkpoint (
                                 job_key, sport, athlete_id, espn_id, status, detail, updated_at
                               ) VALUES (
                                 'season_stats', $1, $2::uuid, $3, 'error', $4, NOW()
                               )
                               ON CONFLICT (job_key, athlete_id) DO UPDATE SET
                                 status = 'error',
                                 detail = EXCLUDED.detail,
                                 updated_at = NOW()""",
                            sport,
                            str(row["id"]),
                            str(row.get("espn_id")),
                            str(exc)[:500],
                        )
                    except Exception:  # noqa: BLE001
                        pass
    finally:
        await conn.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sport", default=None, help="Single sport key")
    p.add_argument("--espn-id", default=None, help="Backfill one ESPN id")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument(
        "--after-athlete-id",
        default=None,
        help="Resume after this athlete UUID (checkpoint cursor).",
    )
    p.add_argument(
        "--refresh-season",
        action="append",
        default=[],
        help="ESPN season year to force-refresh (repeatable). "
        "Completed matched seasons are otherwise skipped.",
    )
    p.add_argument(
        "--current-only",
        action="store_true",
        help="Only scrape/write in_progress seasons (nightly path).",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
