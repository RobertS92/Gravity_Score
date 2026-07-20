#!/usr/bin/env python3
"""Rescore the key-athlete verify panel (~20/sport) and write results."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["DISABLE_FIRECRAWL"] = "1"
os.environ["SCORING_MODE"] = "local"
os.environ["TEAM_RECORD_REMOTE_FETCH_DISABLED"] = "1"
os.environ.setdefault("MODEL_BUNDLE_ROOT", str((ROOT / "models" / "bundles").resolve()))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg

from gravity_api.config import get_settings
from gravity_api.scrapers.orchestrator import run_scrapers_for_athlete
from gravity_api.services.sport_percentiles import refresh_sport_percentiles
from scripts.run_fast_fleet_rescore import score_and_persist

PANEL_PATH = ROOT / "reports" / "key_athlete_verify_panel.json"
OUT_PATH = ROOT / "reports" / "key_athlete_verify_results.json"
SUMMARY_PATH = ROOT / "reports" / "key_athlete_verify_summary.md"
CONCURRENCY = 8
SCORE_TIMEOUT_S = 150


def as_dict(dc):
    if isinstance(dc, dict):
        return dc
    if isinstance(dc, str):
        try:
            v = json.loads(dc)
            return v if isinstance(v, dict) else {}
        except Exception:
            return {}
    return {}


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    pos = (len(ordered) - 1) * pct
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return round(ordered[lo] * (1.0 - frac) + ordered[hi] * frac, 4)


def _score_distribution(rows: list[dict], key: str) -> dict:
    values = [float(r[key]) for r in rows if r.get(key) is not None]
    n = len(values)
    if not values:
        return {"n": 0}
    return {
        "n": n,
        "min": round(min(values), 4),
        "p10": _percentile(values, 0.10),
        "p25": _percentile(values, 0.25),
        "median": _percentile(values, 0.50),
        "p75": _percentile(values, 0.75),
        "p90": _percentile(values, 0.90),
        "p95": _percentile(values, 0.95),
        "max": round(max(values), 4),
        "below_50": sum(v < 50 for v in values),
        "50_to_75": sum(50 <= v < 75 for v in values),
        "75_to_90": sum(75 <= v < 90 for v in values),
        "90_plus": sum(v >= 90 for v in values),
        "90_plus_pct": round(100.0 * sum(v >= 90 for v in values) / n, 2),
        "floor_5": sum(v <= 5.5 for v in values),
    }


def _distribution_report(results: list[dict]) -> dict:
    sports = sorted({str(r.get("sport")) for r in results})
    out = {
        "overall": {
            "gravity": _score_distribution(results, "G_after"),
            "value": _score_distribution(results, "V_after"),
        },
        "by_sport": {},
    }
    for sport in sports:
        rows = [r for r in results if r.get("sport") == sport]
        out["by_sport"][sport] = {
            "gravity": _score_distribution(rows, "G_after"),
            "value": _score_distribution(rows, "V_after"),
        }
    return out


async def ingest_one(pool, sport: str, aid: str, name: str) -> bool:
    if sport == "cfb":
        return True
    keys = [f"espn_stats_{sport}"]
    try:
        async with pool.acquire() as conn:
            await asyncio.wait_for(
                run_scrapers_for_athlete(
                    conn,
                    aid,
                    scraper_keys=keys,
                    persist=True,
                    score_after=False,
                    include_extended=False,
                ),
                timeout=75,
            )
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  INGEST ERR {name}: {e}", flush=True)
        return False


async def main() -> int:
    panel = json.loads(PANEL_PATH.read_text())
    athletes = [a for rows in panel["sports"].values() for a in rows]
    print(f"Panel size: {len(athletes)}", flush=True)

    pool = await asyncpg.create_pool(
        get_settings().pg_dsn,
        min_size=2,
        max_size=CONCURRENCY + 2,
        statement_cache_size=0,
        command_timeout=180,
    )

    # Score-only by default: GS inference + team records already land in
    # score_and_persist. Optional --ingest re-pulls ESPN stats (slow; college
    # experience side-scrape can hang pro athletes).
    do_ingest = "--ingest" in sys.argv
    if do_ingest:
        print("=== INGEST ===", flush=True)
        sem = asyncio.Semaphore(6)

        async def _ing(a):
            async with sem:
                return await ingest_one(pool, a["sport"], a["id"], a["name"])

        for sport in ["nfl", "nba", "wnba", "ncaab_mens", "ncaab_womens"]:
            group = [a for a in athletes if a["sport"] == sport]
            t0 = time.time()
            await asyncio.gather(*(_ing(a) for a in group))
            print(f"  ingested {sport}: {len(group)} in {time.time() - t0:.1f}s", flush=True)
    else:
        print("=== SKIP INGEST (score-only; pass --ingest to refresh ESPN) ===", flush=True)

    report_only = "--report-only" in sys.argv
    print("=== REPORT ONLY ===" if report_only else "=== RESCORE ===", flush=True)
    results: list[dict] = []
    sem2 = asyncio.Semaphore(CONCURRENCY)
    lock = asyncio.Lock()
    done = 0

    async def _score(a):
        nonlocal done
        async with sem2:
            try:
                r = await asyncio.wait_for(score_and_persist(pool, a["id"]), timeout=SCORE_TIMEOUT_S)
                row = {
                    **a,
                    "G_after": r.get("gravity"),
                    "V_after": r.get("value"),
                    "gravity_source": r.get("gravity_source"),
                    "fallback": r.get("fallback"),
                    "ok": r.get("ok", True),
                }
            except Exception as e:  # noqa: BLE001
                print(f"  SCORE ERR {a['name']}: {e}", flush=True)
                row = {**a, "G_after": None, "V_after": None, "ok": False, "error": str(e)}
            async with lock:
                results.append(row)
                done += 1
                if done % 20 == 0:
                    print(f"  scored {done}/{len(athletes)}", flush=True)

    t0 = time.time()
    if report_only:
        results = [{**a, "ok": True} for a in athletes]
    else:
        await asyncio.gather(*(_score(a) for a in athletes))
        print(f"Rescore done in {time.time() - t0:.1f}s", flush=True)

    async with pool.acquire() as conn:
        await refresh_sport_percentiles(conn, [a["id"] for a in athletes])
        for row in results:
            if not row.get("ok"):
                continue
            db = await conn.fetchrow(
                """SELECT gravity_score, gravity_sport_percentile,
                          value_score, value_sport_percentile,
                          proof_score, dollar_confidence
                   FROM athlete_gravity_scores WHERE athlete_id=$1::uuid
                   ORDER BY calculated_at DESC LIMIT 1""",
                row["id"],
            )
            if not db:
                continue
            dc = as_dict(db["dollar_confidence"])
            row["G_after"] = (
                float(db["gravity_score"]) if db["gravity_score"] is not None else row.get("G_after")
            )
            row["V_after"] = (
                float(db["value_score"]) if db["value_score"] is not None else row.get("V_after")
            )
            row["G_sport_percentile"] = (
                float(db["gravity_sport_percentile"])
                if db["gravity_sport_percentile"] is not None
                else None
            )
            row["V_sport_percentile"] = (
                float(db["value_sport_percentile"])
                if db["value_sport_percentile"] is not None
                else None
            )
            row["proof"] = float(db["proof_score"]) if db["proof_score"] is not None else None
            row["value_source"] = dc.get("value_score_source")
            row["gravity_source"] = dc.get("gravity_source") or row.get("gravity_source")
            row["participation"] = dc.get("participation_index")
            row["team_obs"] = dc.get("team_record_observed")
            row["win_impact"] = dc.get("win_impact_score")

    print("\n" + "=" * 100, flush=True)
    print(
        f"{'SPORT':12} {'NAME':24} {'POS':4} {'G_bef':>6} {'G_aft':>6} "
        f"{'V_bef':>6} {'V_aft':>6} {'gsrc':18} {'vsrc':14}",
        flush=True,
    )
    print("=" * 100, flush=True)
    by_sport: dict[str, list] = defaultdict(list)
    for r in results:
        by_sport[r["sport"]].append(r)
    for sport in ["nfl", "nba", "wnba", "cfb", "ncaab_mens", "ncaab_womens"]:
        rows = sorted(by_sport[sport], key=lambda x: -(x.get("G_after") or 0))
        for r in rows:
            gb = f"{r.get('G_before'):.1f}" if r.get("G_before") is not None else "—"
            ga = f"{r.get('G_after'):.1f}" if r.get("G_after") is not None else "—"
            vb = f"{r.get('V_before'):.1f}" if r.get("V_before") is not None else "—"
            va = f"{r.get('V_after'):.1f}" if r.get("V_after") is not None else "—"
            print(
                f"{sport:12} {r['name'][:24]:24} {(r.get('position') or '?'):4} "
                f"{gb:>6} {ga:>6} {vb:>6} {va:>6} "
                f"{str(r.get('gravity_source') or '—')[:18]:18} "
                f"{str(r.get('value_source') or '—')[:14]:14}",
                flush=True,
            )
        print("-" * 100, flush=True)

    print("\n=== SANITY ===", flush=True)
    issues: list[str] = []
    distributions = _distribution_report(results)
    overall_g = distributions["overall"]["gravity"]
    overall_v = distributions["overall"]["value"]

    key_names = (
        "Patrick Mahomes",
        "Courtland Sutton",
        "Patrick Taylor Jr.",
        "Quenton Nelson",
        "Bam Adebayo",
        "Brandon Ingram",
        "LeBron James",
        "Nikola Jokic",
        "Evan Mobley",
        "Angel Reese",
        "A'ja Wilson",
        "Arch Manning",
    )
    key_athletes = {
        name: next((r for r in results if r.get("name") == name), None)
        for name in key_names
    }

    mahomes = key_athletes["Patrick Mahomes"]
    sutton = key_athletes["Courtland Sutton"]
    if not mahomes or not (94 <= float(mahomes.get("G_after") or 0) <= 97):
        issues.append(f"Mahomes global G outside 94–97: {mahomes and mahomes.get('G_after')}")
    if not sutton or not (70 <= float(sutton.get("G_after") or 0) <= 80):
        issues.append(f"Sutton global G outside 70–80: {sutton and sutton.get('G_after')}")

    lebron = key_athletes["LeBron James"]
    angel = key_athletes["Angel Reese"]
    aja = key_athletes["A'ja Wilson"]
    if not lebron or not (95 <= float(lebron.get("G_after") or 0) <= 97):
        issues.append(f"LeBron global G outside 95–97: {lebron and lebron.get('G_after')}")
    oluokun = next((r for r in results if r.get("name") == "Foyesade Oluokun"), None)
    if oluokun and not (60 <= float(oluokun.get("G_after") or 0) <= 72):
        issues.append(
            f"Oluokun G re-inflated outside 60–72 (team-Twitter gate): {oluokun.get('G_after')}"
        )
    if not angel or not (82 <= float(angel.get("G_after") or 0) <= 88):
        issues.append(f"Angel global G outside evidence band 82–88: {angel and angel.get('G_after')}")
    if not aja or not (95 <= float(aja.get("V_after") or 0) <= 99):
        issues.append(f"A'ja absolute V outside 95–99: {aja and aja.get('V_after')}")

    for name, band in (
        ("Nikola Jokic", (80.0, 89.9)),
        ("Bam Adebayo", (74.0, 84.0)),
        ("Evan Mobley", (72.0, 82.0)),
    ):
        row = key_athletes[name]
        if not row or not (band[0] <= float(row.get("G_after") or 0) <= band[1]):
            issues.append(f"{name} commercial G outside {band[0]}–{band[1]}: {row and row.get('G_after')}")

    quenton = key_athletes["Quenton Nelson"]
    if not quenton or float(quenton.get("G_after") or 100) >= 90:
        issues.append(f"Quenton commercial G too high: {quenton and quenton.get('G_after')}")
    if not quenton or float(quenton.get("V_after") or 0) <= 50:
        issues.append(f"Quenton V lacks meaningful impact: {quenton and quenton.get('V_after')}")

    for name in ("Bam Adebayo", "Brandon Ingram"):
        row = key_athletes[name]
        if not row or float(row.get("G_after") or 100) >= 95:
            issues.append(f"{name} commercial G too high: {row and row.get('G_after')}")

    if overall_g.get("90_plus_pct", 100) > 5:
        issues.append(f"Gravity 90+ not rare: {overall_g.get('90_plus_pct')}%")
    if overall_v.get("90_plus_pct", 100) > 15:
        issues.append(f"Value 90+ not rare: {overall_v.get('90_plus_pct')}%")
    if overall_v.get("floor_5", 0) > 0:
        issues.append(f"Value floor cluster remains: {overall_v.get('floor_5')}")
    if overall_g.get("50_to_75", 0) / max(overall_g.get("n", 1), 1) < 0.50:
        issues.append("Gravity broad middle (50–75) is not a panel majority")
    if overall_g.get("below_50", 0) == 0:
        issues.append("Gravity has no athletes below 50")
    if overall_v.get("50_to_75", 0) / max(overall_v.get("n", 1), 1) < 0.35:
        issues.append("Value broad middle (50–75) is under 35% of elite-skewed panel")

    for sport, rows in by_sport.items():
        missing = [r["name"] for r in rows if r.get("G_after") is None or r.get("V_after") is None]
        if missing:
            issues.append(f"{sport} missing G/V: {missing[:5]}")
        vals = [r.get("V_after") for r in rows if r.get("V_after") is not None]
        if vals:
            uniq = len({round(v, 1) for v in vals})
            floor_n = sum(1 for v in vals if v <= 5.5)
            print(
                f"{sport}: V range [{min(vals):.1f},{max(vals):.1f}] "
                f"unique~{uniq} floor5={floor_n}/{len(vals)}",
                flush=True,
            )
        gravs = [r.get("G_after") for r in rows if r.get("G_after") is not None]
        if gravs:
            print(f"{sport}: G range [{min(gravs):.1f},{max(gravs):.1f}]", flush=True)

    sane = len(issues) == 0
    print("ISSUES:" if issues else "No issues", flush=True)
    for i in issues:
        print(" -", i, flush=True)
    print("PANEL_SANITY", "PASS" if sane else "WARN", flush=True)

    OUT_PATH.write_text(
        json.dumps(
            {
                "results": results,
                "by_sport": {s: by_sport[s] for s in by_sport},
                "distributions": distributions,
                "key_athletes": key_athletes,
                "issues": issues,
                "sane": sane,
                "elapsed_s": round(time.time() - t0, 1),
            },
            indent=2,
            default=str,
        )
        + "\n"
    )
    print("wrote", OUT_PATH, flush=True)

    lines = [
        "# Verify Panel Score Redesign",
        "",
        f"Panel size: {len(results)}  ",
        f"Acceptance: **{'PASS' if sane else 'WARN'}**  ",
        f"Gravity 90+: {overall_g.get('90_plus')} ({overall_g.get('90_plus_pct')}%)  ",
        f"Value 90+: {overall_v.get('90_plus')} ({overall_v.get('90_plus_pct')}%)  ",
        f"Value floor (≤5.5): {overall_v.get('floor_5')}",
        "",
        "> Sport percentiles use the full active persisted sport cohort. The scoped college "
        "fleet has been rescored; non-college cohort rows may still reflect their latest "
        "available score pass.",
        "",
        "## Key athletes",
        "",
        "| Athlete | G before | G global | G sport pct | V before | V global | V sport pct | Sources |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name in key_names:
        row = key_athletes.get(name)
        if row:
            lines.append(
                f"| {name} | {row.get('G_before')} | {row.get('G_after')} | "
                f"{row.get('G_sport_percentile')} | {row.get('V_before')} | "
                f"{row.get('V_after')} | {row.get('V_sport_percentile')} | "
                f"{row.get('gravity_source')} / {row.get('value_source')} |"
            )
    lines += [
        "",
        "## Per-sport distributions",
        "",
        "| Sport | Score | Min | P10 | P25 | Median | P75 | P90 | P95 | Max | <50 | 50–75 | 75–90 | 90+ |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, dist in (
        ("G", distributions["overall"]["gravity"]),
        ("V", distributions["overall"]["value"]),
    ):
        lines.append(
            f"| **Overall** | {label} | {dist.get('min')} | {dist.get('p10')} | "
            f"{dist.get('p25')} | {dist.get('median')} | {dist.get('p75')} | "
            f"{dist.get('p90')} | {dist.get('p95')} | {dist.get('max')} | "
            f"{dist.get('below_50')} | {dist.get('50_to_75')} | "
            f"{dist.get('75_to_90')} | {dist.get('90_plus')} |"
        )
    for sport, blocks in distributions["by_sport"].items():
        for label, dist in (("G", blocks["gravity"]), ("V", blocks["value"])):
            lines.append(
                f"| {sport} | {label} | {dist.get('min')} | {dist.get('p10')} | "
                f"{dist.get('p25')} | {dist.get('median')} | {dist.get('p75')} | "
                f"{dist.get('p90')} | {dist.get('p95')} | {dist.get('max')} | "
                f"{dist.get('below_50')} | {dist.get('50_to_75')} | "
                f"{dist.get('75_to_90')} | {dist.get('90_plus')} |"
            )
    if issues:
        lines += ["", "## Remaining issues", ""] + [f"- {issue}" for issue in issues]
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", SUMMARY_PATH, flush=True)
    await pool.close()
    return 0 if sane else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
