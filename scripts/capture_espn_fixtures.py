#!/usr/bin/env python3
"""WP0 — Capture raw ESPN JSON fixtures for season-correct athlete stats.

Saves under gravity_api/tests/fixtures/espn/<league>/<espn_id>/:
  statisticslog.json
  statistics_<year>_<type>.json   (one completed + one current when available)
  athlete_season_<year>.json
  v3_stats.json
  seasons_<year>.json             (league season calendar)

Usage:
  PYTHONPATH=. python3 scripts/capture_espn_fixtures.py
  PYTHONPATH=. python3 scripts/capture_espn_fixtures.py --athlete lebron
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "gravity_api" / "tests" / "fixtures" / "espn"

UA = "GravityScrapers/1.0"
SITE_HOST = "site.web.api.espn.com"
CORE_HOST = "sports.core.api.espn.com"

CORE_LEAGUE: dict[str, str] = {
    "nba": "basketball/leagues/nba",
    "nfl": "football/leagues/nfl",
    "cfb": "football/leagues/college-football",
    "ncaab_mens": "basketball/leagues/mens-college-basketball",
    "ncaab_womens": "basketball/leagues/womens-college-basketball",
    "wnba": "basketball/leagues/wnba",
}

SITE_LEAGUE: dict[str, str] = {
    "nba": "basketball/nba",
    "nfl": "football/nfl",
    "cfb": "football/college-football",
    "ncaab_mens": "basketball/mens-college-basketball",
    "ncaab_womens": "basketball/womens-college-basketball",
    "wnba": "basketball/wnba",
}

# Spec WP0 athlete set. completed/current years are ESPN path years.
ATHLETES: list[dict[str, Any]] = [
    {
        "key": "lebron",
        "name": "LeBron James",
        "league": "nba",
        "espn_id": "1966",
        "completed_year": 2026,
        "current_year": 2027,
        "season_type": 2,
    },
    {
        "key": "durant",
        "name": "Kevin Durant",
        "league": "nba",
        "espn_id": "3202",
        "completed_year": 2023,  # mid-season trade year
        "current_year": 2027,
        "season_type": 2,
    },
    {
        "key": "mahomes",
        "name": "Patrick Mahomes",
        "league": "nfl",
        "espn_id": "3139477",
        "completed_year": 2025,
        "current_year": 2026,
        "season_type": 2,
    },
    {
        "key": "will_anderson",
        "name": "Will Anderson Jr.",
        "league": "nfl",
        "espn_id": "4685724",
        "completed_year": 2025,
        "current_year": 2026,
        "season_type": 2,
    },
    {
        "key": "arch_manning",
        "name": "Arch Manning",
        "league": "cfb",
        "espn_id": "4870906",
        "completed_year": 2025,
        "current_year": 2026,
        "season_type": 2,
    },
    {
        "key": "colin_simmons",
        "name": "Colin Simmons",
        "league": "cfb",
        "espn_id": "5079689",
        "completed_year": 2025,
        "current_year": 2026,
        "season_type": 2,
    },
    {
        "key": "dybantsa_ncaab",
        "name": "AJ Dybantsa (college)",
        "league": "ncaab_mens",
        "espn_id": "5142718",
        "completed_year": 2026,
        "current_year": 2026,
        "season_type": 2,
    },
    {
        "key": "dybantsa_nba",
        "name": "AJ Dybantsa (nba)",
        "league": "nba",
        "espn_id": "5142718",
        "completed_year": 2027,
        "current_year": 2027,
        "season_type": 2,
    },
    {
        "key": "sarah_strong",
        "name": "Sarah Strong",
        "league": "ncaab_womens",
        "espn_id": "5239592",
        "completed_year": 2026,
        "current_year": 2027,
        "season_type": 2,
    },
]


def _get(url: str, *, retries: int = 3) -> tuple[dict[str, Any] | None, int, dict[str, str]]:
    """GET JSON; return (payload_or_None, status, response_headers)."""
    last_status = 0
    headers_out: dict[str, str] = {}
    for attempt in range(retries):
        req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urlopen(req, timeout=45) as resp:
                last_status = getattr(resp, "status", 200) or 200
                headers_out = {k.lower(): v for k, v in resp.headers.items()}
                raw = resp.read()
                if not raw:
                    return {}, last_status, headers_out
                return json.loads(raw.decode("utf-8")), last_status, headers_out
        except HTTPError as exc:
            last_status = int(exc.code)
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            headers_out = {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])}
            if last_status in {404, 403}:
                try:
                    return (json.loads(body) if body else {"_http_status": last_status}), last_status, headers_out
                except json.JSONDecodeError:
                    return {"_http_status": last_status, "_body": body[:2000]}, last_status, headers_out
            if attempt + 1 < retries and last_status in {429, 500, 502, 503}:
                time.sleep(1.5 * (attempt + 1))
                continue
            return {"_http_status": last_status, "_body": body[:2000]}, last_status, headers_out
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            return {"_error": str(exc)}, 0, headers_out
    return None, last_status, headers_out


def _save(path: Path, payload: Any, *, meta: dict[str, Any] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = payload
    if meta:
        # Keep raw ESPN JSON as top-level when it's a dict; attach capture meta under _capture.
        if isinstance(payload, dict):
            out = dict(payload)
            out["_capture"] = meta
        else:
            out = {"_payload": payload, "_capture": meta}
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")


def _core(league: str, path: str) -> str:
    return f"https://{CORE_HOST}/v2/sports/{CORE_LEAGUE[league]}/{path.lstrip('/')}"


def _site_v3(league: str, path: str) -> str:
    return f"https://{SITE_HOST}/apis/common/v3/sports/{SITE_LEAGUE[league]}/{path.lstrip('/')}"


def capture_athlete(spec: dict[str, Any]) -> dict[str, Any]:
    league = spec["league"]
    espn_id = str(spec["espn_id"])
    out_dir = OUT_ROOT / league / espn_id
    summary: dict[str, Any] = {"key": spec["key"], "league": league, "espn_id": espn_id, "files": {}}

    print(f"\n== {spec['name']} ({league}/{espn_id}) ==")

    # statisticslog
    url = _core(league, f"athletes/{espn_id}/statisticslog")
    data, status, hdrs = _get(url)
    _save(
        out_dir / "statisticslog.json",
        data,
        meta={"url": url, "http_status": status, "date": hdrs.get("date"), "last-modified": hdrs.get("last-modified")},
    )
    summary["files"]["statisticslog"] = status

    # v3 /stats
    url = _site_v3(league, f"athletes/{espn_id}/stats")
    data, status, hdrs = _get(url)
    _save(
        out_dir / "v3_stats.json",
        data,
        meta={"url": url, "http_status": status, "date": hdrs.get("date"), "last-modified": hdrs.get("last-modified")},
    )
    summary["files"]["v3_stats"] = status

    years = sorted({int(spec["completed_year"]), int(spec["current_year"])})
    stype = int(spec.get("season_type") or 2)

    for year in years:
        # season-scoped athlete
        url = _core(league, f"seasons/{year}/athletes/{espn_id}")
        data, status, hdrs = _get(url)
        _save(
            out_dir / f"athlete_season_{year}.json",
            data,
            meta={"url": url, "http_status": status, "date": hdrs.get("date")},
        )
        summary["files"][f"athlete_season_{year}"] = status

        # season-scoped statistics (regular)
        url = _core(league, f"seasons/{year}/types/{stype}/athletes/{espn_id}/statistics")
        data, status, hdrs = _get(url)
        # Some leagues want /statistics/0
        if status == 404:
            url0 = _core(league, f"seasons/{year}/types/{stype}/athletes/{espn_id}/statistics/0")
            data, status, hdrs = _get(url0)
            url = url0
        _save(
            out_dir / f"statistics_{year}_{stype}.json",
            data,
            meta={"url": url, "http_status": status, "date": hdrs.get("date"), "last-modified": hdrs.get("last-modified")},
        )
        summary["files"][f"statistics_{year}_{stype}"] = status

        # league season calendar
        url = _core(league, f"seasons/{year}")
        data, status, hdrs = _get(url)
        _save(
            out_dir / f"seasons_{year}.json",
            data,
            meta={"url": url, "http_status": status, "date": hdrs.get("date")},
        )
        summary["files"][f"seasons_{year}"] = status

        time.sleep(0.35)

    # Unscoped career statistics (cross-check only — never for per-season)
    url = _core(league, f"athletes/{espn_id}/statistics")
    data, status, hdrs = _get(url)
    _save(
        out_dir / "statistics_career_unscoped.json",
        data,
        meta={"url": url, "http_status": status, "note": "career/aggregate — not for season rows"},
    )
    summary["files"]["statistics_career_unscoped"] = status
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--athlete", action="append", help="Athlete key filter (repeatable)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    selected = ATHLETES
    if args.athlete:
        keys = {k.lower() for k in args.athlete}
        selected = [a for a in ATHLETES if a["key"] in keys]
        if not selected:
            print(f"No athletes matched {keys}", file=sys.stderr)
            return 2

    if args.dry_run:
        for a in selected:
            print(f"{a['key']}: {a['league']}/{a['espn_id']}")
        return 0

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    summaries = []
    for spec in selected:
        summaries.append(capture_athlete(spec))
        time.sleep(0.5)

    index_path = OUT_ROOT / "INDEX.json"
    index_path.write_text(
        json.dumps({"captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "athletes": summaries}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"\nIndex → {index_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
