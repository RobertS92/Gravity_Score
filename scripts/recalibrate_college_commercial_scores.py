#!/usr/bin/env python3
"""Re-map latest college commercial_viability Gravity rows after curve changes."""

from __future__ import annotations

import asyncio
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg

from gravity_api.config import get_settings
from gravity_api.feature_engineering.transforms import percentile_rank
from gravity_api.services.commercial_viability import (
    COLLEGE_BASKETBALL_SPORTS,
    COLLEGE_COMMERCIAL_SPORTS,
    _observed_nil_display_floor,
    _score_from_index_and_percentile,
    basketball_production_prominence,
    basketball_star_separation_bonus,
)
from gravity_api.services.nil_valuation import nil_from_row
from gravity_api.services.sport_percentiles import refresh_sport_percentiles


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sports",
        nargs="+",
        choices=sorted(COLLEGE_COMMERCIAL_SPORTS),
        default=sorted(COLLEGE_COMMERCIAL_SPORTS),
        help="College sports to recalibrate",
    )
    return parser


async def main() -> int:
    args = _parser().parse_args()
    conn = await asyncpg.connect(get_settings().pg_dsn, statement_cache_size=0, command_timeout=180)
    changed = 0
    by_sport: dict[str, int] = defaultdict(int)
    try:
        rows = await conn.fetch(
            """
            SELECT a.id::text AS athlete_id, a.sport, r.raw_data,
                   gs.id::text AS score_id, gs.gravity_score, gs.dollar_confidence
            FROM athletes a
            JOIN LATERAL (
                SELECT * FROM athlete_gravity_scores
                WHERE athlete_id = a.id
                ORDER BY calculated_at DESC
                LIMIT 1
            ) gs ON TRUE
            LEFT JOIN LATERAL (
                SELECT raw_data FROM raw_athlete_data
                WHERE athlete_id = a.id
                ORDER BY scraped_at DESC NULLS LAST
                LIMIT 1
            ) r ON TRUE
            WHERE a.sport = ANY($1::text[])
              AND COALESCE(a.is_active, TRUE) = TRUE
            """,
            args.sports,
        )
        by_sport_indices: dict[str, list[float]] = defaultdict(list)
        by_sport_prominence: dict[str, list[float]] = defaultdict(list)
        parsed: list[tuple[Any, dict[str, Any], dict[str, Any]]] = []
        for row in rows:
            dc = _json(row["dollar_confidence"])
            raw = _json(row["raw_data"])
            if dc.get("gravity_source") != "commercial_viability":
                continue
            idx = dc.get("commercial_viability_index")
            if idx is None:
                continue
            try:
                idx_f = float(idx)
            except (TypeError, ValueError):
                continue
            by_sport_indices[str(row["sport"])].append(idx_f)
            if str(row["sport"]) in COLLEGE_BASKETBALL_SPORTS:
                by_sport_prominence[str(row["sport"])].append(
                    basketball_production_prominence(raw, str(row["sport"]))
                )
            parsed.append((row, dc, raw))

        staged: list[tuple[str, str, str, float, str]] = []
        touched_ids: list[str] = []
        for row, dc, raw in parsed:
            sport = str(row["sport"])
            idx = float(dc["commercial_viability_index"])
            pct = percentile_rank(by_sport_indices[sport], idx) if by_sport_indices[sport] else 50.0
            score = _score_from_index_and_percentile(idx, pct, sport)
            nil_floor = _observed_nil_display_floor(nil_from_row(raw))
            if nil_floor is not None:
                score = max(score, nil_floor)
            prominence = basketball_production_prominence(raw, sport)
            prominence_pct: float | None = None
            star_bonus = 0.0
            if sport in COLLEGE_BASKETBALL_SPORTS:
                prominence_pct = percentile_rank(by_sport_prominence[sport], prominence)
                star_bonus = basketball_star_separation_bonus(prominence_pct, idx, prominence)
                score = round(min(94.0, score + star_bonus), 4)
            dc["commercial_viability_percentile"] = round(max(1.0, min(99.0, pct)), 4)
            dc["commercial_nil_market_floor"] = nil_floor
            dc["commercial_viability_score"] = score
            dc["basketball_production_prominence"] = prominence
            dc["basketball_production_prominence_percentile"] = prominence_pct
            dc["basketball_star_separation_bonus"] = star_bonus
            dc["college_commercial_recalibration"] = {
                "version": "college_cv_display_v3",
                "index": round(idx, 4),
                "percentile": dc["commercial_viability_percentile"],
                "nil_floor": nil_floor,
                "basketball_production_prominence": prominence,
                "basketball_production_prominence_percentile": prominence_pct,
                "basketball_star_separation_bonus": star_bonus,
            }
            staged.append(
                (
                    row["score_id"],
                    row["athlete_id"],
                    sport,
                    score,
                    json.dumps(dc),
                )
            )
            changed += 1
            by_sport[sport] += 1
            touched_ids.append(row["athlete_id"])

        async with conn.transaction():
            await conn.execute(
                """
                CREATE TEMP TABLE tmp_college_commercial_recalibration (
                    score_id uuid PRIMARY KEY,
                    athlete_id uuid NOT NULL,
                    sport text NOT NULL,
                    gravity_score double precision NOT NULL,
                    dollar_confidence text NOT NULL
                ) ON COMMIT DROP
                """
            )
            await conn.copy_records_to_table(
                "tmp_college_commercial_recalibration",
                records=staged,
                columns=["score_id", "athlete_id", "sport", "gravity_score", "dollar_confidence"],
            )
            await conn.execute(
                """
                UPDATE athlete_gravity_scores gs
                SET gravity_score = tmp.gravity_score,
                    dollar_confidence = tmp.dollar_confidence::jsonb
                FROM tmp_college_commercial_recalibration tmp
                WHERE gs.id = tmp.score_id
                """
            )
        if touched_ids:
            await refresh_sport_percentiles(conn, touched_ids)
    finally:
        await conn.close()
    print(json.dumps({"changed": changed, "by_sport": dict(by_sport)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
