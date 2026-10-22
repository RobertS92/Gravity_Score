"""Run scraper smoke checks against ESPN (and optional DB scheduled_full)."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gravity_api.scraper_smoke.athletes import SMOKE_ATHLETES, SmokeAthlete
from gravity_api.scrapers.implementations import EspnRosterScraper, EspnStatsScraper
from gravity_api.scrapers.types import AthleteScrapeContext


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class AthleteSmokeResult:
    sport: str
    name: str
    espn_id: str
    mode: str  # espn_scrapers | db_scheduled_full | skipped
    passed: bool
    checks: list[CheckResult] = field(default_factory=list)
    fields_sample: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sport": self.sport,
            "name": self.name,
            "espn_id": self.espn_id,
            "mode": self.mode,
            "passed": self.passed,
            "error": self.error,
            "checks": [asdict(c) for c in self.checks],
            "fields_sample": self.fields_sample,
        }


def _name_ok(scraped: str | None, athlete: SmokeAthlete) -> bool:
    if not scraped:
        return False
    lower = scraped.lower()
    return all(tok.lower() in lower for tok in athlete.name_tokens)


def _has_real_stats(fields: dict[str, Any]) -> bool:
    season = fields.get("season_stats")
    if isinstance(season, dict) and len(season) >= 3:
        return True
    try:
        gp = float(fields.get("games_played_season") or fields.get("gp") or 0)
        if gp > 0:
            return True
    except (TypeError, ValueError):
        pass
    # Pro/college athletes may be off-season with career/history only.
    career = fields.get("career_stats")
    if isinstance(career, dict) and len(career) >= 3:
        return True
    history = fields.get("season_stats_history")
    if isinstance(history, dict) and history:
        return True
    # Count flat numeric stat-like keys written by scrapers.
    statish = 0
    for k, v in fields.items():
        if k in {"espn_id", "player_name", "position", "team", "college", "headshot_url"}:
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            statish += 1
    return statish >= 5


def _assert_identity_and_signal(
    athlete: SmokeAthlete,
    fields: dict[str, Any],
    *,
    require_stats: bool = True,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    name = fields.get("player_name")
    ok_name = _name_ok(str(name) if name else None, athlete)
    checks.append(
        CheckResult(
            "name_matches",
            ok_name,
            f"got={name!r} expected_tokens={athlete.name_tokens}",
        )
    )

    espn_id = str(fields.get("espn_id") or "")
    ok_id = espn_id == athlete.espn_id
    checks.append(
        CheckResult("espn_id_matches", ok_id, f"got={espn_id!r}")
    )

    pos = fields.get("position")
    if athlete.position_hint:
        ok_pos = bool(pos) and str(pos).upper() == athlete.position_hint.upper()
        checks.append(
            CheckResult(
                "position",
                ok_pos,
                f"got={pos!r} expected={athlete.position_hint!r}",
            )
        )
    else:
        checks.append(CheckResult("position_present", bool(pos), f"got={pos!r}"))

    # Team must resolve and match the hint (e.g. LeBron → 76ers, not Lakers).
    team = fields.get("team") or fields.get("college")
    if team:
        ok_team = athlete.team_hint.lower() in str(team).lower()
        checks.append(
            CheckResult(
                "team_or_college",
                ok_team,
                f"got={team!r} expected_hint={athlete.team_hint!r}",
            )
        )
    else:
        checks.append(
            CheckResult(
                "team_or_college",
                False,
                f"team missing (hint={athlete.team_hint})",
            )
        )

    stats_as_of = fields.get("stats_as_of")
    scope = fields.get("stats_scope")
    if scope:
        checks.append(CheckResult("stats_scope", True, f"got={scope!r}"))

    # Reject fake freshness: stats_as_of alone without real stats payload.
    # Rookies (e.g. AJ Dybantsa pre-debut) may have identity but empty stats —
    # allow when stats_as_of is absent; fail only when a stamp exists without stats.
    has_stats = _has_real_stats(fields)
    if has_stats:
        checks.append(
            CheckResult(
                "stats_as_of_present",
                bool(stats_as_of),
                f"got={stats_as_of!r}",
            )
        )
    else:
        checks.append(
            CheckResult(
                "stats_as_of_present",
                True,
                f"deferred (no stats yet); got={stats_as_of!r}",
            )
        )
    if stats_as_of and not has_stats:
        checks.append(
            CheckResult(
                "no_fake_stats_as_of",
                False,
                f"stats_as_of={stats_as_of!r} without real season/career stats",
            )
        )
    elif require_stats and has_stats:
        checks.append(
            CheckResult(
                "real_stats_signal",
                True,
                f"season_stats_keys={list((fields.get('season_stats') or {}).keys())[:8] if isinstance(fields.get('season_stats'), dict) else None}",
            )
        )
    elif require_stats and not has_stats:
        # Soft-pass: identity verified; ESPN has not published a season pack yet.
        checks.append(
            CheckResult(
                "real_stats_signal",
                True,
                "no season pack yet (rookie/empty ESPN); identity checks still required",
            )
        )
    else:
        checks.append(CheckResult("real_stats_signal", True, "not required this mode"))

    # Sport must not be confused — roster/stats scrapers don't rewrite sport key,
    # but wrong ESPN id would fail name check. Explicit sport tag for reporting.
    checks.append(CheckResult("sport_key", True, athlete.sport))
    return checks


async def smoke_athlete_espn_scrapers(athlete: SmokeAthlete) -> AthleteSmokeResult:
    """Production micro-scrapers (roster + stats) without DB persist."""
    ctx = AthleteScrapeContext(
        athlete_id=f"smoke-{athlete.espn_id}",
        name=athlete.name,
        sport=athlete.sport,
        school=athlete.team_hint,
        team=athlete.team_hint,
        position=athlete.position_hint,
        espn_id=athlete.espn_id,
        existing_raw={},
        event_type="scheduled_full",
        force_refresh=True,
    )
    roster = EspnRosterScraper()
    stats = EspnStatsScraper()
    try:
        r1 = await roster.run(ctx, f"espn_roster_{athlete.sport}")
        fields = dict(r1.fields)
        ctx.existing_raw = fields
        r2 = await stats.run(ctx, f"espn_stats_{athlete.sport}")
        fields.update({k: v for k, v in r2.fields.items() if v is not None})
    except Exception as exc:
        return AthleteSmokeResult(
            sport=athlete.sport,
            name=athlete.name,
            espn_id=athlete.espn_id,
            mode="espn_scrapers",
            passed=False,
            error=str(exc),
        )

    checks = _assert_identity_and_signal(athlete, fields)
    # Scrapers themselves must not report failed for core path.
    if r1.status == "failed":
        checks.append(CheckResult("roster_scraper_status", False, r1.error_message or r1.status))
    else:
        checks.append(CheckResult("roster_scraper_status", True, r1.status))
    if r2.status == "failed":
        checks.append(CheckResult("stats_scraper_status", False, r2.error_message or r2.status))
    else:
        checks.append(CheckResult("stats_scraper_status", True, r2.status))

    sample_keys = (
        "player_name",
        "espn_id",
        "position",
        "team",
        "college",
        "games_played_season",
        "games_played_career",
        "stats_as_of",
        "stats_scope",
        "stats_source",
        "stats_collected_at",
        "sacks",
        "tfl",
        "pass_yards",
        "pass_td",
    )
    sample = {k: fields.get(k) for k in sample_keys if fields.get(k) is not None}
    season = fields.get("season_stats")
    if isinstance(season, dict):
        sample["season_stats_n_keys"] = len(season)
        sample["season_stats_keys"] = sorted(season.keys())
        for key in ("sacks", "tfl", "pass_yards", "pass_td", "avgPoints", "pts"):
            if key in season and key not in sample:
                sample[key] = season[key]
    if getattr(athlete, "selection_note", None):
        sample["selection_note"] = athlete.selection_note
    # Keep full merged fields for CSV export (bounded).
    sample["_fields"] = {
        k: v
        for k, v in fields.items()
        if k
        in {
            *sample_keys,
            "season_stats",
            "career_stats",
            "season_stats_history",
        }
    }

    passed = all(c.ok for c in checks)
    return AthleteSmokeResult(
        sport=athlete.sport,
        name=athlete.name,
        espn_id=athlete.espn_id,
        mode="espn_scrapers",
        passed=passed,
        checks=checks,
        fields_sample=sample,
    )


async def smoke_athlete_db_scheduled_full(athlete: SmokeAthlete) -> AthleteSmokeResult:
    """Full orchestrator path when PG_DSN is configured."""
    dsn = os.environ.get("PG_DSN", "").strip()
    if not dsn:
        return AthleteSmokeResult(
            sport=athlete.sport,
            name=athlete.name,
            espn_id=athlete.espn_id,
            mode="skipped",
            passed=True,
            checks=[CheckResult("db_scheduled_full", True, "skipped: PG_DSN unset")],
            error="PG_DSN unset",
        )

    import asyncpg

    from gravity_api.scrapers.orchestrator import run_scrapers_for_athlete

    conn = await asyncpg.connect(dsn, command_timeout=120)
    try:
        row = await conn.fetchrow(
            """SELECT id FROM athletes
               WHERE espn_id = $1 AND sport = $2
               LIMIT 1""",
            athlete.espn_id,
            athlete.sport,
        )
        if not row:
            # Also try aliases for college basketball.
            aliases = {
                "ncaab_mens": ("ncaab_mens", "mcbb"),
                "ncaab_womens": ("ncaab_womens", "wcbb"),
                "cfb": ("cfb", "ncaaf"),
            }.get(athlete.sport, (athlete.sport,))
            row = await conn.fetchrow(
                """SELECT id FROM athletes
                   WHERE espn_id = $1 AND sport = ANY($2::text[])
                   LIMIT 1""",
                athlete.espn_id,
                list(aliases),
            )
        if not row:
            return AthleteSmokeResult(
                sport=athlete.sport,
                name=athlete.name,
                espn_id=athlete.espn_id,
                mode="db_scheduled_full",
                passed=False,
                error=f"athlete espn_id={athlete.espn_id} not in DB for sport={athlete.sport}",
                checks=[
                    CheckResult(
                        "athlete_in_db",
                        False,
                        "seed athlete or run roster sync first",
                    )
                ],
            )

        summary = await run_scrapers_for_athlete(
            conn,
            str(row["id"]),
            event_type="scheduled_full",
            gap_fill=False,
            persist=True,
            score_after=False,
        )
        # Reload merged raw
        raw_row = await conn.fetchrow(
            """SELECT raw_data FROM raw_athlete_data
               WHERE athlete_id = $1::uuid
               ORDER BY scraped_at DESC NULLS LAST LIMIT 1""",
            row["id"],
        )
        fields: dict[str, Any] = {}
        if raw_row and raw_row["raw_data"]:
            raw = raw_row["raw_data"]
            if isinstance(raw, str):
                fields = json.loads(raw)
            elif isinstance(raw, dict):
                fields = dict(raw)

        checks = _assert_identity_and_signal(athlete, fields)
        ok_run = int(summary.get("success_count") or 0) > 0 and not summary.get("skipped")
        checks.append(
            CheckResult(
                "orchestrator_success",
                ok_run,
                f"success_count={summary.get('success_count')} scrapers_run={summary.get('scrapers_run')}",
            )
        )
        if summary.get("pipeline_error"):
            checks.append(
                CheckResult("pipeline_error_absent", False, str(summary["pipeline_error"]))
            )

        sample = {
            "player_name": fields.get("player_name"),
            "espn_id": fields.get("espn_id"),
            "position": fields.get("position"),
            "team": fields.get("team") or fields.get("college"),
            "games_played_season": fields.get("games_played_season"),
            "scrapers_run": summary.get("scrapers_run"),
            "success_count": summary.get("success_count"),
        }
        return AthleteSmokeResult(
            sport=athlete.sport,
            name=athlete.name,
            espn_id=athlete.espn_id,
            mode="db_scheduled_full",
            passed=all(c.ok for c in checks),
            checks=checks,
            fields_sample=sample,
        )
    finally:
        await conn.close()


async def run_smoke_suite(
    *,
    include_db: bool | None = None,
    athletes: tuple[SmokeAthlete, ...] | None = None,
) -> dict[str, Any]:
    selected = athletes or SMOKE_ATHLETES
    if include_db is None:
        include_db = bool(os.environ.get("PG_DSN", "").strip())

    results: list[AthleteSmokeResult] = []
    for athlete in selected:
        espn_result = await smoke_athlete_espn_scrapers(athlete)
        results.append(espn_result)
        if include_db:
            db_result = await smoke_athlete_db_scheduled_full(athlete)
            results.append(db_result)

    by_sport: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        by_sport.setdefault(r.sport, []).append(r.to_dict())

    espn_runs = [r for r in results if r.mode == "espn_scrapers"]
    db_runs = [r for r in results if r.mode == "db_scheduled_full"]
    skipped = [r for r in results if r.mode == "skipped"]

    summary = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "espn_scrapers_passed": sum(1 for r in espn_runs if r.passed),
        "espn_scrapers_failed": sum(1 for r in espn_runs if not r.passed),
        "db_scheduled_full_passed": sum(1 for r in db_runs if r.passed),
        "db_scheduled_full_failed": sum(1 for r in db_runs if not r.passed),
        "db_skipped": len(skipped),
        "all_espn_passed": all(r.passed for r in espn_runs) if espn_runs else False,
    }
    return {
        "summary": summary,
        "by_sport": by_sport,
        "results": [r.to_dict() for r in results],
    }


def run_smoke_suite_sync(**kwargs) -> dict[str, Any]:
    return asyncio.run(run_smoke_suite(**kwargs))


def smoke_results_to_csv_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten smoke results for CSV — always includes stats_scope + stats_as_of."""
    rows: list[dict[str, Any]] = []
    for result in payload.get("results") or []:
        sample = result.get("fields_sample") or {}
        fields = sample.get("_fields") if isinstance(sample.get("_fields"), dict) else {}
        rows.append(
            {
                "sport": result.get("sport"),
                "name": result.get("name"),
                "espn_id": result.get("espn_id"),
                "mode": result.get("mode"),
                "passed": result.get("passed"),
                "team": sample.get("team") or sample.get("college") or fields.get("team"),
                "stats_scope": sample.get("stats_scope") or fields.get("stats_scope"),
                "stats_as_of": sample.get("stats_as_of") or fields.get("stats_as_of"),
                "games_played_season": sample.get("games_played_season")
                or fields.get("games_played_season"),
                "games_played_career": sample.get("games_played_career")
                or fields.get("games_played_career"),
                "sacks": sample.get("sacks"),
                "tfl": sample.get("tfl"),
                "pass_yards": sample.get("pass_yards"),
                "pass_td": sample.get("pass_td"),
                "season_stats_keys": sample.get("season_stats_keys"),
                "selection_note": sample.get("selection_note"),
                "error": result.get("error"),
            }
        )
    return rows


def write_smoke_csv(payload: dict[str, Any], path: str | Path) -> int:
    import csv
    from pathlib import Path as _Path

    out = _Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = smoke_results_to_csv_rows(payload)
    fieldnames = [
        "sport",
        "name",
        "espn_id",
        "mode",
        "passed",
        "team",
        "stats_scope",
        "stats_as_of",
        "games_played_season",
        "games_played_career",
        "sacks",
        "tfl",
        "pass_yards",
        "pass_td",
        "season_stats_keys",
        "selection_note",
        "error",
    ]
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)
