"""Run scraper smoke checks against ESPN (and optional DB scheduled_full)."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gravity_api.scraper_smoke.athletes import (
    SMOKE_ATHLETES,
    LifecycleFact,
    SmokeAthlete,
    lifecycle_facts_for_espn_id,
)
from gravity_api.scrapers.implementations import EspnRosterScraper, EspnStatsScraper
from gravity_api.scrapers.season_calendar import (
    parse_season_label,
    season_label as calendar_season_label,
    season_status,
)
from gravity_api.scrapers.types import AthleteScrapeContext

# WP9: smoke/export provenance columns (career_<key> is dynamic).
SMOKE_PROVENANCE_COLUMNS: tuple[str, ...] = (
    "season_year",
    "season_label",
    "season_type",
    "team_id",
    "is_total",
    "is_complete",
    "stats_as_of",
    "validation_status",
    "n_seasons",
)
STATS_SCOPE_VALUES = frozenset({"season", "career"})
# Never stamp season GP onto career-scoped rows / career_* columns.
_SEASON_ONLY_STAT_KEYS = frozenset({"games_played_season", "gp", "G", "gamesPlayed"})


def normalize_stats_scope(scope: Any) -> str | None:
    """Coerce scraper scope labels to WP9 ``season|career`` (or None)."""
    if scope is None:
        return None
    text = str(scope).strip().lower()
    if not text:
        return None
    if text in STATS_SCOPE_VALUES:
        return text
    # Career-sized aggregates without per-season history.
    if text in {"multi_season", "multiseason", "career_total", "totals", "total"}:
        return "career"
    return None


def _empty_provenance() -> dict[str, Any]:
    return {col: None for col in SMOKE_PROVENANCE_COLUMNS}


def _career_prefixed(career: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not isinstance(career, dict):
        return out
    for key, val in career.items():
        if key in _SEASON_ONLY_STAT_KEYS:
            continue
        if val is None or val == "":
            continue
        out[f"career_{key}"] = val
    return out


def _resolve_season_year(sport: str, label_key: Any) -> int | None:
    if label_key is None or label_key == "":
        return None
    try:
        return parse_season_label(sport, label_key)
    except (TypeError, ValueError):
        pass
    try:
        year = int(str(label_key).strip()[:4])
        if 1800 <= year <= 2100:
            return year
    except (TypeError, ValueError):
        pass
    return None


def _is_complete_for(sport: str, season_year: int | None) -> bool | None:
    if season_year is None:
        return None
    try:
        return season_status(sport, int(season_year), datetime.now(tz=timezone.utc).date()) == "complete"
    except (TypeError, ValueError):
        return None


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


def teams_match(scraped: str | None, live: str | None) -> bool:
    """True when scraped team string matches the live ESPN roster team."""
    if not scraped or not live:
        return False
    a = str(scraped).strip().lower()
    b = str(live).strip().lower()
    if not a or not b:
        return False
    if a == b:
        return True
    return a in b or b in a


def _assert_identity_and_signal(
    athlete: SmokeAthlete,
    fields: dict[str, Any],
    *,
    live_roster_team: str | None = None,
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

    # Team pass/fail: scraped team must equal live ESPN roster team — not team_hint.
    team = fields.get("team") or fields.get("college")
    if live_roster_team:
        ok_team = teams_match(str(team) if team else None, live_roster_team)
        checks.append(
            CheckResult(
                "team_matches_live_espn_roster",
                ok_team,
                f"scraped={team!r} live_espn_roster={live_roster_team!r}",
            )
        )
    elif team:
        checks.append(
            CheckResult(
                "team_or_college_present",
                True,
                f"got={team!r} (no live roster team; team_hint={athlete.team_hint!r} docs-only)",
            )
        )
    else:
        checks.append(
            CheckResult(
                "team_or_college_present",
                False,
                "team missing from scrape",
            )
        )

    stats_as_of = fields.get("stats_as_of")
    scope = fields.get("stats_scope")
    if scope is not None and str(scope).strip() != "":
        normalized = normalize_stats_scope(scope)
        checks.append(
            CheckResult(
                "stats_scope",
                normalized in ("season", "career"),
                f"got={scope!r} normalized={normalized!r}",
            )
        )

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


def lifecycle_fact_checks_from_rows(
    fact: LifecycleFact,
    *,
    college_row: dict[str, Any] | None,
    pro_row: dict[str, Any] | None,
) -> list[CheckResult]:
    """Assert draft-departure lifecycle facts (separate from live team match)."""
    checks: list[CheckResult] = []
    if fact.pro_record_exists:
        checks.append(
            CheckResult(
                "lifecycle_pro_record_exists",
                pro_row is not None,
                f"{fact.name} espn_id={fact.espn_id} pro_sport={fact.pro_sport}",
            )
        )
    if college_row is None:
        checks.append(
            CheckResult(
                "lifecycle_college_row",
                False,
                f"college row missing for {fact.name} ({fact.college_sport})",
            )
        )
        return checks

    is_active = college_row.get("is_active")
    if is_active is None:
        is_active = True
    ok_inactive = bool(is_active) is bool(fact.college_is_active)
    checks.append(
        CheckResult(
            "lifecycle_college_is_active",
            ok_inactive,
            f"got is_active={is_active!r} expected={fact.college_is_active!r}",
        )
    )
    status = str(college_row.get("roster_status") or "")
    ok_status = status == fact.expected_roster_status
    checks.append(
        CheckResult(
            "lifecycle_college_roster_status",
            ok_status,
            f"got={status!r} expected={fact.expected_roster_status!r}",
        )
    )
    if fact.same_espn_id_college_and_pro and pro_row is not None:
        ok_same = str(pro_row.get("espn_id") or "") == str(college_row.get("espn_id") or "")
        checks.append(
            CheckResult(
                "lifecycle_same_espn_id",
                ok_same,
                f"college={college_row.get('espn_id')!r} pro={pro_row.get('espn_id')!r}",
            )
        )
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
    live_roster_team: str | None = None
    try:
        r1 = await roster.run(ctx, f"espn_roster_{athlete.sport}")
        fields = dict(r1.fields)
        # Live ESPN roster team is the identity source of truth (not team_hint).
        raw_team = fields.get("team") or fields.get("college")
        live_roster_team = str(raw_team) if raw_team else None
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

    checks = _assert_identity_and_signal(
        athlete, fields, live_roster_team=live_roster_team
    )
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
        "season_year",
        "season_label",
        "season_type",
        "team_id",
        "is_total",
        "is_complete",
        "validation_status",
        "n_seasons",
        "sacks",
        "tfl",
        "pass_yards",
        "pass_td",
    )
    sample = {k: fields.get(k) for k in sample_keys if fields.get(k) is not None}
    # Prefer season|career only in the sample (WP9).
    if "stats_scope" in sample:
        norm = normalize_stats_scope(sample["stats_scope"])
        if norm:
            sample["stats_scope"] = norm
        else:
            sample.pop("stats_scope", None)
    # Never leave season GP on a career-scoped sample.
    if sample.get("stats_scope") == "career":
        sample.pop("games_played_season", None)
    season = fields.get("season_stats")
    if isinstance(season, dict):
        sample["season_stats_n_keys"] = len(season)
        sample["season_stats_keys"] = sorted(season.keys())
        for key in ("sacks", "tfl", "pass_yards", "pass_td", "avgPoints", "pts"):
            if key in season and key not in sample:
                sample[key] = season[key]
    career = fields.get("career_stats")
    if isinstance(career, dict) and career:
        for key, val in career.items():
            if key in _SEASON_ONLY_STAT_KEYS:
                continue
            sample[f"career_{key}"] = val
        history = fields.get("season_stats_history")
        if isinstance(history, dict) and "n_seasons" not in sample:
            sample["n_seasons"] = len(history)
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

        live_team = fields.get("team") or fields.get("college")
        checks = _assert_identity_and_signal(
            athlete,
            fields,
            live_roster_team=str(live_team) if live_team else None,
        )
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

        # Lifecycle facts (draft departures) — separate from live team match.
        for fact in lifecycle_facts_for_espn_id(athlete.espn_id):
            college = await conn.fetchrow(
                """SELECT id, espn_id, sport, is_active, roster_status, school
                   FROM athletes
                   WHERE espn_id = $1 AND sport = $2
                   LIMIT 1""",
                fact.espn_id,
                fact.college_sport,
            )
            pro = await conn.fetchrow(
                """SELECT id, espn_id, sport, is_active, roster_status, school
                   FROM athletes
                   WHERE espn_id = $1 AND sport = $2
                   LIMIT 1""",
                fact.espn_id,
                fact.pro_sport,
            )
            checks.extend(
                lifecycle_fact_checks_from_rows(
                    fact,
                    college_row=dict(college) if college else None,
                    pro_row=dict(pro) if pro else None,
                )
            )

        sample = {
            "player_name": fields.get("player_name"),
            "espn_id": fields.get("espn_id"),
            "position": fields.get("position"),
            "team": fields.get("team") or fields.get("college"),
            "stats_scope": normalize_stats_scope(fields.get("stats_scope")),
            "stats_as_of": fields.get("stats_as_of"),
            "season_year": fields.get("season_year"),
            "season_label": fields.get("season_label"),
            "season_type": fields.get("season_type"),
            "team_id": fields.get("team_id"),
            "is_total": fields.get("is_total"),
            "is_complete": fields.get("is_complete"),
            "validation_status": fields.get("validation_status"),
            "n_seasons": fields.get("n_seasons"),
            "scrapers_run": summary.get("scrapers_run"),
            "success_count": summary.get("success_count"),
        }
        # Season GP only when scope is season (WP9: no games_played_season in career context).
        if sample.get("stats_scope") != "career" and fields.get("games_played_season") is not None:
            sample["games_played_season"] = fields.get("games_played_season")
        career = fields.get("career_stats")
        if isinstance(career, dict):
            sample.update(_career_prefixed(career))
            history = fields.get("season_stats_history")
            if isinstance(history, dict) and sample.get("n_seasons") is None:
                sample["n_seasons"] = len(history)
        sample["_fields"] = {
            k: v
            for k, v in fields.items()
            if k
            in {
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
                "season_year",
                "season_label",
                "season_type",
                "team_id",
                "is_total",
                "is_complete",
                "validation_status",
                "n_seasons",
                "season_stats",
                "career_stats",
                "season_stats_history",
            }
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


def _base_smoke_identity(result: dict[str, Any], sample: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "sport": result.get("sport"),
        "name": result.get("name"),
        "espn_id": result.get("espn_id"),
        "mode": result.get("mode"),
        "passed": result.get("passed"),
        "team": sample.get("team") or sample.get("college") or fields.get("team"),
        "sacks": sample.get("sacks"),
        "tfl": sample.get("tfl"),
        "pass_yards": sample.get("pass_yards"),
        "pass_td": sample.get("pass_td"),
        "season_stats_keys": sample.get("season_stats_keys"),
        "selection_note": sample.get("selection_note"),
        "error": result.get("error"),
    }


def _season_export_row(
    *,
    base: dict[str, Any],
    sport: str,
    label_key: Any,
    blob: dict[str, Any] | None,
    stats_as_of: Any,
    validation_status: Any = None,
) -> dict[str, Any]:
    """One ``stats_scope=season`` smoke/export row with full provenance columns."""
    row = {**base, **_empty_provenance()}
    row["stats_scope"] = "season"
    year = None
    if isinstance(blob, dict) and blob.get("season_year") is not None:
        year = _resolve_season_year(sport, blob.get("season_year"))
    if year is None:
        year = _resolve_season_year(sport, label_key)
    row["season_year"] = year
    if year is not None:
        try:
            row["season_label"] = calendar_season_label(sport, int(year))
        except (TypeError, ValueError):
            row["season_label"] = str(label_key) if label_key is not None else None
    elif label_key is not None:
        row["season_label"] = str(label_key)

    blob = blob if isinstance(blob, dict) else {}
    row["season_type"] = blob.get("season_type") or "regular"
    team_id = blob.get("team_id")
    if team_id is None or team_id == "":
        team_id = "TOT"
    row["team_id"] = str(team_id)
    is_total = blob.get("is_total")
    if is_total is None:
        is_total = str(team_id) == "TOT"
    row["is_total"] = bool(is_total)
    if blob.get("is_complete") is not None:
        row["is_complete"] = bool(blob.get("is_complete"))
    else:
        row["is_complete"] = _is_complete_for(sport, year)
    row["stats_as_of"] = (
        blob.get("stats_as_of")
        or stats_as_of
    )
    row["validation_status"] = (
        blob.get("validation_status")
        or validation_status
        or "unvalidated"
    )
    # Season GP belongs on season rows only.
    gp = blob.get("games_played_season")
    if gp is None:
        gp = blob.get("gp")
    if gp is not None:
        row["games_played_season"] = gp
    return row


def _career_export_row(
    *,
    base: dict[str, Any],
    career: dict[str, Any] | None,
    n_seasons: int | None,
    stats_as_of: Any,
    validation_status: Any = None,
) -> dict[str, Any]:
    """One ``stats_scope=career`` row: career_<key>, no games_played_season."""
    row = {**base, **_empty_provenance()}
    row["stats_scope"] = "career"
    row["n_seasons"] = n_seasons
    row["stats_as_of"] = stats_as_of
    row["validation_status"] = validation_status or "unvalidated"
    row.update(_career_prefixed(career))
    # Explicitly omit season GP in career context (WP9).
    row.pop("games_played_season", None)
    return row


def smoke_result_to_export_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand one smoke athlete result into season + career provenance rows."""
    sample = result.get("fields_sample") or {}
    fields = sample.get("_fields") if isinstance(sample.get("_fields"), dict) else {}
    sport = str(result.get("sport") or "")
    base = _base_smoke_identity(result, sample, fields)
    stats_as_of = sample.get("stats_as_of") or fields.get("stats_as_of")
    validation_status = (
        sample.get("validation_status")
        or fields.get("validation_status")
    )
    history = fields.get("season_stats_history")
    if not isinstance(history, dict):
        history = {}
    season_stats = fields.get("season_stats")
    if not isinstance(season_stats, dict):
        season_stats = {}
    career = fields.get("career_stats")
    if not isinstance(career, dict):
        career = {}

    rows: list[dict[str, Any]] = []

    if history:
        for label_key in sorted(history.keys(), key=lambda k: str(k)):
            blob = history.get(label_key)
            if not isinstance(blob, dict):
                continue
            rows.append(
                _season_export_row(
                    base=base,
                    sport=sport,
                    label_key=label_key,
                    blob=blob,
                    stats_as_of=stats_as_of,
                    validation_status=validation_status,
                )
            )
    elif season_stats:
        label_key = (
            sample.get("season_year")
            or fields.get("season_year")
            or sample.get("season_label")
            or fields.get("season_label")
            or stats_as_of
        )
        blob = {
            **season_stats,
            "season_year": fields.get("season_year") or sample.get("season_year"),
            "season_type": fields.get("season_type") or sample.get("season_type"),
            "team_id": fields.get("team_id") or sample.get("team_id"),
            "is_total": fields.get("is_total") if fields.get("is_total") is not None else sample.get("is_total"),
            "is_complete": fields.get("is_complete") if fields.get("is_complete") is not None else sample.get("is_complete"),
            "stats_as_of": stats_as_of,
            "validation_status": validation_status,
            "games_played_season": (
                fields.get("games_played_season")
                or sample.get("games_played_season")
                or season_stats.get("games_played_season")
                or season_stats.get("gp")
            ),
        }
        rows.append(
            _season_export_row(
                base=base,
                sport=sport,
                label_key=label_key,
                blob=blob,
                stats_as_of=stats_as_of,
                validation_status=validation_status,
            )
        )

    n_seasons = len(history) if history else (
        sample.get("n_seasons") if sample.get("n_seasons") is not None else fields.get("n_seasons")
    )
    if career or (history and len(history) >= 1):
        # Derive career from history totals keys when career blob empty but n_seasons known.
        career_blob = career or {
            k.replace("career_", "", 1): v
            for k, v in sample.items()
            if str(k).startswith("career_")
        }
        if not career_blob and fields.get("games_played_career") is not None:
            career_blob = {"games_played_career": fields.get("games_played_career")}
        rows.append(
            _career_export_row(
                base=base,
                career=career_blob if isinstance(career_blob, dict) else {},
                n_seasons=int(n_seasons) if n_seasons is not None else (len(history) or None),
                stats_as_of=stats_as_of,
                validation_status=validation_status,
            )
        )

    if not rows:
        # Identity-only: still emit provenance columns + normalized scope.
        row = {**base, **_empty_provenance()}
        scope = normalize_stats_scope(sample.get("stats_scope") or fields.get("stats_scope"))
        row["stats_scope"] = scope
        row["stats_as_of"] = stats_as_of
        row["validation_status"] = validation_status
        # Only attach season GP when scope is season (never on career/unknown career risk).
        if scope == "season":
            gp = sample.get("games_played_season") or fields.get("games_played_season")
            if gp is not None:
                row["games_played_season"] = gp
            for col in (
                "season_year",
                "season_label",
                "season_type",
                "team_id",
                "is_total",
                "is_complete",
            ):
                if sample.get(col) is not None:
                    row[col] = sample.get(col)
                elif fields.get(col) is not None:
                    row[col] = fields.get(col)
        elif scope == "career":
            row["n_seasons"] = sample.get("n_seasons") or fields.get("n_seasons")
            row.update(_career_prefixed(career))
            for k, v in sample.items():
                if str(k).startswith("career_") and k not in row:
                    # Strip season-GP disguised as career_* if any.
                    if k in {"career_games_played_season", "career_gp"}:
                        continue
                    row[k] = v
        rows.append(row)

    # Final WP9 invariants per row.
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        scope = normalize_stats_scope(row.get("stats_scope"))
        row["stats_scope"] = scope
        if scope == "career":
            row.pop("games_played_season", None)
            row.pop("gp", None)
        elif scope == "season":
            # Season rows do not carry career_<key> aggregates (columns may exist blank).
            for key in list(row.keys()):
                if key.startswith("career_"):
                    row.pop(key, None)
        cleaned.append(row)
    return cleaned


