#!/usr/bin/env python3
"""Deactivate college roster rows for athletes who have active pro rows.

This handles the common draft/transfer boundary case where a player remains in
the college search set after a pro roster row has been created.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg

from gravity_api.config import get_settings

COLLEGE_SPORTS = ("cfb", "ncaab_mens", "ncaab_womens")
PRO_SPORTS = ("nfl", "nba", "wnba", "mlb")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Persist deactivations")
    parser.add_argument("--name", help="Limit to one athlete name for surgical cleanup")
    parser.add_argument(
        "--college-id",
        action="append",
        default=[],
        help="Explicit college athlete UUID to review/deactivate (repeatable)",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "reports" / "college_roster_hygiene_report.json"),
        help="JSON report path",
    )
    return parser


async def find_stale_college_rows(
    conn: asyncpg.Connection,
    *,
    name: str | None = None,
    college_ids: list[str] | None = None,
) -> list[dict]:
    params: list[object] = [list(COLLEGE_SPORTS), list(PRO_SPORTS)]
    filters: list[str] = []
    if name:
        params.append(name)
        filters.append(f"AND name ILIKE ${len(params)}")
    if college_ids:
        params.append(college_ids)
        filters.append(f"AND id = ANY(${len(params)}::uuid[])")
    candidate_filter = "\n            ".join(filters)

    rows = await conn.fetch(
        f"""
        WITH active_college AS (
          SELECT *,
                 regexp_replace(lower(name), '[^a-z0-9]+', '', 'g') AS name_key
          FROM athletes
          WHERE sport = ANY($1::text[])
            AND COALESCE(is_active, TRUE) = TRUE
            AND name !~ '^[A-Z]\\.?\\s'
            {candidate_filter}
        ),
        active_pro AS (
          SELECT *,
                 regexp_replace(lower(name), '[^a-z0-9]+', '', 'g') AS name_key
          FROM athletes
          WHERE sport = ANY($2::text[])
            AND COALESCE(is_active, TRUE) = TRUE
        )
        SELECT college.id::text AS college_id,
               college.name,
               college.sport AS college_sport,
               college.position AS college_position,
               college.school AS college_school,
               college.team AS college_team,
               college.height_inches AS college_height_inches,
               college.weight_lbs AS college_weight_lbs,
               college.updated_at AS college_updated_at,
               pro.id::text AS pro_id,
               pro.name AS pro_name,
               pro.sport AS pro_sport,
               pro.position AS pro_position,
               pro.school AS pro_team,
               pro.height_inches AS pro_height_inches,
               pro.weight_lbs AS pro_weight_lbs,
               pro.updated_at AS pro_updated_at
        FROM active_college college
        JOIN active_pro pro
          ON pro.name_key = college.name_key
         AND (
              (college.sport = 'cfb' AND pro.sport = 'nfl')
           OR (college.sport = 'ncaab_mens' AND pro.sport = 'nba')
           OR (college.sport = 'ncaab_womens' AND pro.sport = 'wnba')
         )
        ORDER BY college.name, college.sport, pro.updated_at DESC NULLS LAST
        """,
        *params,
    )
    seen: set[str] = set()
    output: list[dict] = []
    for row in rows:
        if row["college_id"] in seen:
            continue
        seen.add(row["college_id"])
        output.append(dict(row))
    return output


async def main() -> int:
    args = _parser().parse_args()
    if args.apply and not (args.name or args.college_id):
        raise SystemExit(
            "--apply requires --name or one or more --college-id values; "
            "bulk exact-name deactivation is intentionally disabled"
        )
    conn = await asyncpg.connect(get_settings().pg_dsn, statement_cache_size=0, command_timeout=120)
    try:
        stale = await find_stale_college_rows(
            conn,
            name=args.name,
            college_ids=args.college_id,
        )
        changed = 0
        if args.apply and stale:
            ids = [row["college_id"] for row in stale]
            status = await conn.execute(
                """
                UPDATE athletes
                SET is_active = FALSE,
                    updated_at = NOW()
                WHERE id = ANY($1::uuid[])
                  AND sport = ANY($2::text[])
                  AND COALESCE(is_active, TRUE) = TRUE
                """,
                ids,
                list(COLLEGE_SPORTS),
            )
            changed = int(status.rsplit(" ", 1)[-1])
        report = {
            "mode": "apply" if args.apply else "dry_run",
            "candidates": len(stale),
            "deactivated": changed,
            "rows": stale,
        }
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps({k: report[k] for k in ("mode", "candidates", "deactivated")}))
        print(f"wrote {out_path}")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
