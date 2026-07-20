#!/usr/bin/env python3
"""Apply global-Gravity calibration only to the verify panel's latest rows."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg

from gravity_api.config import get_settings
from gravity_api.services.global_scores import calibrate_global_commercial_score
from gravity_api.services.sport_percentiles import refresh_sport_percentiles

PANEL_PATH = ROOT / "reports" / "key_athlete_verify_panel.json"


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


async def main() -> int:
    panel = json.loads(PANEL_PATH.read_text(encoding="utf-8"))
    athletes = [row for rows in panel["sports"].values() for row in rows]
    ids = [row["id"] for row in athletes]
    conn = await asyncpg.connect(get_settings().pg_dsn, statement_cache_size=0)
    changed = 0
    try:
        rows = await conn.fetch(
            """
            SELECT a.id::text, a.sport,
                   r.raw_data,
                   ss.instagram_followers, ss.tiktok_followers, ss.twitter_followers,
                   gs.id::text AS score_id, gs.brand_score, gs.dollar_confidence,
                   l.value_usd, l.label_type, l.confidence, l.source
            FROM athletes a
            JOIN LATERAL (
                SELECT * FROM athlete_gravity_scores
                WHERE athlete_id=a.id ORDER BY calculated_at DESC LIMIT 1
            ) gs ON TRUE
            LEFT JOIN LATERAL (
                SELECT raw_data FROM raw_athlete_data
                WHERE athlete_id=a.id ORDER BY scraped_at DESC LIMIT 1
            ) r ON TRUE
            LEFT JOIN LATERAL (
                SELECT * FROM social_snapshots
                WHERE athlete_id=a.id ORDER BY scraped_at DESC LIMIT 1
            ) ss ON TRUE
            LEFT JOIN LATERAL (
                SELECT * FROM athlete_value_labels
                WHERE athlete_id=a.id AND value_usd > 0
                ORDER BY confidence DESC NULLS LAST, value_usd DESC LIMIT 1
            ) l ON TRUE
            WHERE a.id=ANY($1::uuid[])
            """,
            ids,
        )
        async with conn.transaction():
            for row in rows:
                raw = _json(row["raw_data"])
                for key in ("instagram_followers", "tiktok_followers", "twitter_followers"):
                    value = row[key]
                    if value and not raw.get(key):
                        raw[key] = int(value)
                if row["value_usd"]:
                    raw.update(
                        {
                            "observed_market_value_usd": float(row["value_usd"]),
                            "observed_market_value_type": row["label_type"],
                            "observed_market_value_confidence": float(row["confidence"] or 0.8),
                            "observed_market_value_source": row["source"],
                        }
                    )
                dc = _json(row["dollar_confidence"])
                score, audit = calibrate_global_commercial_score(
                    {
                        "brand_score": float(row["brand_score"] or 55.0),
                        "dollar_confidence": dc,
                    },
                    raw,
                    str(row["sport"]),
                )
                dc["global_commercial_calibration"] = audit
                await conn.execute(
                    """
                    UPDATE athlete_gravity_scores
                    SET gravity_score=$2, dollar_confidence=$3::jsonb
                    WHERE id=$1::uuid
                    """,
                    row["score_id"],
                    score,
                    json.dumps(dc),
                )
                changed += 1
        await refresh_sport_percentiles(conn, ids)
    finally:
        await conn.close()
    print(f"recalibrated {changed} verify-panel rows")
    return 0 if changed == len(ids) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
