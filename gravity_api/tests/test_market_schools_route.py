import asyncio
from unittest.mock import AsyncMock

from gravity_api.routers.market import market_schools


def test_market_schools_returns_program_gravity_scores():
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "school": "State U",
                    "conference": "SEC",
                    "sport": "cfb",
                    "avg_gravity_score": 72.3,
                    "athlete_count": 87,
                    "top_athlete_name": "A. Player",
                    "nil_environment_score": 66.0,
                    "collective_budget_usd": 2100000.0,
                }
            ],
            [
                {
                    "team_id": "team-1",
                    "school_name": "State U",
                    "sport": "cfb",
                    "gravity_score": 84.8,
                    "brand_score": 79.1,
                    "proof_score": 81.4,
                    "velocity_score": 73.2,
                    "risk_score": 11.0,
                    "scored_at": "2026-05-10T00:00:00Z",
                }
            ],
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


def test_market_schools_maps_mcbb_programs_to_team_scores():
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "school": "State U",
                    "conference": "Big 12",
                    "sport": "mcbb",
                    "avg_gravity_score": 71.0,
                    "athlete_count": 16,
                    "top_athlete_name": "B. Hooper",
                    "nil_environment_score": 60.0,
                    "collective_budget_usd": None,
                }
            ],
            [
                {
                    "team_id": "team-mbb",
                    "school_name": "State U",
                    "sport": "ncaab_mens",
                    "gravity_score": 83.3,
                    "brand_score": 78.0,
                    "proof_score": 80.0,
                    "velocity_score": 72.0,
                    "risk_score": 22.0,
                    "scored_at": "2026-05-11T00:00:00Z",
                }
            ],
        ]
    )

    out = asyncio.run(market_schools(limit=1, db=conn))
    schools = out["schools"]

    assert len(schools) == 1
    assert schools[0]["team_id"] == "team-mbb"
    assert schools[0]["sport"] == "mcbb"
    assert schools[0]["program_gravity_score"] == 83.3


def test_market_schools_uses_athlete_nil_estimate_when_budget_missing():
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "school": "Estimate U",
                    "conference": "ACC",
                    "sport": "cfb",
                    "avg_gravity_score": 68.0,
                    "athlete_count": 12,
                    "top_athlete_name": "C. Prospect",
                    "nil_environment_score": 88.0,
                    "collective_budget_usd": None,
                    "athlete_nil_market_estimate": 1850000.0,
                }
            ],
            [],
        ]
    )

    out = asyncio.run(market_schools(limit=1, db=conn))
    schools = out["schools"]

    assert len(schools) == 1
    assert schools[0]["nil_market_size_estimate"] == 1850000.0
