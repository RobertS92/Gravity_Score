"""Tests for commercial viability scoring."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from gravity_api.services.commercial_viability import (
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
