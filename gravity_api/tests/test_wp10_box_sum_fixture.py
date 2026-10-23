"""WP10: fixture-based NCAAB box SUM(pts) vs header score (no staging DB)."""

from __future__ import annotations

import json
from pathlib import Path

from gravity_api.scrapers.clients.espn_games import EspnGamesClient
from gravity_api.services.games_store import box_score_reconciliation

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "espn"
    / "ncaab_mens"
    / "box_score_sample.json"
)


def test_ncaab_box_sum_matches_header_scores():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    client = EspnGamesClient()
    summary = client.parse_game_summary(
        "ncaab_mens",
        "sample-2024-01-15",
        payload,
        source_url="fixture:ncaab_mens/box_score_sample.json",
    )
    assert summary.home_score == 78
    assert summary.away_score == 71
    assert summary.home_team_id == "251"
    assert summary.away_team_id == "99"
    assert len(summary.players) == 8

    players = [
        {
            "team_id": p.team_id,
            "espn_athlete_id": p.espn_athlete_id,
            "stats": p.stats,
        }
        for p in summary.players
    ]
    report = box_score_reconciliation(
        home_team_id=summary.home_team_id,
        away_team_id=summary.away_team_id,
        home_score=summary.home_score,
        away_score=summary.away_score,
        players=players,
    )
    assert report["matched"] is True
    assert report["by_team"]["251"] == 78.0
    assert report["by_team"]["99"] == 71.0
    assert report["discrepancies"] == []


def test_ncaab_box_sum_flags_discrepancy():
    report = box_score_reconciliation(
        home_team_id="251",
        away_team_id="99",
        home_score=78,
        away_score=71,
        players=[
            {"team_id": "251", "stats": {"pts": 40}},
            {"team_id": "99", "stats": {"pts": 71}},
        ],
    )
    assert report["matched"] is False
    assert any(d["team_id"] == "251" for d in report["discrepancies"])
