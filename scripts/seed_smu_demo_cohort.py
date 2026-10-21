#!/usr/bin/env python3
"""Seed / refresh the SMU demonstration cohort via ESPN roster sync.

Loads data/demo/smu_demo_cohort.json, syncs SMU (ESPN team 2567) for CFB and
men's basketball, then verifies curated athletes exist with fresh
roster_verified_at. Does not invent scores — run gap-fill/scoring separately
before Brand Match demos.

Usage:
  PG_DSN=... python scripts/seed_smu_demo_cohort.py
  PG_DSN=... python scripts/seed_smu_demo_cohort.py --verify-only
  PG_DSN=... python scripts/seed_smu_demo_cohort.py --include-wbb
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg

from gravity_api.services.roster_sync import sync_team_roster

COHORT_PATH = ROOT / "data" / "demo" / "smu_demo_cohort.json"
SMU_TEAM_ID = "2567"


def load_cohort() -> dict[str, Any]:
    return json.loads(COHORT_PATH.read_text(encoding="utf-8"))


def curated_athletes(cohort: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in cohort.get("athletes") or []:
        if row.get("coverage") == "gap":
            continue
        espn_id = str(row.get("espn_id") or "").strip()
        if not espn_id:
            continue
        out.append(row)
    return out


async def verify_cohort(conn: asyncpg.Connection, cohort: dict[str, Any]) -> dict[str, Any]:
    wanted = curated_athletes(cohort)
    missing: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    present: list[dict[str, Any]] = []
    for row in wanted:
        espn_id = str(row["espn_id"])
        db = await conn.fetchrow(
            """SELECT id::text AS id, name, school, sport, position,
                      roster_status, is_active, roster_verified_at
                 FROM athletes
                WHERE espn_id = $1
                LIMIT 1""",
            espn_id,
        )
        payload = {
            "name": row.get("name"),
            "espn_id": espn_id,
            "sport": row.get("sport"),
            "db": dict(db) if db else None,
        }
        if not db:
            missing.append(payload)
            continue
        present.append(payload)
        verified = db["roster_verified_at"]
        active = bool(db["is_active"]) and str(db["roster_status"] or "") in (
            "active_on_roster",
            "transferred",
        )
        if verified is None or not active:
            stale.append(payload)

    school_cfb = await conn.fetchval(
        """SELECT COUNT(*)::int FROM athletes
            WHERE sport = 'cfb'
              AND school ILIKE '%SMU%'
              AND COALESCE(is_active, TRUE) = TRUE"""
    )
    jennings = await conn.fetchrow(
        """SELECT id::text AS id, name, school, sport, roster_verified_at
             FROM athletes
            WHERE espn_id = '5084084' OR name ILIKE 'Kevin Jennings'
            LIMIT 1"""
    )
    return {
        "wanted": len(wanted),
        "present": len(present),
        "missing": missing,
        "stale_or_inactive": stale,
        "smu_cfb_active_count": school_cfb,
        "kevin_jennings": dict(jennings) if jennings else None,
        "ok": not missing and jennings is not None,
    }


async def sync_smu(
    conn: asyncpg.Connection,
    *,
    include_wbb: bool,
) -> list[dict[str, Any]]:
    sports = ["cfb", "ncaab_mens"]
    if include_wbb:
        sports.append("ncaab_womens")
    results: list[dict[str, Any]] = []
    for sport in sports:
        print(f"Syncing SMU {sport} team_id={SMU_TEAM_ID} …")
        result = await sync_team_roster(conn, sport, SMU_TEAM_ID)
        results.append(result)
        err = result.get("error")
        seen = result.get("players_seen") or result.get("added", 0) + result.get("updated", 0)
        print(
            f"  sport={sport} error={err!r} added={result.get('added')} "
            f"updated={result.get('updated')} players_seen≈{seen}"
        )
    return results


async def run(*, verify_only: bool, include_wbb: bool) -> int:
    dsn = os.environ.get("PG_DSN") or os.environ.get("DATABASE_URL")
    if not dsn:
        print("Set PG_DSN or DATABASE_URL", file=sys.stderr)
        return 2

    cohort = load_cohort()
    team = (cohort.get("school") or {}).get("espn_team_id") or SMU_TEAM_ID
    if str(team) != SMU_TEAM_ID:
        print(f"Warning: cohort team id {team} != default {SMU_TEAM_ID}", file=sys.stderr)

    conn = await asyncpg.connect(dsn)
    try:
        sync_results: list[dict[str, Any]] = []
        if not verify_only:
            sync_results = await sync_smu(conn, include_wbb=include_wbb)
        report = await verify_cohort(conn, cohort)
    finally:
        await conn.close()

    print(json.dumps({"sync": sync_results, "verify": report}, default=str, indent=2))
    if not report["ok"]:
        print(
            "SMU cohort incomplete. Missing espn_ids:",
            [m["espn_id"] for m in report["missing"]],
            file=sys.stderr,
        )
        return 1
    print("SMU demo cohort OK — Kevin Jennings present; curated espn_ids found.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed / verify SMU demo cohort")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip roster sync; only check DB for curated espn_ids",
    )
    parser.add_argument(
        "--include-wbb",
        action="store_true",
        help="Also sync ncaab_womens (often empty for SMU on ESPN)",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(verify_only=args.verify_only, include_wbb=args.include_wbb)))


if __name__ == "__main__":
    main()
