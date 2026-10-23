"""Arch Manning: ESPN season-sum ~5206 vs Sports-Reference ~4994 (zero tolerance).

SCRAPER_FIX_SPEC §4.4 — mismatch is stored and logged to collection_errors with
both values. Do not rewrite ESPN toward SR.
"""

from __future__ import annotations

import json
from pathlib import Path

from gravity_api.scrapers.clients.espn_season_history import (
    EspnSeasonHistoryClient,
    derive_career_from_seasons,
)
from gravity_api.services.stat_validation import (
    collection_errors_from_validation,
    log_validation_result,
    validate_career_counting_stat,
    validate_completed_season,
    values_match,
)
from gravity_api.scrapers.types import SeasonStatLine
from datetime import date, datetime, timezone

FIXTURES = Path(__file__).parent / "fixtures"
SR_ARCH = FIXTURES / "sports_reference" / "cfb" / "arch_manning.json"
ARCH_V3 = FIXTURES / "season_history" / "arch_cfb_v3.json"
ESPN_2025 = FIXTURES / "espn" / "cfb" / "4870906" / "statistics_2025_2.json"

_ON = date(2026, 10, 22)


def _sr_blob() -> dict:
    return json.loads(SR_ARCH.read_text(encoding="utf-8"))


def _espn_season_sum_pass_yards() -> float:
    blob = json.loads(ARCH_V3.read_text(encoding="utf-8"))
    client = EspnSeasonHistoryClient()
    rows = client._rows_from_v3(
        blob["payload"],
        espn_id="4870906",
        sport="cfb",
        season_type="regular",
        source_url=blob.get("url") or "fixture",
    )
    seasons = [r for r in rows if not r.is_total]
    career = derive_career_from_seasons(seasons)
    return float(career.get("pass_yards") or career.get("passingYards") or 0)


def test_sr_fixture_locks_4994_career():
    sr = _sr_blob()
    assert sr["career"]["pass_yards"] == 4994.0
    assert sum(s["pass_yards"] for s in sr["seasons"].values()) == 4994.0
    assert sr["investigation"]["espn_v3_fixture_season_sum_pass_yards"] == 5206


def test_espn_v3_fixture_season_sum_is_5206():
    yds = _espn_season_sum_pass_yards()
    assert yds == 5206.0
    assert yds < 5427  # not the career-aggregate hallucination


def test_espn_5206_vs_sr_4994_is_zero_tolerance_mismatch():
    sr = _sr_blob()
    ours = _espn_season_sum_pass_yards()
    theirs = float(sr["career"]["pass_yards"])
    assert not values_match("pass_yards", ours, theirs)

    result = validate_career_counting_stat(
        ours_total=ours,
        second_source_total=theirs,
        stat_key="pass_yards",
        league="cfb",
        athlete_name="Arch Manning",
    )
    assert result.status == "mismatch"
    assert "pass_yards" in result.details["mismatches"]
    cmp = result.details["comparisons"]["pass_yards"]
    assert cmp["ours"] == 5206.0
    assert cmp["theirs"] == 4994.0

    errors = collection_errors_from_validation(
        result, athlete_name="Arch Manning"
    )
    assert errors
    assert any("5206" in e and "4994" in e for e in errors)
    # log_validation_result returns the same strings (and emits WARNING).
    logged = log_validation_result(result, athlete_name="Arch Manning")
    assert logged == errors


def test_espn_2025_fixture_vs_sr_2025_is_mismatch_with_both_values():
    """Completed-season gate: ESPN WP0 2025 undercounts vs locked SR 2025."""
    from gravity_api.scrapers.clients.espn import _strip_capture
    from gravity_api.scrapers.parsers.espn_stats import parse_core_season_statistics

    sr = _sr_blob()["seasons"]["2025"]
    raw = json.loads(ESPN_2025.read_text(encoding="utf-8"))
    clean, _ = _strip_capture(raw)
    line = parse_core_season_statistics(
        clean,
        league="cfb",
        season_year=2025,
        season_type="regular",
        team_id="TOT",
        team_name="Texas",
        is_total=True,
        source_url="fixture:espn/cfb/4870906/statistics_2025_2.json",
        stats_as_of=datetime(2026, 10, 22, tzinfo=timezone.utc),
    )
    result = validate_completed_season(
        line,
        second_source_stats=sr,
        position="QB",
        on=_ON,
    )
    assert result.status == "mismatch"
    assert "pass_yards" in result.details["mismatches"]
    cmp = result.details["comparisons"]["pass_yards"]
    assert cmp["ours"] == 2942.0
    assert cmp["theirs"] == 3163.0
    errors = collection_errors_from_validation(
        result, athlete_name="Arch Manning"
    )
    assert any("pass_yards" in e and "2942" in e and "3163" in e for e in errors)


# Silence unused import lint for SeasonStatLine if type checkers want it present
_ = SeasonStatLine
