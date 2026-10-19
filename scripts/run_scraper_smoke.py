#!/usr/bin/env python3
"""Multi-sport scraper smoke test CLI.

Examples:
  PYTHONPATH=. python scripts/run_scraper_smoke.py
  PYTHONPATH=. python scripts/run_scraper_smoke.py --json-out /tmp/smoke.json
  PG_DSN=... PYTHONPATH=. python scripts/run_scraper_smoke.py --include-db
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gravity_api.scraper_smoke.runner import run_smoke_suite_sync  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Scraper smoke test (priority sports)")
    parser.add_argument(
        "--include-db",
        action="store_true",
        help="Also run DB scheduled_full when PG_DSN is set",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write full JSON results to this path",
    )
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        default=True,
        help="Exit 1 if any ESPN scraper smoke check fails (default)",
    )
    parser.add_argument(
        "--no-fail-on-error",
        action="store_true",
        help="Always exit 0 (still print failures)",
    )
    args = parser.parse_args()

    import os

    include_db = bool(args.include_db) or bool(os.environ.get("PG_DSN", "").strip())
    payload = run_smoke_suite_sync(include_db=include_db)

    summary = payload["summary"]
    print("=== Scraper smoke summary ===")
    print(json.dumps(summary, indent=2))
    print()
    for sport, rows in payload["by_sport"].items():
        print(f"## {sport}")
        for row in rows:
            mark = "PASS" if row["passed"] else "FAIL"
            if row["mode"] == "skipped":
                mark = "SKIP"
            print(f"  [{mark}] {row['name']} ({row['espn_id']}) mode={row['mode']}")
            for c in row.get("checks") or []:
                if not c["ok"]:
                    print(f"      - FAIL {c['name']}: {c['detail']}")
            if row.get("error") and row["mode"] != "skipped":
                print(f"      error: {row['error']}")
        print()

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {args.json_out}")

    failed = summary.get("espn_scrapers_failed", 0) + summary.get(
        "db_scheduled_full_failed", 0
    )
    if args.no_fail_on_error:
        return 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
