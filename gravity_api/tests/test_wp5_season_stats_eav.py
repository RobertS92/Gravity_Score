"""WP5: EAV grain writer + counting catalog."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from gravity_api.scrapers.parsers.stat_catalog import (
    derive_rates,
    is_counting,
    stat_key_info_for_sport,
)
from gravity_api.scrapers.types import SeasonStatLine
from gravity_api.services.sport_pipeline.season_stats_store import (
    upsert_season_stat_lines,
)


def test_is_counting_marks_rates_false():
    assert is_counting("pass_yards") is True
    assert is_counting("sacks") is True
    assert is_counting("gp") is True
    assert is_counting("fg_pct") is False
    assert is_counting("pass_yards_per_attempt") is False
    assert is_counting("passer_rating") is False
    assert is_counting("pass_long") is False


def test_stat_key_info_includes_is_counting():
    info = stat_key_info_for_sport("nba")
    assert info["pts"].is_counting is True
    assert info["fg_pct"].is_counting is False


def test_derive_rates_from_counts():
    rates = derive_rates(
        "nba",
        {"pts": 2000.0, "gp": 80.0, "fgm": 400.0, "fga": 1000.0},
    )
    assert rates["ppg"] == 25.0
    assert rates["fg_pct"] == 0.4


@pytest.mark.asyncio
async def test_upsert_season_stat_lines_writes_eav_and_team_season():
    conn = MagicMock()
    conn.execute = AsyncMock(return_value="OK")
    # asyncpg transaction context manager
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=tx)

    lines = [
        SeasonStatLine(
            league="nba",
            season_year=2024,
            season_type="regular",
            team_id="13",
            team_name="Lakers",
            is_total=False,
            stats={"pts": 2000.0, "gp": 70.0},
            source_key="espn.core.statistics",
            source_url="https://example.test/stats",
            stats_as_of=datetime(2024, 6, 1, tzinfo=timezone.utc),
        ),
        SeasonStatLine(
            league="nba",
            season_year=2024,
            season_type="regular",
            team_id="TOT",
            team_name=None,
            is_total=True,
            stats={"pts": 2000.0, "gp": 70.0},
            source_key="espn.core.statistics",
            source_url="https://example.test/stats",
            stats_as_of=datetime(2024, 6, 1, tzinfo=timezone.utc),
        ),
    ]

    written = await upsert_season_stat_lines(
        conn,
        "00000000-0000-0000-0000-000000000001",
        lines,
        position="G",
        sport="nba",
    )
    assert written >= 1
    # At least one athlete_team_seasons upsert for the non-TOT line.
    sqls = [c.args[0] for c in conn.execute.await_args_list]
    assert any("athlete_season_stats" in s for s in sqls)
    assert any("athlete_team_seasons" in s for s in sqls)
    assert any("team_id" in s and "season_type" in s for s in sqls)
