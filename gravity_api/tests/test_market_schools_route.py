import asyncio
from unittest.mock import AsyncMock

from gravity_api.routers.market import market_schools


def test_market_schools_returns_program_gravity_scores():
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {
                "team_id": "team-1",
                "school": "State U",
                "conference": "SEC",
                "sport": "cfb",
                "avg_gravity_score": 72.3,
                "program_gravity_score": 84.8,
                "program_brand_score": 79.1,
                "program_proof_score": 81.4,
                "program_velocity_score": 73.2,
                "program_risk_score": 89.0,
                "athlete_count": 87,
                "top_athlete_name": "A. Player",
                "nil_environment_score": 66.0,
                "collective_budget_usd": 2100000.0,
            }
        ]
    )

    out = asyncio.run(market_schools(limit=1, db=conn))
    schools = out["schools"]

    assert len(schools) == 1
    assert schools[0]["team_id"] == "team-1"
    assert schools[0]["program_gravity_score"] == 84.8
    assert schools[0]["program_brand_score"] == 79.1
    assert schools[0]["program_proof_score"] == 81.4
    assert schools[0]["program_velocity_score"] == 73.2
    assert schools[0]["program_risk_score"] == 89.0
