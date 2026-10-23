"""WP4 acceptance: no invented GP; no scoring-anchor relabel of prior seasons."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from gravity_api.scrapers.parsers.stat_normalizer import merge_stat_layers
from gravity_api.scrapers.season_calendar import current_season_year
import importlib

season_stats_mod = importlib.import_module(
    "gravity_api.services.sport_pipeline.season_stats"
)


def test_merge_stat_layers_does_not_invent_gp():
    fields = merge_stat_layers(
        "cfb",
        current={"passingYards": 1200, "passingTouchdowns": 10},
    )
    assert fields.get("games_played_season") is None
    assert fields.get("gp") is None
    assert "pass_yards" in fields or "season_stats" in fields


def test_cfb_current_year_on_2026_10_22_is_2026():
    assert current_season_year("cfb", date(2026, 10, 22)) == 2026


@pytest.mark.asyncio
async def test_only_2025_history_writes_zero_2026_rows(monkeypatch):
    """Athlete with only 2025 data on 2026-10-22 (CFB) → one 2025 set, zero 2026."""
    written_years: list[int] = []

    fake_conn = MagicMock()

    async def fake_execute(sql, *args):
        # args layout from _write_eav: athlete_id, sport, league, year, ...
        if len(args) >= 4 and isinstance(args[3], int):
            written_years.append(int(args[3]))
        return "OK"

    fake_conn.execute = AsyncMock(side_effect=fake_execute)

    monkeypatch.setattr(
        season_stats_mod,
        "current_season_year",
        lambda sport, on: 2026,
    )
    # Skip wide-table side path.
    monkeypatch.setattr(
        season_stats_mod,
        "datetime",
        MagicMock(now=MagicMock(return_value=MagicMock(date=MagicMock(return_value=date(2026, 10, 22))))),
    )

    raw = {
        "season_stats_history": {
            "2025": {
                "passingYards": 2500.0,
                "passingTouchdowns": 20.0,
                "gamesPlayed": 12.0,
            }
        },
        "stats_source": "espn_history",
    }

    # Position must map to a valid group for cfb QB-ish; use QB.
    count = await season_stats_mod.upsert_season_stats_from_raw(
        fake_conn,
        athlete_id="00000000-0000-0000-0000-000000000001",
        sport="cfb",
        position="QB",
        raw=raw,
    )

    years = sorted(set(written_years))
    assert 2025 in years
    assert 2026 not in years
    assert count >= 1
