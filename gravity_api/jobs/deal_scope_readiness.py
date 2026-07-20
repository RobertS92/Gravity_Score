"""Report governed transaction counts and calibration readiness by deal scope."""

from __future__ import annotations

import argparse
import asyncio
import json

import asyncpg

from gravity_api.config import get_settings
from gravity_api.services.deal_scope_pricing import DEAL_SCOPES


async def readiness(conn: asyncpg.Connection) -> dict[str, object]:
    rows = await conn.fetch(
        """SELECT deal_scope::text AS deal_scope,
                  COUNT(*)::int AS qualified_transactions,
                  COUNT(DISTINCT athlete_id)::int AS unique_athletes,
                  MIN(deal_date) AS earliest_deal,
                  MAX(deal_date) AS latest_deal
           FROM verified_deal_transactions
           WHERE retracted_at IS NULL
           GROUP BY deal_scope"""
    )
    by_scope = {str(row["deal_scope"]): dict(row) for row in rows}
    output: dict[str, object] = {}
    for scope in DEAL_SCOPES:
        row = by_scope.get(scope, {})
        count = int(row.get("qualified_transactions") or 0)
        output[scope] = {
            "qualified_transactions": count,
            "unique_athletes": int(row.get("unique_athletes") or 0),
            "earliest_deal": str(row.get("earliest_deal")) if row.get("earliest_deal") else None,
            "latest_deal": str(row.get("latest_deal")) if row.get("latest_deal") else None,
            "minimum_gap": max(0, 100 - count),
            "preferred_gap": max(0, 300 - count),
            "status": "production_candidate" if count >= 300 else "pilot_candidate" if count >= 100 else "insufficient_data",
        }
    return output


async def main() -> None:
    settings = get_settings()
    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        print(json.dumps(await readiness(conn), indent=2, default=str))
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.parse_args()
    asyncio.run(main())
