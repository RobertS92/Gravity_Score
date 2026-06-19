import asyncio
from unittest.mock import AsyncMock

from gravity_api.routers.market import market_schools


def test_market_schools_returns_program_gravity_scores():
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "program_id": "program-1",
                    "school": "State U",
                    "conference": "SEC",
                    "sport": "cfb",
                    "nil_environment_score": 66.0,
                    "collective_budget_usd": 2100000.0,
                }
            ],
            [
                {
                    "school": "State U",
                    "sport": "cfb",
                    "avg_gravity_score": 72.3,
                    "athlete_count": 87,
                    "top_athlete_name": "A. Player",
                    "athlete_nil_market_estimate": 1800000.0,
                }
            ],
            [
                {
                    "team_id": "team-1",
                    "matched_team_id": "team-1",
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
    athlete_aggregate_sql = conn.fetch.await_args_list[1].args[0]
    assert "a.nil_valuation_raw" not in athlete_aggregate_sql
    assert "to_jsonb(a) -> 'nil_valuation_raw'" in athlete_aggregate_sql


def test_market_schools_maps_mcbb_programs_to_team_scores():
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "program_id": "program-mbb",
                    "school": "State U",
                    "conference": "Big 12",
                    "sport": "mcbb",
                    "nil_environment_score": 60.0,
                    "collective_budget_usd": None,
                }
            ],
            [
                {
                    "school": "State U",
                    "sport": "mcbb",
                    "avg_gravity_score": 71.0,
                    "athlete_count": 16,
                    "top_athlete_name": "B. Hooper",
                    "athlete_nil_market_estimate": 900000.0,
                }
            ],
            [
                {
                    "team_id": "team-mbb",
                    "matched_team_id": "team-mbb",
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
                    "program_id": "program-estimate",
                    "school": "Estimate U",
                    "conference": "ACC",
                    "sport": "cfb",
                    "nil_environment_score": 88.0,
                    "collective_budget_usd": None,
                }
            ],
            [
                {
                    "school": "Estimate U",
                    "sport": "cfb",
                    "avg_gravity_score": 68.0,
                    "athlete_count": 12,
                    "top_athlete_name": "C. Prospect",
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


def test_market_schools_falls_back_to_avg_gravity_when_team_score_missing():
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "program_id": "program-fallback",
                    "school": "Fallback U",
                    "conference": "ACC",
                    "sport": "cfb",
                    "nil_environment_score": None,
                    "collective_budget_usd": None,
                }
            ],
            [
                {
                    "school": "Fallback U",
                    "sport": "cfb",
                    "avg_gravity_score": 69.1,
                    "athlete_count": 10,
                    "top_athlete_name": "D. Athlete",
                    "athlete_nil_market_estimate": 1200000.0,
                }
            ],
            [],
        ]
    )

    out = asyncio.run(market_schools(limit=1, db=conn))
    schools = out["schools"]

    assert len(schools) == 1
    assert schools[0]["program_gravity_score"] == 69.1


def test_market_schools_uses_program_id_when_team_join_is_missing():
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "program_id": "program-cfb-1",
                    "school": "Program Id U",
                    "conference": "SEC",
                    "sport": "CFB",
                    "nil_environment_score": 70.0,
                    "collective_budget_usd": None,
                }
            ],
            [
                {
                    "school": "Program Id U",
                    "sport": "cfb",
                    "avg_gravity_score": None,
                    "avg_program_gravity_score": None,
                    "athlete_count": 8,
                    "top_athlete_name": "E. Prospect",
                    "athlete_nil_market_estimate": 650000.0,
                }
            ],
            [
                {
                    "team_id": "program-cfb-1",
                    "matched_team_id": None,
                    "school_name": None,
                    "sport": None,
                    "gravity_score": 82.5,
                    "brand_score": 77.4,
                    "proof_score": 75.3,
                    "velocity_score": 71.2,
                    "risk_score": 19.0,
                    "scored_at": "2026-05-12T00:00:00Z",
                }
            ],
        ]
    )

    out = asyncio.run(market_schools(limit=1, db=conn))
    schools = out["schools"]

    assert len(schools) == 1
    assert schools[0]["team_id"] is None
    assert schools[0]["program_gravity_score"] == 82.5


def test_market_schools_falls_back_to_athlete_program_gravity_average():
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "program_id": "program-avg",
                    "school": "Signal U",
                    "conference": "ACC",
                    "sport": "cfb",
                    "nil_environment_score": 55.0,
                    "collective_budget_usd": None,
                }
            ],
            [
                {
                    "school": "Signal U",
                    "sport": "cfb",
                    "avg_gravity_score": None,
                    "avg_program_gravity_score": 74.4,
                    "athlete_count": 5,
                    "top_athlete_name": "F. Signal",
                    "athlete_nil_market_estimate": 500000.0,
                }
            ],
            [],
        ]
    )

    out = asyncio.run(market_schools(limit=1, db=conn))
    schools = out["schools"]

    assert len(schools) == 1
    assert schools[0]["avg_gravity_score"] == 74.4
    assert schools[0]["program_gravity_score"] == 74.4
