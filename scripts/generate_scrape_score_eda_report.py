#!/usr/bin/env python3
"""Generate markdown EDA report on scrape coverage, stats/NIL quality, and scoring."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg

ACCEPTANCE_SPORTS = ("cfb", "nfl", "nba", "ncaab_mens", "ncaab_womens", "wnba")
COLLEGE_SPORTS = ("cfb", "ncaab_mens", "ncaab_womens")
REPORT_PATH = ROOT / "reports" / "scrape_score_eda_report.md"
BASELINE_JSON = ROOT / "reports" / "scrape_score_eda_report_baseline.json"


def _pct(num: int | float, den: int | float) -> str:
    if not den:
        return "0.0%"
    return f"{100.0 * num / den:.1f}%"


async def _sport_scrape_stats(conn: asyncpg.Connection, sport: str) -> dict:
    row = await conn.fetchrow(
        """
        WITH r AS (
          SELECT COALESCE(r.raw_data, '{}'::jsonb) raw, r.scraped_at
          FROM athletes a
          LEFT JOIN LATERAL (
            SELECT raw_data, scraped_at FROM raw_athlete_data
            WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
          ) r ON TRUE
          WHERE a.sport = $1 AND COALESCE(a.is_active, TRUE)
        )
        SELECT
          COUNT(*) AS active_n,
          COUNT(*) FILTER (WHERE scraped_at IS NOT NULL) AS scraped,
          COUNT(*) FILTER (
            WHERE COALESCE((raw->>'games_played_season')::float, 0) > 0
               OR COALESCE((raw->'season_stats'->>'gp')::float, 0) > 0
               OR COALESCE((raw->'season_stats'->>'games_played_season')::float, 0) > 0
          ) AS has_gp,
          COUNT(*) FILTER (
            WHERE raw ? 'season_stats'
              AND jsonb_typeof(raw->'season_stats') = 'object'
              AND (SELECT COUNT(*) FROM jsonb_each(raw->'season_stats')) >= 3
          ) AS stats3,
          COUNT(*) FILTER (WHERE COALESCE(raw->>'nil_valuation_observed', '0') = '1') AS nil_observed,
          COUNT(*) FILTER (
            WHERE COALESCE((raw->>'nil_valuation')::float, 0) > 0
              AND COALESCE(raw->>'nil_valuation_observed', '0') <> '1'
          ) AS nil_imputed_only,
          COUNT(*) FILTER (WHERE raw->>'stats_source' ILIKE '%sports_reference%') AS sr_source,
          COUNT(*) FILTER (WHERE COALESCE(raw->>'instagram_handle', '') <> '') AS ig_handle,
          COUNT(*) FILTER (
            WHERE COALESCE((raw->>'commercial_viability_score')::float, 0) > 0
          ) AS has_commercial_score,
          MAX(scraped_at) AS last_scraped
        FROM r
        """,
        sport,
    )
    return dict(row)


async def _sport_score_stats(conn: asyncpg.Connection, sport: str) -> dict:
    row = await conn.fetchrow(
        """
        WITH latest AS (
          SELECT DISTINCT ON (s.athlete_id)
            s.gravity_score, s.model_version, s.dollar_p50_usd,
            s.brand_score, s.proof_score, s.velocity_score, s.calculated_at
          FROM athlete_gravity_scores s
          JOIN athletes a ON a.id = s.athlete_id
          WHERE a.sport = $1 AND COALESCE(a.is_active, TRUE)
          ORDER BY s.athlete_id, s.calculated_at DESC NULLS LAST
        )
        SELECT
          COUNT(*) AS scored_n,
          ROUND(AVG(gravity_score)::numeric, 2) AS avg_gravity,
          ROUND(STDDEV(gravity_score)::numeric, 2) AS std_gravity,
          ROUND(MIN(gravity_score)::numeric, 2) AS min_gravity,
          ROUND(MAX(gravity_score)::numeric, 2) AS max_gravity,
          COUNT(*) FILTER (WHERE ABS(gravity_score - 77.0) < 0.15) AS near_77,
          COUNT(*) FILTER (WHERE model_version ILIKE '%fallback%') AS fallback_model,
          COUNT(*) FILTER (WHERE dollar_p50_usd IS NOT NULL AND dollar_p50_usd > 0) AS has_dollar_p50,
          MAX(calculated_at) AS last_scored
        FROM latest
        """,
        sport,
    )
    models = await conn.fetch(
        """
        WITH latest AS (
          SELECT DISTINCT ON (s.athlete_id) s.model_version
          FROM athlete_gravity_scores s
          JOIN athletes a ON a.id = s.athlete_id
          WHERE a.sport = $1 AND COALESCE(a.is_active, TRUE)
          ORDER BY s.athlete_id, s.calculated_at DESC NULLS LAST
        )
        SELECT COALESCE(model_version, '(none)') AS model, COUNT(*) AS n
        FROM latest GROUP BY 1 ORDER BY n DESC LIMIT 8
        """,
        sport,
    )
    out = dict(row)
    out["models"] = [(r["model"], r["n"]) for r in models]
    return out


async def _cfb_position_breakdown(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch(
        """
        WITH r AS (
          SELECT UPPER(COALESCE(a.position, 'UNK')) pos, COALESCE(r.raw_data, '{}'::jsonb) raw
          FROM athletes a
          LEFT JOIN LATERAL (
            SELECT raw_data FROM raw_athlete_data
            WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
          ) r ON TRUE
          WHERE a.sport = 'cfb' AND COALESCE(a.is_active, TRUE)
        )
        SELECT pos, COUNT(*) n,
          COUNT(*) FILTER (
            WHERE COALESCE((raw->>'games_played_season')::float, 0) > 0
               OR COALESCE((raw->'season_stats'->>'gp')::float, 0) > 0
          ) has_gp,
          COUNT(*) FILTER (
            WHERE raw ? 'season_stats'
              AND (SELECT COUNT(*) FROM jsonb_each(raw->'season_stats')) >= 3
          ) stats3,
          COUNT(*) FILTER (WHERE COALESCE(raw->>'nil_valuation_observed', '0') = '1') nil_obs
        FROM r
        GROUP BY 1 HAVING COUNT(*) >= 30
        ORDER BY n DESC LIMIT 15
        """
    )
    return [dict(r) for r in rows]


async def _ass_raw_sync_gap(conn: asyncpg.Connection, sport: str) -> dict:
    row = await conn.fetchrow(
        """
        WITH latest AS (
          SELECT a.id, COALESCE(r.raw_data, '{}'::jsonb) raw
          FROM athletes a
          LEFT JOIN LATERAL (
            SELECT raw_data FROM raw_athlete_data
            WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
          ) r ON TRUE
          WHERE a.sport = $1 AND COALESCE(a.is_active, TRUE)
        ), ass AS (
          SELECT athlete_id, COUNT(*) FILTER (WHERE stat_value > 0) AS pos_stats
          FROM athlete_season_stats WHERE sport = $1 GROUP BY athlete_id
        )
        SELECT
          COUNT(*) FILTER (WHERE ass.pos_stats >= 3) ass_has_3,
          COUNT(*) FILTER (
            WHERE ass.pos_stats >= 3
              AND NOT (l.raw ? 'season_stats'
                AND (SELECT COUNT(*) FROM jsonb_each(l.raw->'season_stats')) >= 3)
          ) ass3_not_in_raw
        FROM latest l
        LEFT JOIN ass ON ass.athlete_id = l.id
        """,
        sport,
    )
    return dict(row)


async def _nil_sources(conn: asyncpg.Connection, sport: str) -> list[tuple[str, int, int]]:
    rows = await conn.fetch(
        """
        WITH r AS (
          SELECT COALESCE(r.raw_data, '{}'::jsonb) raw FROM athletes a
          LEFT JOIN LATERAL (
            SELECT raw_data FROM raw_athlete_data
            WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
          ) r ON TRUE
          WHERE a.sport = $1 AND COALESCE(a.is_active, TRUE)
        )
        SELECT COALESCE(NULLIF(raw->>'nil_valuation_source', ''), '(none)') src,
          COUNT(*) n,
          COUNT(*) FILTER (WHERE COALESCE(raw->>'nil_valuation_observed', '0') = '1') obs
        FROM r GROUP BY 1 ORDER BY n DESC LIMIT 10
        """,
        sport,
    )
    return [(r["src"], r["n"], r["obs"]) for r in rows]


async def _recent_gap_fill_runs(conn: asyncpg.Connection) -> list[dict]:
    try:
        rows = await conn.fetch(
            """
            SELECT id, status, started_at, finished_at, metadata
            FROM scraper_runs
            WHERE metadata::text ILIKE '%gap%'
               OR metadata::text ILIKE '%nightly%'
            ORDER BY started_at DESC NULLS LAST
            LIMIT 5
            """
        )
        return [dict(r) for r in rows]
    except asyncpg.PostgresError:
        return []


async def build_report(conn: asyncpg.Connection, *, note: str = "") -> str:
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        "# Scrape & Score EDA Report",
        "",
        f"**Generated:** {now}",
        "",
    ]
    if note:
        lines.extend([f"> {note}", ""])

    lines.extend(
        [
            "## Executive summary",
            "",
            "This report summarizes post–gap-fill data quality (stats, NIL, SR fallback) and scoring",
            "distribution across acceptance sports. Key health signals:",
            "",
            "- **GP / stats3** — season stat coverage in raw JSON",
            "- **nil_observed** — verified NIL only (imputed excluded from training signal)",
            "- **sr_source** — Sports Reference fallback hits",
            "- **near_77 / fallback_model** — composite fallback scoring (production ML may need redeploy)",
            "- **commercial_viability_score** — college 1–99 percentile commercial index",
            "",
        ]
    )

    lines.extend(["## Scrape coverage by sport", "", "| Sport | Active | Scraped | GP% | Stats≥3 | NIL obs | SR | Comm. score |", "|-------|--------|---------|-----|---------|---------|-----|-------------|"])
    scrape_by_sport: dict[str, dict] = {}
    for sport in ACCEPTANCE_SPORTS:
        s = await _sport_scrape_stats(conn, sport)
        scrape_by_sport[sport] = s
        n = s["active_n"] or 0
        lines.append(
            f"| {sport} | {n} | {s['scraped']} | {_pct(s['has_gp'], n)} | "
            f"{_pct(s['stats3'], n)} | {_pct(s['nil_observed'], n)} | "
            f"{s['sr_source']} | {_pct(s['has_commercial_score'], n)} |"
        )

    lines.extend(["", "## Scoring by sport", "", "| Sport | Scored | Avg | Std | Min | Max | Near 77 | Fallback | $ P50 |", "|-------|--------|-----|-----|-----|-----|---------|----------|-------|"])
    score_by_sport: dict[str, dict] = {}
    for sport in ACCEPTANCE_SPORTS:
        sc = await _sport_score_stats(conn, sport)
        score_by_sport[sport] = sc
        n = sc["scored_n"] or 0
        lines.append(
            f"| {sport} | {n} | {sc['avg_gravity']} | {sc['std_gravity']} | "
            f"{sc['min_gravity']} | {sc['max_gravity']} | "
            f"{_pct(sc['near_77'], n)} | {_pct(sc['fallback_model'], n)} | "
            f"{_pct(sc['has_dollar_p50'], n)} |"
        )

    lines.extend(["", "### Model version mix", ""])
    for sport in ACCEPTANCE_SPORTS:
        sc = score_by_sport[sport]
        if not sc.get("models"):
            continue
        model_str = ", ".join(f"`{m}` ({n})" for m, n in sc["models"])
        lines.append(f"- **{sport}:** {model_str}")

    lines.extend(["", "## CFB deep dive", ""])
    sync = await _ass_raw_sync_gap(conn, "cfb")
    lines.extend(
        [
            f"- **athlete_season_stats ≥3 but raw <3:** {sync['ass3_not_in_raw']} "
            f"(of {sync['ass_has_3']} with ASS≥3)",
            "",
            "### By position (n≥30)",
            "",
            "| Pos | N | GP% | Stats≥3 | NIL obs |",
            "|-----|---|-----|---------|---------|",
        ]
    )
    for r in await _cfb_position_breakdown(conn):
        lines.append(
            f"| {r['pos']} | {r['n']} | {_pct(r['has_gp'], r['n'])} | "
            f"{_pct(r['stats3'], r['n'])} | {_pct(r['nil_obs'], r['n'])} |"
        )

    lines.extend(["", "### NIL sources (CFB)", ""])
    for src, n, obs in await _nil_sources(conn, "cfb"):
        lines.append(f"- `{src}`: {n} total, {obs} observed")

    lines.extend(["", "## College commercial viability sample", ""])
    rows = await conn.fetch(
        """
        WITH r AS (
          SELECT a.name, a.sport,
            (r.raw_data->>'commercial_viability_score')::float cv,
            (r.raw_data->>'nil_dollar_p50_usd')::float p50,
            r.raw_data->>'nil_signal_source' nil_src,
            s.gravity_score, s.model_version
          FROM athletes a
          JOIN LATERAL (
            SELECT raw_data FROM raw_athlete_data
            WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
          ) r ON TRUE
          LEFT JOIN LATERAL (
            SELECT gravity_score, model_version FROM athlete_gravity_scores
            WHERE athlete_id = a.id ORDER BY calculated_at DESC LIMIT 1
          ) s ON TRUE
          WHERE a.sport = ANY($1::text[])
            AND COALESCE(a.is_active, TRUE)
            AND (r.raw_data->>'commercial_viability_score') IS NOT NULL
        )
        SELECT * FROM r ORDER BY cv DESC NULLS LAST LIMIT 15
        """,
        list(COLLEGE_SPORTS),
    )
    if rows:
        lines.extend(["| Athlete | Sport | CV 1-99 | NIL P50 | Signal | Gravity | Model |", "|---------|-------|---------|---------|--------|---------|-------|"])
        for r in rows:
            p50 = f"${int(r['p50']):,}" if r["p50"] else "—"
            lines.append(
                f"| {r['name']} | {r['sport']} | {int(r['cv'] or 0)} | {p50} | "
                f"{r['nil_src'] or '—'} | {round(r['gravity_score'] or 0, 1)} | "
                f"`{r['model_version'] or '—'}` |"
            )
    else:
        lines.append("_No commercial_viability_score fields yet — run gap-fill + college rescore._")

    lines.extend(["", "## Recommendations", ""])
    cfb = scrape_by_sport.get("cfb", {})
    cfb_sc = score_by_sport.get("cfb", {})
    recs: list[str] = []
    if (cfb.get("has_gp") or 0) / max(cfb.get("active_n") or 1, 1) < 0.5:
        recs.append("CFB GP coverage still low — verify ESPN parser and SR fallback on next scrape batch.")
    if (cfb.get("sr_source") or 0) == 0:
        recs.append("Zero Sports Reference sources — check Firecrawl + direct SR search URLs.")
    if (cfb_sc.get("fallback_model") or 0) / max(cfb_sc.get("scored_n") or 1, 1) > 0.5:
        recs.append("Majority fallback scoring — redeploy gravity-ml with sport routes + CFB value bundle.")
    if (cfb.get("nil_observed") or 0) < 50:
        recs.append("NIL observed count low — gap-fill prioritization should target ranked athletes; confirm On3 scrapes.")
    if sync.get("ass3_not_in_raw", 0) > 50:
        recs.append("ASS→raw sync gap remains — confirm raw_stats_sync runs on orchestrator path.")
    if not recs:
        recs.append("Coverage and scoring metrics look healthy for acceptance sports.")
    for r in recs:
        lines.append(f"- {r}")

    if BASELINE_JSON.exists():
        try:
            baseline = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
            lines.extend(["", "## Delta vs baseline", ""])
            lines.append("| Sport | GP Δ | Stats≥3 Δ | NIL obs Δ | Comm. score Δ | Near 77 Δ |")
            lines.append("|-------|------|-----------|-----------|---------------|-----------|")
            for sport in ACCEPTANCE_SPORTS:
                b_scrape = (baseline.get("sports") or {}).get(sport, {}).get("scrape") or {}
                b_score = (baseline.get("sports") or {}).get(sport, {}).get("score") or {}
                cur_s = scrape_by_sport[sport]
                cur_sc = score_by_sport[sport]
                bn = b_scrape.get("active_n") or 1
                cn = cur_s["active_n"] or 1

                def _delta(cur: int, base: int, den: int) -> str:
                    cp = 100.0 * cur / den
                    bp = 100.0 * base / max(bn, 1)
                    d = cp - bp
                    sign = "+" if d >= 0 else ""
                    return f"{sign}{d:.1f}pp"

                lines.append(
                    f"| {sport} | "
                    f"{_delta(cur_s['has_gp'], b_scrape.get('has_gp', 0), cn)} | "
                    f"{_delta(cur_s['stats3'], b_scrape.get('stats3', 0), cn)} | "
                    f"{_delta(cur_s['nil_observed'], b_scrape.get('nil_observed', 0), cn)} | "
                    f"{_delta(cur_s['has_commercial_score'], b_scrape.get('has_commercial_score', 0), cn)} | "
                    f"{_delta(cur_sc['near_77'], b_score.get('near_77', 0), cur_sc['scored_n'] or 1)} |"
                )
        except (json.JSONDecodeError, OSError):
            pass

    lines.extend(["", "---", "", f"_Report JSON snapshot: `reports/scrape_score_eda_report.json`_"])
    return "\n".join(lines) + "\n"


async def main() -> None:
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise SystemExit("PG_DSN required")

    note = os.environ.get("REPORT_NOTE", "")
    conn = await asyncpg.connect(dsn, command_timeout=180)
    try:
        md = await build_report(conn, note=note)
    finally:
        await conn.close()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(md, encoding="utf-8")

    snapshot = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "sports": {},
    }
    conn2 = await asyncpg.connect(dsn, command_timeout=180)
    try:
        for sport in ACCEPTANCE_SPORTS:
            snapshot["sports"][sport] = {
                "scrape": await _sport_scrape_stats(conn2, sport),
                "score": await _sport_score_stats(conn2, sport),
            }
        if "cfb" in snapshot["sports"]:
            snapshot["cfb_ass_sync"] = await _ass_raw_sync_gap(conn2, "cfb")
    finally:
        await conn2.close()

    json_path = REPORT_PATH.with_suffix(".json")
    json_path.write_text(json.dumps(snapshot, default=str, indent=2), encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    asyncio.run(main())