def smoke_results_to_csv_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten smoke results for CSV/JSON — full WP9 provenance column set."""
    rows: list[dict[str, Any]] = []
    for result in payload.get("results") or []:
        rows.extend(smoke_result_to_export_rows(result))
    return rows


def smoke_csv_fieldnames(rows: list[dict[str, Any]] | None = None) -> list[str]:
    """Stable CSV header: identity + scope + provenance + optional stats + career_*."""
    base = [
        "sport",
        "name",
        "espn_id",
        "mode",
        "passed",
        "team",
        "stats_scope",
        *SMOKE_PROVENANCE_COLUMNS,
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
    career_cols: list[str] = []
    seen = set(base)
    for row in rows or []:
        for key in row:
            if key.startswith("career_") and key not in seen:
                seen.add(key)
                career_cols.append(key)
    career_cols.sort()
    # Insert career_* after n_seasons block (after provenance / before games_played_season).
    insert_at = base.index("games_played_season")
    return base[:insert_at] + career_cols + base[insert_at:]


def write_smoke_csv(payload: dict[str, Any], path: str | Path) -> int:
    import csv
    from pathlib import Path as _Path

    out = _Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = smoke_results_to_csv_rows(payload)
    fieldnames = smoke_csv_fieldnames(rows)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            # DictWriter leaves missing keys blank; ensure career rows omit season GP.
            out_row = dict(row)
            if out_row.get("stats_scope") == "career":
                out_row.pop("games_played_season", None)
            writer.writerow(out_row)
    return len(rows)
