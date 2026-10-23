"""WP2 acceptance: category-aware SeasonStatLine parsing + namespaced normalize."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gravity_api.scrapers.parsers.espn_stats import (
    ParseConflict,
    parse_core_season_statistics,
)
from gravity_api.scrapers.parsers.stat_normalizer import (
    aliases_unique_within_category_scope,
    normalize_namespaced_stats,
)

FIXTURES = Path(__file__).parent / "fixtures" / "espn"


def _load_core(league: str, espn_id: str, filename: str) -> dict:
    path = FIXTURES / league / espn_id / filename
    assert path.exists(), f"missing fixture {path}"
    return json.loads(path.read_text())


def _parse_fixture(
    league: str,
    espn_id: str,
    filename: str,
    *,
    season_year: int,
    season_type: str = "regular",
) -> tuple[dict[str, float], dict[str, float]]:
    payload = _load_core(league, espn_id, filename)
    line = parse_core_season_statistics(
        payload,
        league=league,
        season_year=season_year,
        season_type=season_type,
        team_id="TOT",
        team_name=None,
        is_total=True,
        source_url=f"fixture:{league}/{espn_id}/{filename}",
        stats_as_of=datetime(2026, 10, 22, tzinfo=timezone.utc),
    )
    normalized = normalize_namespaced_stats(league, line.stats)
    return line.stats, normalized


@pytest.mark.parametrize("sport", ["cfb", "nfl", "nba", "ncaab_mens"])
def test_aliases_unique_within_category_scope(sport: str):
    aliases_unique_within_category_scope(sport)


def test_will_anderson_sacks_from_defensive_category():
    namespaced, norm = _parse_fixture(
        "nfl", "4685724", "statistics_2026_2.json", season_year=2026
    )
    assert namespaced.get("defensive.sacks") == 7.5
    assert namespaced.get("passing.sacks") == 0.0
    assert norm.get("sacks", 0) > 0
    assert norm["sacks"] == namespaced["defensive.sacks"] == 7.5
    assert norm.get("pass_sacks") == 0.0


def test_colin_simmons_tfl_gte_sacks():
    namespaced, norm = _parse_fixture(
        "cfb", "5079689", "statistics_2026_2.json", season_year=2026
    )
    assert namespaced.get("defensive.sacks") == 10.5
    assert namespaced.get("defensive.tacklesForLoss") == 15.5
    assert norm.get("sacks", 0) > 0
    assert norm.get("tfl", 0) >= norm.get("sacks", 0)
    assert norm["tfl"] == 15.5
    assert norm["sacks"] == 10.5


def test_mahomes_pass_sacks_populated_sacks_absent():
    namespaced, norm = _parse_fixture(
        "nfl", "3139477", "statistics_2025_2.json", season_year=2025
    )
    assert namespaced.get("passing.sacks") == 34.0
    assert namespaced.get("defensive.sacks") == 0.0
    assert "pass_sacks" in norm
    assert norm["pass_sacks"] == 34.0
    assert "sacks" not in norm


def test_parse_conflict_duplicate_within_category(caplog):
    payload = {
        "splits": {
            "categories": [
                {
                    "name": "defensive",
                    "stats": [
                        {"name": "sacks", "value": 7.5},
                        {"name": "sacks", "value": 99.0},
                    ],
                }
            ]
        }
    }
    with caplog.at_level("WARNING"):
        line = parse_core_season_statistics(
            payload,
            league="nfl",
            season_year=2026,
            season_type="regular",
            team_id="TOT",
            team_name=None,
            is_total=True,
            source_url="test",
            stats_as_of=datetime(2026, 10, 22, tzinfo=timezone.utc),
        )
    assert line.stats.get("defensive.sacks") == 7.5
    assert any("ParseConflict" in r.message or "duplicate stat" in r.message for r in caplog.records)
    # Ensure the exception type is the one we use for conflicts.
    assert issubclass(ParseConflict, Exception)


def test_category_pair_sacks_and_ints_disambiguated():
    namespaced = {
        "defensive.sacks": 7.5,
        "passing.sacks": 2.0,
        "defensive.interceptions": 3.0,
        "passing.interceptions": 1.0,
    }
    out = normalize_namespaced_stats("nfl", namespaced)
    assert out["sacks"] == 7.5
    assert out["pass_sacks"] == 2.0
    assert out["interceptions"] == 3.0
    assert out["pass_int"] == 1.0
