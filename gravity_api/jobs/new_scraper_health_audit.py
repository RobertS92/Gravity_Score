"""Run newly implemented scrapers and produce field-level health report."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)

import asyncpg

from gravity_api.scraper_registry import registry_by_key
from gravity_api.scrapers.orchestrator import run_scrapers_for_athlete

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Scrapers added or substantially wired in the recent implementation sprint.
NEW_SCRAPERS_BY_SPORT: dict[str, list[str]] = {
    "cfb": [
        "cfbd_api_stats_cfb",
        "recruiting_247_cfb",
        "opendorse_profile_cfb",
        "sports_ref_honors_cfb",
        "news_rss_on3",
        "social_growth_delta",
    ],
    "nfl": [
        "spotrac_contract_nfl",
        "forbes_earnings_nfl",
        "fantasy_adp_nfl",
        "sports_ref_honors_nfl",
        "news_rss_on3",
        "social_growth_delta",
    ],
    "nba": [
        "spotrac_contract_nba",
        "forbes_earnings_nba",
        "college_experience_pro_nba",
        "sports_ref_honors_nba",
        "news_rss_on3",
        "social_growth_delta",
    ],
    "wnba": [
        "spotrac_contract_wnba",
        "forbes_earnings_wnba",
        "sports_ref_honors_wnba",
        "news_rss_on3",
        "social_growth_delta",
    ],
    "ncaab_mens": [
        "kenpom_ncaab_mens",
        "recruiting_247_ncaab_mens",
        "opendorse_profile_ncaab_mens",
        "sports_ref_honors_ncaab_mens",
        "news_rss_on3",
        "social_growth_delta",
    ],
    "ncaab_womens": [
        "her_hoop_stats_ncaab_womens",
        "recruiting_247_ncaab_womens",
        "opendorse_profile_ncaab_womens",
        "sports_ref_honors_ncaab_womens",
        "news_rss_on3",
        "social_growth_delta",
    ],
    "ncaa_baseball": [
        "perfect_game_recruiting_baseball",
        "d1baseball_rankings_baseball",
        "mlb_draft_pipeline_baseball",
        "recruiting_247_ncaa_baseball",
        "opendorse_profile_ncaa_baseball",
        "sports_ref_honors_ncaa_baseball",
        "news_rss_on3",
        "social_growth_delta",
    ],
    "ncaa_volleyball": [
        "avca_poll_volleyball",
        "prepvolleyball_recruiting_volleyball",
        "avca_all_american_volleyball",
        "recruiting_247_ncaa_volleyball",
        "opendorse_profile_ncaa_volleyball",
        "sports_ref_honors_ncaa_volleyball",
        "news_rss_on3",
        "social_growth_delta",
    ],
}

DEFAULT_SPORTS = tuple(NEW_SCRAPERS_BY_SPORT.keys())


@dataclass
class ScraperAgg:
    runs: int = 0
    success: int = 0
    partial: int = 0
    failed: int = 0
    skipped: int = 0
    confidence_sum: float = 0.0
    errors: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    durations_ms: list[float] = field(default_factory=list)


@dataclass
class FieldAgg:
    attempts: int = 0
    filled: int = 0
    failed: int = 0


class AuditCollector:
    def __init__(self) -> None:
        self.registry = registry_by_key()
        self.scraper: dict[str, ScraperAgg] = defaultdict(ScraperAgg)
        self.field: dict[str, FieldAgg] = defaultdict(FieldAgg)
        self.field_by_scraper: dict[tuple[str, str], FieldAgg] = defaultdict(FieldAgg)
        self.athletes_processed = 0
        self.athletes_failed = 0
        self.started_at = datetime.now(timezone.utc).isoformat()
        self._lock = asyncio.Lock()

    async def record_async(self, scraper_key: str, result: dict[str, Any]) -> None:
        async with self._lock:
            self.record(scraper_key, result)

    async def inc_processed(self) -> None:
        async with self._lock:
            self.athletes_processed += 1

    async def inc_failed(self) -> None:
        async with self._lock:
            self.athletes_failed += 1

    def record(self, scraper_key: str, result: dict[str, Any]) -> None:
        agg = self.scraper[scraper_key]
        agg.runs += 1
        status = str(result.get("status") or "failed")
        if status == "success":
            agg.success += 1
        elif status == "partial":
            agg.partial += 1
        elif status == "skipped":
            agg.skipped += 1
        else:
            agg.failed += 1
        agg.confidence_sum += float(result.get("confidence") or 0.0)
        err = result.get("error_message") or result.get("error")
        if err:
            key = str(err)[:120]
            agg.errors[key] += 1

        expected = self.registry.get(scraper_key)
        feature_keys = tuple(expected.feature_keys) if expected else tuple()
        written = set(result.get("fields_written") or [])
        failed_fields = set(result.get("fields_failed") or [])
        fields = result.get("fields") or {}

        keys_to_score = feature_keys or tuple(fields.keys())
        for fk in keys_to_score:
            fa = self.field[fk]
            fas = self.field_by_scraper[(scraper_key, fk)]
            fa.attempts += 1
            fas.attempts += 1
            val = fields.get(fk)
            if fk in written and val is not None and val != "" and val != {} and val != []:
                fa.filled += 1
                fas.filled += 1
            elif fk in failed_fields:
                fa.failed += 1
                fas.failed += 1

    def to_report(self, *, sports: list[str], limit_per_sport: int | None) -> dict[str, Any]:
        scraper_rows = []
        for key, agg in sorted(self.scraper.items()):
            runs = max(agg.runs, 1)
            scraper_rows.append(
                {
                    "scraper_key": key,
                    "runs": agg.runs,
                    "success_rate_pct": round(100 * agg.success / runs, 1),
                    "partial_rate_pct": round(100 * agg.partial / runs, 1),
                    "failed_rate_pct": round(100 * agg.failed / runs, 1),
                    "skipped_rate_pct": round(100 * agg.skipped / runs, 1),
                    "avg_confidence": round(agg.confidence_sum / runs, 3),
                    "top_error": max(agg.errors.items(), key=lambda x: x[1])[0] if agg.errors else None,
                    "top_error_count": max(agg.errors.values()) if agg.errors else 0,
                }
            )

        field_rows = []
        for fk, fa in sorted(self.field.items()):
            attempts = max(fa.attempts, 1)
            fill_rate = 100 * fa.filled / attempts
            field_rows.append(
                {
                    "field": fk,
                    "attempts": fa.attempts,
                    "filled": fa.filled,
                    "failed": fa.failed,
                    "missing": fa.attempts - fa.filled - fa.failed,
                    "fill_rate_pct": round(fill_rate, 1),
                    "failure_rate_pct": round(100 * fa.failed / attempts, 1),
                }
            )

        field_scraper_rows = []
        for (sk, fk), fa in sorted(self.field_by_scraper.items()):
            attempts = max(fa.attempts, 1)
            field_scraper_rows.append(
                {
                    "scraper_key": sk,
                    "field": fk,
                    "attempts": fa.attempts,
                    "filled": fa.filled,
                    "fill_rate_pct": round(100 * fa.filled / attempts, 1),
                    "failure_rate_pct": round(100 * fa.failed / attempts, 1),
                }
            )

        total_runs = sum(a.runs for a in self.scraper.values())
        return {
            "meta": {
                "started_at": self.started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "sports": sports,
                "limit_per_sport": limit_per_sport,
                "athletes_processed": self.athletes_processed,
                "athletes_failed": self.athletes_failed,
                "total_scraper_runs": total_runs,
            },
            "scraper_health": scraper_rows,
            "field_fill_rates": field_rows,
            "field_by_scraper": field_scraper_rows,
        }


def _markdown_report(report: dict[str, Any]) -> str:
    meta = report["meta"]
    lines = [
        "# New Scraper Health Report",
        "",
        f"- **Athletes processed:** {meta['athletes_processed']:,}",
        f"- **Athlete-level failures:** {meta['athletes_failed']:,}",
        f"- **Total scraper runs:** {meta['total_scraper_runs']:,}",
        f"- **Finished:** {meta['finished_at']}",
        "",
        "## Scraper health",
        "",
        "| Scraper | Runs | Success % | Partial % | Failed % | Skipped % | Avg conf | Top error |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["scraper_health"]:
        err = (row.get("top_error") or "")[:60].replace("|", "/")
        lines.append(
            f"| {row['scraper_key']} | {row['runs']} | {row['success_rate_pct']} | "
            f"{row['partial_rate_pct']} | {row['failed_rate_pct']} | {row['skipped_rate_pct']} | "
            f"{row['avg_confidence']} | {err} |"
        )
    lines.extend(
        [
            "",
            "## Field fill rates (all scrapers)",
            "",
            "| Field | Attempts | Filled | Missing | Failed | Fill % | Fail % |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in sorted(report["field_fill_rates"], key=lambda r: r["fill_rate_pct"]):
        lines.append(
            f"| {row['field']} | {row['attempts']} | {row['filled']} | {row['missing']} | "
            f"{row['failed']} | {row['fill_rate_pct']} | {row['failure_rate_pct']} |"
        )
    lines.extend(
        [
            "",
            "## Field fill by scraper (fill rate < 50%)",
            "",
            "| Scraper | Field | Attempts | Filled | Fill % |",
            "|---|---|---:|---:|---:|",
        ]
    )
    low = [r for r in report["field_by_scraper"] if r["fill_rate_pct"] < 50]
    for row in sorted(low, key=lambda r: (r["fill_rate_pct"], r["scraper_key"])):
        lines.append(
            f"| {row['scraper_key']} | {row['field']} | {row['attempts']} | "
            f"{row['filled']} | {row['fill_rate_pct']} |"
        )
    return "\n".join(lines) + "\n"




def _write_reports(output_dir: Path, report: dict[str, Any], stem: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2))
    md_path.write_text(_markdown_report(report))
    return json_path, md_path


async def write_checkpoint(
    collector: AuditCollector,
    *,
    output_dir: Path,
    sports: list[str],
    limit_per_sport: int | None,
) -> None:
    async with collector._lock:
        report = collector.to_report(sports=sports, limit_per_sport=limit_per_sport)
        report["meta"]["checkpoint"] = True
    _write_reports(output_dir, report, "new_scraper_health_checkpoint")
    logger.info(
        "Checkpoint: %d athletes processed, %d athlete failures",
        report["meta"]["athletes_processed"],
        report["meta"]["athletes_failed"],
    )


async def fetch_athlete_ids(
    conn: asyncpg.Connection,
    sport: str,
    *,
    limit: int | None,
    resume_within_hours: int | None = None,
) -> list[str]:
    if resume_within_hours:
        sql = """SELECT a.id FROM athletes a
                 WHERE a.sport = $1 AND COALESCE(a.is_active, TRUE)
                   AND NOT EXISTS (
                     SELECT 1 FROM raw_athlete_data r
                     WHERE r.athlete_id = a.id
                       AND r.scrape_version = 'gravity_api_scrapers_v1'
                       AND r.scraped_at > NOW() - ($2::int * INTERVAL '1 hour')
                   )
                 ORDER BY a.updated_at DESC NULLS LAST"""
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = await conn.fetch(sql, sport, int(resume_within_hours))
    else:
        sql = """SELECT id FROM athletes
                 WHERE sport = $1 AND COALESCE(is_active, TRUE)
                 ORDER BY updated_at DESC NULLS LAST"""
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = await conn.fetch(sql, sport)
    return [str(r["id"]) for r in rows]


async def audit_sport(
    pool: asyncpg.Pool,
    sport: str,
    collector: AuditCollector,
    *,
    limit: int | None,
    concurrency: int,
    resume_within_hours: int | None,
    checkpoint_every: int | None,
    output_dir: Path,
    sports_for_report: list[str],
) -> None:
    keys = NEW_SCRAPERS_BY_SPORT.get(sport, [])
    if not keys:
        return
    async with pool.acquire() as conn:
        ids = await fetch_athlete_ids(
            conn, sport, limit=limit, resume_within_hours=resume_within_hours
        )
    if not ids:
        logger.info("[%s] no athletes", sport)
        return
    logger.info("[%s] auditing %d athletes with %d scrapers", sport, len(ids), len(keys))
    sem = asyncio.Semaphore(concurrency)

    async def one(athlete_id: str) -> None:
        async with sem:
            async with pool.acquire() as conn:
                try:
                    out = await run_scrapers_for_athlete(
                        conn,
                        athlete_id,
                        scraper_keys=keys,
                        persist=True,
                        score_after=False,
                    )
                    for r in out.get("results") or []:
                        await collector.record_async(r["scraper_key"], r)
                    await collector.inc_processed()
                except Exception as exc:
                    await collector.inc_failed()
                    logger.warning("[%s] athlete %s failed: %s", sport, athlete_id, exc)

    checkpoint_mark = 0
    for i in range(0, len(ids), concurrency * 5):
        batch = ids[i : i + concurrency * 5]
        await asyncio.gather(*[one(aid) for aid in batch])
        logger.info("[%s] progress %d/%d athletes", sport, min(i + len(batch), len(ids)), len(ids))
        if checkpoint_every:
            async with collector._lock:
                processed = collector.athletes_processed
            if processed - checkpoint_mark >= checkpoint_every:
                await write_checkpoint(
                    collector,
                    output_dir=output_dir,
                    sports=sports_for_report,
                    limit_per_sport=limit,
                )
                checkpoint_mark = processed


async def run_audit(
    *,
    sports: tuple[str, ...],
    limit_per_sport: int | None,
    concurrency: int,
    sport_parallel: int,
    output_dir: Path,
    resume_within_hours: int | None,
    checkpoint_every: int | None,
) -> dict[str, Any]:
    dsn = os.environ.get("PG_DSN", "").strip()
    if not dsn:
        raise RuntimeError("PG_DSN required")

    collector = AuditCollector()
    output_dir.mkdir(parents=True, exist_ok=True)
    sports_list = list(sports)

    pool = await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=max(concurrency * sport_parallel, concurrency) + 2,
        command_timeout=180,
    )
    try:
        if sport_parallel <= 1:
            for sport in sports:
                await audit_sport(
                    pool,
                    sport,
                    collector,
                    limit=limit_per_sport,
                    concurrency=concurrency,
                    resume_within_hours=resume_within_hours,
                    checkpoint_every=checkpoint_every,
                    output_dir=output_dir,
                    sports_for_report=sports_list,
                )
        else:
            sem = asyncio.Semaphore(sport_parallel)

            async def sport_task(sport: str) -> None:
                async with sem:
                    await audit_sport(
                        pool,
                        sport,
                        collector,
                        limit=limit_per_sport,
                        concurrency=concurrency,
                        resume_within_hours=resume_within_hours,
                        checkpoint_every=checkpoint_every,
                        output_dir=output_dir,
                        sports_for_report=sports_list,
                    )

            await asyncio.gather(*[sport_task(sp) for sp in sports])
    finally:
        await pool.close()

    report = collector.to_report(sports=sports_list, limit_per_sport=limit_per_sport)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    _, md_path = _write_reports(output_dir, report, f"new_scraper_health_{stamp}")
    logger.info("Wrote report %s", md_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit new scrapers and emit health report")
    parser.add_argument("--sports", default=",".join(DEFAULT_SPORTS))
    parser.add_argument("--limit-per-sport", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=int(os.environ.get("SCRAPE_CONCURRENCY", "2")))
    parser.add_argument("--sport-parallel", type=int, default=1)
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent.parent.parent / "reports"),
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=100,
        help="Write reports/new_scraper_health_checkpoint.* every N athletes (0 to disable)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip athletes scraped by gravity_api_scrapers_v1 within --resume-within-hours",
    )
    parser.add_argument(
        "--resume-within-hours",
        type=int,
        default=24,
        help="With --resume, skip athletes scraped within this many hours",
    )
    args = parser.parse_args()
    sports = tuple(s.strip() for s in args.sports.split(",") if s.strip())
    t0 = time.time()
    report = asyncio.run(
        run_audit(
            sports=sports,
            limit_per_sport=args.limit_per_sport,
            concurrency=args.concurrency,
            sport_parallel=args.sport_parallel,
            output_dir=Path(args.output_dir),
            resume_within_hours=args.resume_within_hours if args.resume else None,
            checkpoint_every=args.checkpoint_every or None,
        )
    )
    elapsed = time.time() - t0
    print(json.dumps({"elapsed_s": round(elapsed), "meta": report["meta"]}, indent=2))


if __name__ == "__main__":
    main()
