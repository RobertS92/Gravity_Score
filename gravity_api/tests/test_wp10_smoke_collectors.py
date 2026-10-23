"""Unit tests for WP10 + season-history smoke collectors (fixture/offline)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gravity_api.scraper_smoke.athletes import SmokeAthlete
from gravity_api.scraper_smoke.wp10_season_history import (
    _line_to_history_blob,
    collect_wp10_games,
)
from gravity_api.scrapers.clients.espn_games import EspnGamesClient
from gravity_api.scrapers.types import SeasonStatLine

ROOT = Path(__file__).resolve().parents[1]
BOX_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "espn"
    / "ncaab_mens"
    / "box_score_sample.json"
)


def test_line_to_history_blob_has_provenance():
    line = SeasonStatLine(
        league="nba",
        season_year=2026,
        season_type="regular",
        team_id="TOT",
        team_name="LAL",
        is_total=True,
        stats={"general.points": 1800.0, "general.gamesPlayed": 70.0},
        source_key="espn_core",
        source_url="https://example.test/stats",
        stats_as_of=datetime(2026, 6, 27, tzinfo=timezone.utc),
    )
    blob = _line_to_history_blob(line, "nba")
    assert blob["season_year"] == 2026
    assert blob["season_label"] == "2025-26"
    assert blob["season_type"] == "regular"
    assert blob["team_id"] == "TOT"
    assert blob["team_name"] == "LAL"
    assert blob["is_total"] is True
    assert blob["stats_as_of"]
    assert "T" in str(blob["stats_as_of"])  # ISO timestamp, not season label
    assert blob["stats_as_of"] != "2026"
    assert blob["stats_as_of"] != "2025-26"


def test_parse_eventlog_game_ids_played_only():
    payload = {
        "events": {
            "items": [
                {
                    "played": False,
                    "event": {
                        "$ref": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/111"
                    },
                },
                {
                    "played": True,
                    "event": {
                        "$ref": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/222"
                    },
                },
                {
                    "played": True,
                    "statistics": {},
                    "event": {
                        "$ref": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/333"
                    },
                },
            ]
        }
    }
    ids = EspnGamesClient.parse_eventlog_game_ids(payload, played_only=True, limit=5)
    assert ids == ["222", "333"]


@pytest.mark.asyncio
async def test_collect_wp10_games_uses_fixture_summary(monkeypatch: pytest.MonkeyPatch):
    athlete = SmokeAthlete(
        sport="ncaab_mens",
        name="Sample Player",
        espn_id="1001",
        team_hint="Duke",
        position_hint="G",
    )
    payload = json.loads(BOX_FIXTURE.read_text(encoding="utf-8"))
    client = EspnGamesClient()

    async def fake_list(*_a, **_k):
        return ["sample-2024-01-15"]

    async def fake_fetch(league, game_id):
        return client.parse_game_summary(
            league, game_id, payload, source_url="fixture:box"
        )

    monkeypatch.setattr(client, "list_athlete_game_ids", fake_list)
    monkeypatch.setattr(client, "fetch_parsed_game", fake_fetch)

    result = await collect_wp10_games(athlete, games_client=client, max_games=1)
    assert result.ok
    assert result.games_fetched == 1
    assert result.box_reconcile_ok is True
    assert result.games[0]["home_score"] == 78
    assert result.games[0]["away_score"] == 71
