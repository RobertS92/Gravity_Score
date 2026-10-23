#!/usr/bin/env python3
"""Multi-sport scraper smoke test CLI.

Examples:
  PYTHONPATH=. python scripts/run_scraper_smoke.py
  PYTHONPATH=. python scripts/run_scraper_smoke.py --json-out /tmp/smoke.json
  PYTHONPATH=. python scripts/run_scraper_smoke.py \\
    --free-tier-csv /tmp/free-tier.csv \\
    --wp10-csv /tmp/wp10-season-history.csv
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

from gravity_api.scraper_smoke.runner import (  # noqa: E402
    run_smoke_suite_sync,
    smoke_results_to_csv_rows,
    write_free_tier_csv,
    write_smoke_csv,
    write_wp10_detail_csv,
)


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
        "--csv-out",
        type=Path,
        default=None,
        help=(
            "Write smoke CSV with WP9 provenance columns "
            "(season_year, season_label, season_type, team_id, is_total, "
            "is_complete, stats_as_of, validation_status, n_seasons, career_*, "
            "stats_scope=season|career) plus WP10 summary columns"
        ),
    )
    parser.add_argument(
        "--free-tier-csv",
        type=Path,
        default=None,
        help="Write one-row-per-athlete free-tier CSV (Phase-1 shape + WP10 cols)",
    )
    parser.add_argument(
        "--wp10-csv",
        type=Path,
        default=None,
        help="Write dedicated season-history + WP10 game detail CSV",
    )
    parser.add_argument(
        "--no-season-history",
        action="store_true",
        help="Skip live SeasonStatLine season-history collector",
    )
    parser.add_argument(
        "--no-wp10-games",
        action="store_true",
        help="Skip live WP10 eventlog/summary/box fetch",
    )
    parser.add_argument(
        "--max-history-seasons",
        type=int,
        default=None,
        help="Cap seasons fetched per athlete (default: all log years)",
    )
    parser.add_argument(
        "--max-wp10-games",
        type=int,
        default=2,
        help="Max games to fetch/validate per athlete (default 2)",
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
    payload = run_smoke_suite_sync(
        include_db=include_db,
        include_season_history=not args.no_season_history,
        include_wp10_games=not args.no_wp10_games,
        max_history_seasons=args.max_history_seasons,
        max_wp10_games=args.max_wp10_games,
    )

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
            sample = row.get("fields_sample") or {}
            if sample.get("n_season_lines") is not None:
                print(
                    f"      season_history: ok={sample.get('season_history_ok')} "
                    f"lines={sample.get('n_season_lines')} "
                    f"log={sample.get('n_seasons_log')}"
                )
            if sample.get("games_fetched") is not None or sample.get("wp10_games_ok") is not None:
                print(
                    f"      wp10_games: ok={sample.get('wp10_games_ok')} "
                    f"fetched={sample.get('games_fetched')} "
                    f"box={sample.get('games_with_athlete_box')} "
                    f"reconcile={sample.get('box_reconcile_ok')}"
                )
            if row.get("error") and row["mode"] != "skipped":
                print(f"      error: {row['error']}")
        print()

    # Same provenance rows as CSV (season + career) for JSON consumers.
    export_rows = smoke_results_to_csv_rows(payload)
    payload = {**payload, "export_rows": export_rows}

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"Wrote {args.json_out} ({len(export_rows)} export_rows)")

    if args.csv_out:
        n = write_smoke_csv(payload, args.csv_out)
        print(
            f"Wrote {args.csv_out} ({n} rows; WP9+WP10 columns: "
            "stats_scope, season_*, wp10_*, career_*)"
        )

    if args.free_tier_csv:
        n = write_free_tier_csv(payload, args.free_tier_csv)
        print(f"Wrote {args.free_tier_csv} ({n} free-tier athlete rows)")

    if args.wp10_csv:
        n = write_wp10_detail_csv(payload, args.wp10_csv)
        print(f"Wrote {args.wp10_csv} ({n} season-history/game detail rows)")

    failed = summary.get("espn_scrapers_failed", 0) + summary.get(
        "db_scheduled_full_failed", 0
    )
    if args.no_fail_on_error:
        return 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
