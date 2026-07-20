"""Tests for commercial viability scoring."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from gravity_api.services.commercial_viability import (
    basketball_production_prominence,
    basketball_star_separation_bonus,
    compute_college_commercial_viability,
    compute_commercial_viability_index,
)


def test_commercial_viability_index_increases_with_signals():
    low = compute_commercial_viability_index({"recruiting_stars": 2})
    high = compute_commercial_viability_index(
        {
            "recruiting_stars": 5,
            "instagram_followers": 500_000,
            "nil_valuation": 2_000_000,
            "nil_valuation_observed": 1,
        }
    )
    assert high > low
    assert 0 <= high <= 100


def test_commercial_viability_percentile_capped_1_to_99():
    async def run():
        conn = AsyncMock()
        conn.fetch = AsyncMock(
            return_value=[
                {"raw_data": {"recruiting_stars": 3, "instagram_followers": 10_000}},
                {"raw_data": {"recruiting_stars": 4, "instagram_followers": 50_000}},
                {"raw_data": {"recruiting_stars": 5, "instagram_followers": 1_000_000}},
            ]
        )
        raw = {
            "recruiting_stars": 5,
            "instagram_followers": 2_000_000,
            "nil_valuation": 5_000_000,
            "nil_valuation_observed": 1,
        }
        return await compute_college_commercial_viability(conn, "a1", "cfb", raw)

    result = asyncio.run(run())
    assert 1 <= result["commercial_viability_score"] <= 99
    assert result["nil_signal_source"] == "observed"
    assert result["nil_dollar_p50"] == pytest.approx(5_000_000.0)


def test_commercial_viability_handles_json_string_raw_data():
    async def run():
        conn = AsyncMock()
        conn.fetch = AsyncMock(
            return_value=[
                {"raw_data": '{"recruiting_stars": 3, "instagram_followers": 10000}'},
                {"raw_data": {"recruiting_stars": 5, "instagram_followers": 500000}},
            ]
        )
        raw = {"recruiting_stars": 4, "instagram_followers": 100_000}
        return await compute_college_commercial_viability(conn, "a1", "cfb", raw)

    result = asyncio.run(run())
    assert 1 <= result["commercial_viability_score"] <= 99


def test_commercial_viability_estimated_nil_when_unobserved():
    async def run():
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        raw = {"recruiting_stars": 4, "instagram_followers": 200_000}
        return await compute_college_commercial_viability(conn, "a1", "cfb", raw)

    result = asyncio.run(run())
    assert result["nil_signal_source"] == "estimated"
    assert result["nil_dollar_p50"] > 25_000


def test_commercial_viability_score_spreads_not_ceiling():
    """Depth players must not all land at G≈99 via pure percentile."""
    async def run():
        # Left-skewed cohort: most athletes share a similar mid index.
        peers = [
            {"raw_data": {"recruiting_stars": 3, "instagram_followers": 5_000}}
            for _ in range(40)
        ] + [
            {"raw_data": {"recruiting_stars": 4, "instagram_followers": 20_000}},
            {"raw_data": {"recruiting_stars": 5, "instagram_followers": 80_000}},
        ]
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=peers)
        depth = await compute_college_commercial_viability(
            conn,
            "depth",
            "cfb",
            {"recruiting_stars": 3, "instagram_followers": 8_000},
        )
        star = await compute_college_commercial_viability(
            conn,
            "star",
            "cfb",
            {
                "recruiting_stars": 5,
                "instagram_followers": 1_500_000,
                "nil_valuation": 3_000_000,
                "nil_valuation_observed": 1,
                "proof_performance_index_pctile": 92,
            },
        )
        return depth, star

    depth, star = asyncio.run(run())
    assert depth["commercial_viability_score"] < 90
    assert star["commercial_viability_score"] > depth["commercial_viability_score"]
    assert star["commercial_viability_score"] <= 99


def test_college_gravity_uses_observed_nil_market_floor():
    async def run():
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        return await compute_college_commercial_viability(
            conn,
            "jeremiah-smith-like",
            "cfb",
            {
                "instagram_followers": 3_000,
                "twitter_followers": 1_050,
                "nil_valuation": 16_743_000,
                "nil_valuation_observed": 1,
                "proof_performance_index_pctile": 86,
            },
        )

    result = asyncio.run(run())
    assert 80 <= result["commercial_viability_score"] <= 82
    assert result["commercial_viability_score"] >= result["commercial_nil_market_floor"]


def test_college_observed_nil_floor_ramps_through_very_rare_band():
    async def run():
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        return await compute_college_commercial_viability(
            conn,
            "colin-simmons-like",
            "cfb",
            {
                "recruiting_stars": 5,
                "instagram_followers": 4_000,
                "nil_valuation": 10_440_000,
                "nil_valuation_observed": 1,
            },
        )

    result = asyncio.run(run())
    assert 75 <= result["commercial_viability_score"] < 80


def test_college_mega_nil_and_index_can_remain_extreme():
    async def run():
        conn = AsyncMock()
        conn.fetch = AsyncMock(
            return_value=[
                {"raw_data": {"recruiting_stars": 3, "instagram_followers": 5_000}}
                for _ in range(100)
            ]
        )
        return await compute_college_commercial_viability(
            conn,
            "arch-manning-like",
            "cfb",
            {
                "recruiting_stars": 5,
                "instagram_followers": 622_000,
                "twitter_followers": 90_000,
                "nil_valuation": 21_866_000,
                "nil_valuation_observed": 1,
                "proof_performance_index_pctile": 95,
            },
        )

    result = asyncio.run(run())
    assert 85 <= result["commercial_viability_score"] <= 94
    assert result["commercial_viability_score"] >= result["commercial_nil_market_floor"]


def test_low_signal_college_player_lands_in_active_roster_middle():
    async def run():
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[{"raw_data": {"recruiting_stars": 2}} for _ in range(9)])
        return await compute_college_commercial_viability(
            conn,
            "ordinary-active-player",
            "ncaab_mens",
            {"recruiting_stars": 2},
        )

    result = asyncio.run(run())
    assert 50 <= result["commercial_viability_score"] <= 65


def test_basketball_production_prominence_separates_true_stars():
    depth = basketball_production_prominence(
        {"gp": 30, "pts": 150, "reb": 60, "ast": 30, "stl": 12, "blk": 3},
        "ncaab_mens",
    )
    star = basketball_production_prominence(
        {"gp": 30, "pts": 750, "reb": 210, "ast": 150, "stl": 75, "blk": 30},
        "ncaab_mens",
    )
    assert star > depth
    assert basketball_production_prominence({"gp": 2, "pts": 60}, "ncaab_mens") == 0
    assert basketball_production_prominence({"gp": 30, "pts": 750}, "cfb") == 0


def test_basketball_star_bonus_only_moves_elite_upper_tail():
    assert basketball_star_separation_bonus(95.0, 45.0) == 0
    assert basketball_star_separation_bonus(98.0, 45.0) == pytest.approx(1.8)
    assert basketball_star_separation_bonus(100.0, 45.0) == pytest.approx(13.0)
    assert basketball_star_separation_bonus(95.0, 50.0) == pytest.approx(1.25)
