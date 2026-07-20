#!/usr/bin/env python3
"""Score the 54-player NFL heat-check panel from live DB scores."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg

PANEL: list[dict[str, str]] = [
    # QB
    {"group": "QB", "tier": "Star", "name": "Patrick Mahomes", "team": "Chiefs"},
    {"group": "QB", "tier": "Star", "name": "Josh Allen", "team": "Bills"},
    {"group": "QB", "tier": "Elite", "name": "Lamar Jackson", "team": "Ravens"},
    {"group": "QB", "tier": "Elite", "name": "Joe Burrow", "team": "Bengals"},
    {"group": "QB", "tier": "Starter", "name": "Trevor Lawrence", "team": "Jaguars"},
    {"group": "QB", "tier": "Starter", "name": "Kirk Cousins", "team": "Falcons"},
    # RB
    {"group": "RB", "tier": "Star", "name": "Christian McCaffrey", "team": "49ers"},
    {"group": "RB", "tier": "Star", "name": "Saquon Barkley", "team": "Eagles"},
    {"group": "RB", "tier": "Elite", "name": "Derrick Henry", "team": "Ravens"},
    {"group": "RB", "tier": "Elite", "name": "Jonathan Taylor", "team": "Colts"},
    {"group": "RB", "tier": "Starter", "name": "Kenneth Walker III", "team": "Seahawks"},
    {"group": "RB", "tier": "Starter", "name": "James Conner", "team": "Cardinals"},
    # WR
    {"group": "WR", "tier": "Star", "name": "Justin Jefferson", "team": "Vikings"},
    {"group": "WR", "tier": "Star", "name": "Tyreek Hill", "team": "Dolphins"},
    {"group": "WR", "tier": "Elite", "name": "CeeDee Lamb", "team": "Cowboys"},
    {"group": "WR", "tier": "Elite", "name": "Amon-Ra St. Brown", "team": "Lions"},
    {"group": "WR", "tier": "Starter", "name": "Courtland Sutton", "team": "Broncos"},
    {"group": "WR", "tier": "Starter", "name": "DJ Moore", "team": "Bears"},
    # TE
    {"group": "TE", "tier": "Star", "name": "Travis Kelce", "team": "Chiefs"},
    {"group": "TE", "tier": "Star", "name": "Trey McBride", "team": "Cardinals"},
    {"group": "TE", "tier": "Elite", "name": "George Kittle", "team": "49ers"},
    {"group": "TE", "tier": "Elite", "name": "Mark Andrews", "team": "Ravens"},
    {"group": "TE", "tier": "Starter", "name": "David Njoku", "team": "Browns"},
    {"group": "TE", "tier": "Starter", "name": "Evan Engram", "team": "Jaguars"},
    # OL
    {"group": "OL", "tier": "Star", "name": "Trent Williams", "team": "49ers"},
    {"group": "OL", "tier": "Star", "name": "Lane Johnson", "team": "Eagles"},
    {"group": "OL", "tier": "Elite", "name": "Chris Lindstrom", "team": "Falcons"},
    {"group": "OL", "tier": "Elite", "name": "Quenton Nelson", "team": "Colts"},
    {"group": "OL", "tier": "Starter", "name": "Tyler Linderbaum", "team": "Ravens"},
    {"group": "OL", "tier": "Starter", "name": "Tyler Smith", "team": "Cowboys"},
    # DL
    {"group": "DL", "tier": "Star", "name": "Myles Garrett", "team": "Browns"},
    {"group": "DL", "tier": "Star", "name": "Micah Parsons", "team": "Cowboys"},
    {"group": "DL", "tier": "Elite", "name": "Maxx Crosby", "team": "Raiders"},
    {"group": "DL", "tier": "Elite", "name": "Nick Bosa", "team": "49ers"},
    {"group": "DL", "tier": "Starter", "name": "Will Anderson Jr.", "team": "Texans"},
    {"group": "DL", "tier": "Starter", "name": "Montez Sweat", "team": "Bears"},
    # LB
    {"group": "LB", "tier": "Star", "name": "T.J. Watt", "team": "Steelers"},
    {"group": "LB", "tier": "Star", "name": "Fred Warner", "team": "49ers"},
    {"group": "LB", "tier": "Elite", "name": "Roquan Smith", "team": "Ravens"},
    {"group": "LB", "tier": "Elite", "name": "Devin Lloyd", "team": "Jaguars"},
    {"group": "LB", "tier": "Starter", "name": "Zaire Franklin", "team": "Colts"},
    {"group": "LB", "tier": "Starter", "name": "Jerome Baker", "team": "Seahawks"},
    # DB
    {"group": "DB", "tier": "Star", "name": "Patrick Surtain II", "team": "Broncos"},
    {"group": "DB", "tier": "Star", "name": "Sauce Gardner", "team": "Jets"},
    {"group": "DB", "tier": "Elite", "name": "Minkah Fitzpatrick", "team": "Steelers"},
    {"group": "DB", "tier": "Elite", "name": "Jalen Ramsey", "team": "Dolphins"},
    {"group": "DB", "tier": "Starter", "name": "L'Jarius Sneed", "team": "Titans"},
    {"group": "DB", "tier": "Starter", "name": "Brian Branch", "team": "Lions"},
    # K
    {"group": "K", "tier": "Star", "name": "Harrison Butker", "team": "Chiefs"},
    {"group": "K", "tier": "Star", "name": "Justin Tucker", "team": "Ravens"},
    {"group": "K", "tier": "Elite", "name": "Evan McPherson", "team": "Bengals"},
    {"group": "K", "tier": "Elite", "name": "Jake Elliott", "team": "Eagles"},
    {"group": "K", "tier": "Starter", "name": "Brandon McManus", "team": "Packers"},
    {"group": "K", "tier": "Starter", "name": "Wil Lutz", "team": "Jaguars"},
]


def _team_match(db_team: str | None, hint: str) -> bool:
    if not db_team:
        return False
    t = db_team.lower()
    h = hint.lower()
    aliases = {
        "chiefs": ["kansas city", "chiefs"],
        "bills": ["buffalo", "bills"],
        "ravens": ["baltimore", "ravens"],
        "bengals": ["cincinnati", "bengals"],
        "jaguars": ["jacksonville", "jaguars"],
        "falcons": ["atlanta", "falcons"],
        "49ers": ["san francisco", "49ers"],
        "eagles": ["philadelphia", "eagles"],
        "colts": ["indianapolis", "colts"],
        "seahawks": ["seattle", "seahawks"],
        "cardinals": ["arizona", "cardinals"],
        "vikings": ["minnesota", "vikings"],
        "dolphins": ["miami", "dolphins"],
        "cowboys": ["dallas", "cowboys"],
        "lions": ["detroit", "lions"],
        "broncos": ["denver", "broncos"],
        "bears": ["chicago", "bears"],
        "browns": ["cleveland", "browns"],
        "raiders": ["las vegas", "raiders"],
        "texans": ["houston", "texans"],
        "steelers": ["pittsburgh", "steelers"],
        "jets": ["new york jets", "jets"],
        "titans": ["tennessee", "titans"],
        "packers": ["green bay", "packers"],
    }
    for token in aliases.get(h, [h]):
        if token in t:
            return True
    return h in t


async def main() -> int:
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        print(json.dumps({"error": "PG_DSN not configured"}))
        return 1

    conn = await asyncpg.connect(dsn, command_timeout=120)
    results: list[dict] = []
    missing: list[dict] = []

    try:
        for entry in PANEL:
            name = entry["name"]
            rows = await conn.fetch(
                """
                SELECT a.id::text AS athlete_id, a.name, a.position, a.school AS team
                FROM athletes a
                WHERE a.sport = 'nfl'
                  AND COALESCE(a.is_active, TRUE)
                  AND lower(a.name) = lower($1)
                ORDER BY a.updated_at DESC NULLS LAST
                """,
                name,
            )
            athlete = None
            for row in rows:
                if _team_match(row["team"], entry["team"]):
                    athlete = row
                    break
            if athlete is None and rows:
                athlete = rows[0]

            if not athlete:
                missing.append(entry)
                continue

            score = await conn.fetchrow(
                """
                SELECT gravity_score, brand_score, proof_score, proximity_score,
                       velocity_score, risk_score, model_version, calculated_at
                FROM athlete_gravity_scores
                WHERE athlete_id = $1::uuid
                ORDER BY calculated_at DESC NULLS LAST
                LIMIT 1
                """,
                athlete["athlete_id"],
            )
            if not score:
                missing.append({**entry, "reason": "no score row"})
                continue

            results.append(
                {
                    **entry,
                    "player": athlete["name"],
                    "position": athlete["position"],
                    "team": athlete["team"],
                    "gravity_score": float(score["gravity_score"]),
                    "brand": float(score["brand_score"] or 0),
                    "proof": float(score["proof_score"] or 0),
                    "proximity": float(score["proximity_score"] or 0),
                    "velocity": float(score["velocity_score"] or 0),
                    "risk": float(score["risk_score"] or 0),
                    "model_version": score["model_version"],
                }
            )
    finally:
        await conn.close()

    out = {"scored": results, "missing": missing, "n_scored": len(results), "n_missing": len(missing)}
    print(json.dumps(out, indent=2))
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
