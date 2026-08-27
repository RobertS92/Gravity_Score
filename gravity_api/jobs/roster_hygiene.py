"""Deactivate college rows that match an active pro roster.

Dry-run:
  PYTHONPATH=. python3 -m gravity_api.jobs.roster_hygiene

Apply medium+high confidence matches:
  PYTHONPATH=. python3 -m gravity_api.jobs.roster_hygiene --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()

import asyncpg

from gravity_api.services.roster_retirement import Confidence, apply_pro_college_hygiene

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main_async(
    *,
    apply: bool,
    min_confidence: Confidence,
    name: str | None,
    college_ids: list[str],
    out: str | None,
) -> dict:
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise RuntimeError("PG_DSN required")
    conn = await asyncpg.connect(dsn, statement_cache_size=0, command_timeout=120)
    try:
        report = await apply_pro_college_hygiene(
            conn,
            apply=apply,
            min_confidence=min_confidence,
            name=name,
            college_ids=college_ids or None,
        )
    finally:
        await conn.close()
    summary = {k: report[k] for k in ("mode", "min_confidence", "candidates", "actionable", "deactivated", "by_confidence")}
    logger.info("%s", json.dumps(summary))
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
        logger.info("wrote %s", path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="College/pro roster hygiene")
    parser.add_argument("--apply", action="store_true", help="Persist left_for_draft updates")
    parser.add_argument(
        "--min-confidence",
        default="medium",
        choices=("high", "medium", "low"),
        help="Lowest auto-apply confidence. low is name-only and unsafe in bulk.",
    )
    parser.add_argument("--name", default=None)
    parser.add_argument("--college-id", action="append", default=[])
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parents[2] / "reports" / "college_roster_hygiene_report.json"),
    )
    args = parser.parse_args()
    if args.apply and args.min_confidence == "low" and not (args.name or args.college_id):
        raise SystemExit("--apply --min-confidence low requires --name or --college-id")
    asyncio.run(
        main_async(
            apply=args.apply,
            min_confidence=args.min_confidence,  # type: ignore[arg-type]
            name=args.name,
            college_ids=args.college_id,
            out=args.out,
        )
    )


if __name__ == "__main__":
    main()
