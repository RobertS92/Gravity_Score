"""Tests for athlete_season_stats → raw enrichment."""

import asyncio
from unittest.mock import AsyncMock

from gravity_api.services.sport_pipeline.raw_stats_sync import (
    apply_ass_enrichment_to_raw,
    enrich_raw_from_athlete_season_stats,
)


def test_apply_ass_enrichment_fills_gaps_only():
    raw = {"pass_yards": 3200.0, "season_stats": {"pass_yards": 3200.0}}
    enrichment = {
        "season_stats": {"pass_yards": 2800.0, "gp": 12.0, "pass_td": 25.0},
        "games_played_season": 12,
    }
    out = apply_ass_enrichment_to_raw(raw, enrichment)
    assert out["pass_yards"] == 3200.0
    assert out["pass_td"] == 25.0
    assert out["games_played_season"] == 12
    assert out["season_stats"]["gp"] == 12.0
    assert out["season_stats"]["pass_yards"] == 3200.0


def test_apply_ass_enrichment_does_not_overwrite_richer_scraper_data():
    raw = {"games_played_season": 11, "season_stats": {"gp": 11.0, "pass_yards": 3000.0}}
    enrichment = {"games_played_season": 9, "season_stats": {"gp": 9.0}}
    out = apply_ass_enrichment_to_raw(raw, enrichment)
    assert out["games_played_season"] == 11
    assert out["season_stats"]["gp"] == 11.0


def test_enrich_raw_from_athlete_season_stats_builds_season_blob():
    async def run():
        conn = AsyncMock()
        conn.fetch = AsyncMock(
            return_value=[
                {"stat_key": "pass_yards", "stat_value": 2800.0, "games_played": 12},
                {"stat_key": "pass_td", "stat_value": 22.0, "games_played": 12},
            ]
        )
        return await enrich_raw_from_athlete_season_stats(conn, "athlete-1", "cfb")

    enrichment = asyncio.run(run())
    assert enrichment["games_played_season"] == 12
    assert enrichment["season_stats"]["pass_yards"] == 2800.0
    assert enrichment["season_stats"]["gp"] == 12.0
