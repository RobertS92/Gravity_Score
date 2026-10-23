"""WP6: second-source season validation (SCRAPER_FIX_SPEC §4.4)."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from gravity_api.scrapers.clients.espn import _strip_capture
from gravity_api.scrapers.parsers.espn_stats import parse_core_season_statistics
from gravity_api.scrapers.types import SeasonStatLine
from gravity_api.services.stat_validation import (
    canonicalize_stat_dict,
    fetch_second_source_stats,
    line_canonical_stats,
    primary_stat_keys,
    validate_completed_season,
    values_match,
)

FIXTURES = Path(__file__).parent / "fixtures" / "espn"

# Spec "today" for season_status: after 2025-26 / 2025 football seasons closed.
_ON = date(2026, 10, 22)

# Injected second-source dicts aligned to ESPN fixture completed seasons.
# Built from the same fixture parse so CI does not need live CFBD/SR.
# Any real production mismatch must be investigated in docs/specs/wp6-validation-notes.md
# — not "fixed" by loosening tolerances here.
_SECOND_SOURCE: dict[str, dict[str, float]] = {
    "lebron_2026": {
        "gp": 60.0,
        "pts": 1256.0,
        "reb": 364.0,
        "ast": 432.0,
        "min": 1989.0,
    },
    "durant_2023": {
        "gp": 47.0,
        "pts": 1366.0,
        "reb": 313.0,
        "ast": 235.0,
        "min": 1672.0,
    },
    "mahomes_2025": {
        "gp": 14.0,
        "pass_yards": 3587.0,
        "pass_td": 22.0,
        "pass_int": 11.0,
        "pass_attempts": 502.0,
    },
    "will_anderson_2025": {
        "gp": 17.0,
        "tackles": 54.0,
        "sacks": 12.0,
        "tfl": 20.0,
        "interceptions": 0.0,
    },
    "arch_manning_2025": {
        "gp": 12.0,
        "pass_yards": 2942.0,
        "pass_td": 24.0,
        "pass_int": 7.0,
        "pass_attempts": 370.0,
    },
    "colin_simmons_2025": {
        "gp": 11.0,
        "tackles": 41.0,
        "sacks": 11.0,
        "tfl": 11.0,
        "interceptions": 0.0,
    },
    "dybantsa_ncaab_2026": {
        "gp": 34.0,
        "pts": 859.0,
        "reb": 229.0,
        "ast": 129.0,
        "min": 1178.0,
    },
    "sarah_strong_2026": {
        "gp": 8.0,
        "pts": 141.0,
        "reb": 75.0,
        "ast": 42.0,
        "min": 223.0,
    },
}


def _line_from_fixture(
    league: str,
    espn_id: str,
    filename: str,
    *,
    season_year: int,
    season_type: str = "regular",
    team_id: str = "TOT",
) -> SeasonStatLine:
    path = FIXTURES / league / espn_id / filename
    assert path.exists(), f"missing fixture {path}"
    raw = json.loads(path.read_text(encoding="utf-8"))
    clean, _ = _strip_capture(raw)
    return parse_core_season_statistics(
        clean,
        league=league,
        season_year=season_year,
        season_type=season_type,
        team_id=team_id,
        team_name=None,
        is_total=True,
        source_url=f"fixture:{league}/{espn_id}/{filename}",
        stats_as_of=datetime(2026, 10, 22, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Unit: keys, aliases, tolerances
# ---------------------------------------------------------------------------


def test_primary_stat_keys_basketball():
    assert primary_stat_keys("nba") == ("gp", "pts", "reb", "ast", "min")
    assert primary_stat_keys("wnba") == ("gp", "pts", "reb", "ast", "min")
    assert primary_stat_keys("ncaab_mens") == ("gp", "pts", "reb", "ast", "min")
    assert primary_stat_keys("ncaab_womens") == ("gp", "pts", "reb", "ast", "min")


def test_primary_stat_keys_football_by_position():
    assert primary_stat_keys("nfl", "QB")[1] == "pass_yards"
    assert primary_stat_keys("cfb", "RB")[1] == "rush_yards"
    assert primary_stat_keys("nfl", "WR")[3] == "receptions"
    assert primary_stat_keys("nfl", "DE")[2] == "sacks"
    assert primary_stat_keys("cfb", "LB")[1] == "tackles"


def test_canonicalize_maps_games_played_aliases():
    out = canonicalize_stat_dict({"games_played_season": 60, "pts": 100})
    assert out["gp"] == 60.0
    assert out["pts"] == 100.0


def test_values_match_zero_on_counts_tenth_on_sacks():
    assert values_match("pts", 1256.0, 1256.0)
    assert not values_match("pts", 1256.0, 1257.0)
    assert values_match("sacks", 12.0, 12.05)
    assert values_match("sacks", 12.0, 11.9)
    assert not values_match("sacks", 12.0, 11.8)
    assert values_match("tfl", 20.0, 20.1)


# ---------------------------------------------------------------------------
# WP0 athlete completed-season matches (injected second source)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key,league,espn_id,filename,year,position,second_key",
    [
        ("lebron", "nba", "1966", "statistics_2026_2.json", 2026, None, "lebron_2026"),
        ("durant", "nba", "3202", "statistics_2023_2.json", 2023, None, "durant_2023"),
        (
            "mahomes",
            "nfl",
            "3139477",
            "statistics_2025_2.json",
            2025,
            "QB",
            "mahomes_2025",
        ),
        (
            "will_anderson",
            "nfl",
            "4685724",
            "statistics_2025_2.json",
            2025,
            "DE",
            "will_anderson_2025",
        ),
        (
            "arch_manning",
            "cfb",
            "4870906",
            "statistics_2025_2.json",
            2025,
            "QB",
            "arch_manning_2025",
        ),
        (
            "colin_simmons",
            "cfb",
            "5079689",
            "statistics_2025_2.json",
            2025,
            "DE",
            "colin_simmons_2025",
        ),
        (
            "dybantsa_ncaab",
            "ncaab_mens",
            "5142718",
            "statistics_2026_2.json",
            2026,
            None,
            "dybantsa_ncaab_2026",
        ),
        (
            "sarah_strong",
            "ncaab_womens",
            "5239592",
            "statistics_2026_2.json",
            2026,
            None,
            "sarah_strong_2026",
        ),
    ],
)
def test_wp0_completed_season_matches_injected_second_source(
    key: str,
    league: str,
    espn_id: str,
    filename: str,
    year: int,
    position: str | None,
    second_key: str,
):
    line = _line_from_fixture(league, espn_id, filename, season_year=year)
    ours = line_canonical_stats(line)
    assert ours.get("gp") is not None, f"{key} missing gp after canonicalize: {ours}"

    result = validate_completed_season(
        line,
        second_source_stats=_SECOND_SOURCE[second_key],
        position=position,
        on=_ON,
    )
    assert result.status == "matched", (
        f"{key} expected matched, got {result.status}: {result.details}"
    )
    assert result.details["comparisons"]
    assert not result.details["mismatches"]


def test_dybantsa_nba_in_progress_is_unvalidated():
    """Dybantsa NBA 2027 has no completed season in WP0 fixtures."""
    # Fabricate an in-progress line (fixture stats endpoint 404'd for 2027).
    line = SeasonStatLine(
        league="nba",
        season_year=2027,
        season_type="regular",
        team_id="TOT",
        team_name="Wizards",
        is_total=True,
        stats={"general.gamesPlayed": 2.0, "offensive.points": 20.0},
        source_key="espn",
        source_url="fixture:nba/5142718/in_progress",
        stats_as_of=datetime(2026, 10, 22, tzinfo=timezone.utc),
    )
    result = validate_completed_season(line, second_source_stats=None, on=_ON)
    assert result.status == "unvalidated"
    assert result.details["season_status"] == "in_progress"


def test_completed_without_second_source_is_no_second_source():
    line = _line_from_fixture(
        "nba", "1966", "statistics_2026_2.json", season_year=2026
    )
    result = validate_completed_season(line, second_source_stats=None, on=_ON)
    assert result.status == "no_second_source"


def test_mismatch_reports_both_values():
    line = _line_from_fixture(
        "nba", "1966", "statistics_2026_2.json", season_year=2026
    )
    bad = dict(_SECOND_SOURCE["lebron_2026"])
    bad["pts"] = 9999.0
    result = validate_completed_season(
        line, second_source_stats=bad, on=_ON
    )
    assert result.status == "mismatch"
    assert "pts" in result.details["mismatches"]
    cmp = result.details["comparisons"]["pts"]
    assert cmp["ours"] == 1256.0
    assert cmp["theirs"] == 9999.0


def test_sacks_decimal_tolerance_allows_tenth():
    line = _line_from_fixture(
        "nfl", "4685724", "statistics_2025_2.json", season_year=2025
    )
    second = dict(_SECOND_SOURCE["will_anderson_2025"])
    second["sacks"] = 12.05  # within ±0.1
    result = validate_completed_season(
        line, second_source_stats=second, position="DE", on=_ON
    )
    assert result.status == "matched"


def test_sacks_decimal_tolerance_rejects_beyond_tenth():
    line = _line_from_fixture(
        "nfl", "4685724", "statistics_2025_2.json", season_year=2025
    )
    second = dict(_SECOND_SOURCE["will_anderson_2025"])
    second["sacks"] = 11.8  # beyond ±0.1
    result = validate_completed_season(
        line, second_source_stats=second, position="DE", on=_ON
    )
    assert result.status == "mismatch"
    assert "sacks" in result.details["mismatches"]


# ---------------------------------------------------------------------------
# Fetch path routing (mocked CFBD / Sports-Reference)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_second_source_cfbd_for_cfb(monkeypatch: pytest.MonkeyPatch):
    line = _line_from_fixture(
        "cfb", "4870906", "statistics_2025_2.json", season_year=2025
    )

    fake_client = MagicMock()
    fake_client.fetch_player_stats_bundle = AsyncMock(
        return_value=(
            {"id": 1},
            {},
            {
                "2025": {
                    "games_played_season": 12.0,
                    "pass_yards": 2942.0,
                    "pass_td": 24.0,
                    "pass_int": 7.0,
                    "pass_attempts": 370.0,
                }
            },
        )
    )

    class _FakeCfbd:
        def __init__(self, *a: Any, **k: Any) -> None:
            pass

        async def fetch_player_stats_bundle(self, **kwargs: Any) -> Any:
            return await fake_client.fetch_player_stats_bundle(**kwargs)

    monkeypatch.setattr(
        "gravity_api.scrapers.clients.cfbd.CfbdClient",
        _FakeCfbd,
    )
    monkeypatch.setattr(
        "gravity_api.scrapers.clients.cfbd.cfbd_is_rate_limited",
        lambda: False,
    )

    stats = await fetch_second_source_stats(
        line, athlete_name="Arch Manning", team="Texas", position="QB"
    )
    assert stats is not None
    assert stats["gp"] == 12.0
    assert stats["pass_yards"] == 2942.0

    result = validate_completed_season(
        line, second_source_stats=stats, position="QB", on=_ON
    )
    assert result.status == "matched"


@pytest.mark.asyncio
async def test_fetch_second_source_sports_reference_for_nba(
    monkeypatch: pytest.MonkeyPatch,
):
    line = _line_from_fixture(
        "nba", "1966", "statistics_2026_2.json", season_year=2026
    )

    async def _fake_sr(sport: str, name: str, school: str | None = None) -> dict:
        assert sport == "nba"
        assert "LeBron" in name or "James" in name or name
        return {
            "season_stats": {
                "gp": 60.0,
                "pts": 1256.0,
                "reb": 364.0,
                "ast": 432.0,
                "min": 1989.0,
            },
            "stats_source": "sports_reference",
        }

    monkeypatch.setattr(
        "gravity_api.scrapers.parsers.sports_reference_stats.fetch_sports_ref_stats",
        _fake_sr,
    )

    stats = await fetch_second_source_stats(
        line, athlete_name="LeBron James", school="Lakers"
    )
    assert stats is not None
    assert stats["pts"] == 1256.0

    result = validate_completed_season(line, second_source_stats=stats, on=_ON)
    assert result.status == "matched"


@pytest.mark.asyncio
async def test_fetch_second_source_none_when_empty(monkeypatch: pytest.MonkeyPatch):
    line = _line_from_fixture(
        "nba", "1966", "statistics_2026_2.json", season_year=2026
    )

    async def _empty(*a: Any, **k: Any) -> dict:
        return {}

    monkeypatch.setattr(
        "gravity_api.scrapers.parsers.sports_reference_stats.fetch_sports_ref_stats",
        _empty,
    )
    stats = await fetch_second_source_stats(line, athlete_name="LeBron James")
    assert stats is None
