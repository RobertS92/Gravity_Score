"""Observed commercial market-value anchors for athlete scoring."""

from __future__ import annotations

from typing import Any

import asyncpg


EXPECTED_LABEL_TYPE: dict[str, str] = {
    "nfl": "contract_apy",
    "nba": "salary_annual",
    "wnba": "salary_annual",
}


async def enrich_raw_with_market_value_anchor(
    conn: asyncpg.Connection,
    athlete_id: str,
    sport: str,
    raw: dict[str, Any],
) -> dict[str, Any]:
    """Attach the best observed APY/salary label without persisting it to raw.

    Labels are authoritative commercial observations and should anchor model
    inference. They remain request-scoped so derived training features cannot
    accidentally leak the target back into future model training exports.
    """
    label_type = EXPECTED_LABEL_TYPE.get((sport or "").lower())
    if not label_type:
        return raw

    row = await conn.fetchrow(
        """SELECT value_usd, label_type, confidence, source
           FROM athlete_value_labels
           WHERE athlete_id = $1::uuid
             AND label_type = $2
             AND value_usd > 0
           ORDER BY confidence DESC NULLS LAST, value_usd DESC
           LIMIT 1""",
        athlete_id,
        label_type,
    )
    if not row:
        return raw

    out = dict(raw)
    out["observed_market_value_usd"] = float(row["value_usd"])
    out["observed_market_value_type"] = str(row["label_type"])
    out["observed_market_value_confidence"] = float(row["confidence"] or 0.8)
    out["observed_market_value_source"] = str(row["source"] or "athlete_value_labels")
    return out


__all__ = ["EXPECTED_LABEL_TYPE", "enrich_raw_with_market_value_anchor"]
