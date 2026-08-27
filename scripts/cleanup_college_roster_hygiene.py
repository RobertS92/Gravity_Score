#!/usr/bin/env python3
"""Deactivate college roster rows for athletes who have active pro rows.

Thin CLI over ``gravity_api.services.roster_retirement``. Prefer:

  PYTHONPATH=. python3 -m gravity_api.jobs.roster_hygiene --apply
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
from gravity_api.services.roster_retirement import apply_pro_college_hygiene


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
        "--min-confidence",
        default="medium",
        choices=("high", "medium", "low"),
        help="Lowest confidence that --apply will persist. Name-only is low.",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "reports" / "college_roster_hygiene_report.json"),
        help="JSON report path",
    )
    return parser


async def main() -> int:
    args = _parser().parse_args()
    if args.apply and args.min_confidence == "low" and not (args.name or args.college_id):
        raise SystemExit(
            "--apply --min-confidence low requires --name or --college-id; "
            "bulk name-only deactivation is disabled"
        )
    conn = await asyncpg.connect(get_settings().pg_dsn, statement_cache_size=0, command_timeout=120)
    try:
        report = await apply_pro_college_hygiene(
            conn,
            apply=args.apply,
            min_confidence=args.min_confidence,
            name=args.name,
            college_ids=args.college_id or None,
        )
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    k: report[k]
                    for k in (
                        "mode",
                        "min_confidence",
                        "candidates",
                        "actionable",
                        "deactivated",
                        "by_confidence",
                    )
                }
            )
        )
        print(f"wrote {out_path}")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
