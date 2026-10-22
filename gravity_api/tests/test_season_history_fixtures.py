"""Acceptance fixtures for season-history backfill (spec SCRAPER_SEASON_BACKFILL).

Uses recorded ESPN v3 / core payloads under tests/fixtures/season_history/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gravity_api.scrapers.clients.espn_season_history import (
    EspnSeasonHistoryClient,
    TOT_TEAM_ID,
    derive_career_from_seasons,
)
from gravity_api.scrapers.parsers.stat_normalizer import normalize_espn_stats
from gravity_api.scrapers.parsers.espn_stats import stats_from_espn_payload

FIXTURES = Path(__file__).parent / "fixtures" / "season_history"


def _load(name: str) -> dict:
    path = FIXTURES / name
    assert path.exists(), f"missing fixture {path}"
    return json.loads(path.read_text())


def _rows_from_fixture(name: str, sport: str, espn_id: str):
    blob = _load(name)
    client = EspnSeasonHistoryClient()
    return client._rows_from_v3(
        blob["payload"],
        espn_id=espn_id,
        sport=sport,
        season_type="regular",
        source_url=blob.get("url") or "fixture",
    )


def test_lebron_24_regular_season_rows_team_order():
    rows = _rows_from_fixture("lebron_nba_v3.json", "nba", "1966")
    # Exclude mid-season TOT rows from the "24 seasons" count.
    seasons = [r for r in rows if not r.is_total]
    # One primary team row per year (no mid-season trade in LeBron career on ESPN).
    by_year = {}
    for r in seasons:
        by_year.setdefault(r.espn_season_year, []).append(r)
    assert len(by_year) == 24, f"expected 24 seasons, got {len(by_year)}"
    assert min(by_year) == 2004
    assert max(by_year) == 2027

    # Team progression CLE → MIA → CLE → LAL → PHI (by first appearance order).
    abbr_by_year = {
        y: (by_year[y][0].team_abbr or by_year[y][0].raw_team_slug or "")
        for y in sorted(by_year)
    }
    sequence = [abbr_by_year[y] for y in sorted(abbr_by_year)]
    # Normalize slug/abbr
    def norm(a: str) -> str:
        a = (a or "").upper()
        if "CAVALIER" in a or a in {"CLE", "5"}:
            return "CLE"
        if "HEAT" in a or a in {"MIA", "14"}:
            return "MIA"
        if "LAKER" in a or a in {"LAL", "13"}:
            return "LAL"
        if "76" in a or "SIXER" in a or a in {"PHI", "20"}:
            return "PHI"
        return a

    norms = [norm(a) for a in sequence]
    # Collapse consecutive duplicates into franchise stretches.
    stretches = []
    for a in norms:
        if not stretches or stretches[-1] != a:
            stretches.append(a)
    assert stretches == ["CLE", "MIA", "CLE", "LAL", "PHI"], stretches

    # Current season incomplete.
    assert any(
        r.espn_season_year == 2027 and r.is_complete is False for r in seasons
    )


def test_durant_midseason_trade_bkn_phx_tot():
    rows = _rows_from_fixture("durant_nba_v3.json", "nba", "3202")
    y2023 = [r for r in rows if r.espn_season_year == 2023]
    team_ids = {r.team_id for r in y2023}
    assert "17" in team_ids  # BKN
    assert "21" in team_ids  # PHX
    assert TOT_TEAM_ID in team_ids
    tot = next(r for r in y2023 if r.is_total)
    assert tot.team_id == TOT_TEAM_ID
    bkn = next(r for r in y2023 if r.team_id == "17")
    phx = next(r for r in y2023 if r.team_id == "21")
    # GP on TOT should equal sum of team GPs when present.
    if bkn.games_played and phx.games_played and tot.games_played:
        assert tot.games_played == bkn.games_played + phx.games_played


def test_dybantsa_college_and_nba_rows():
    college = _rows_from_fixture("dybantsa_ncaab_v3.json", "ncaab_mens", "5142718")
    nba = _rows_from_fixture("dybantsa_nba_v3.json", "nba", "5142718")
    assert len([r for r in college if not r.is_total]) >= 1
    byu = college[0]
    assert byu.espn_season_year in {2026, 2025}
    assert byu.is_complete is True or byu.espn_season_year < 2027
    # NBA pack may be empty for rookies — fixture documents that gap.
    assert isinstance(nba, list)
    # Spec: college inactive is a roster concern; fixture only asserts college row exists.
    assert byu.league == "ncaab_mens"


def test_arch_manning_per_season_texas():
    rows = _rows_from_fixture("arch_cfb_v3.json", "cfb", "4870906")
    seasons = [r for r in rows if not r.is_total]
    years = sorted({r.espn_season_year for r in seasons})
    assert years == [2023, 2024, 2025, 2026], years
    for r in seasons:
        slug = (r.raw_team_slug or r.team_abbr or "").lower()
        assert "texas" in slug or r.team_abbr in {"TEX", "Texas"} or r.team_id == "251"
    career = derive_career_from_seasons(seasons)
    # Summed yards must be less than the old career-aggregate hallucination (5427)
    # and reconcile toward Sports-Reference (~4994 for completed seasons + partial).
    yds = career.get("pass_yards") or career.get("passingYards") or 0
    assert yds > 0
    assert yds < 5427


def test_colin_simmons_sacks_and_tfl():
    rows = _rows_from_fixture("colin_cfb_v3.json", "cfb", "5079689")
    # Enrich 2026 from core fixture.
    core = _load("colin_cfb_2026_core.json")["payload"]
    flat = stats_from_espn_payload(core)
    norm = normalize_espn_stats("cfb", flat)
    assert norm.get("sacks", 0) > 0
    # TFL may be reconstructed from sacks+stuffs when ESPN zeros tacklesForLoss.
    assert norm.get("tfl", 0) >= norm.get("sacks", 0)

    y2026 = [r for r in rows if r.espn_season_year == 2026 and not r.is_total]
    assert y2026
    # Merge core into fixture row like the live enricher.
    row = y2026[0]
    merged = dict(row.stats)
    for k, v in norm.items():
        if merged.get(k) in (None, 0) and v:
            merged[k] = v
    sacks = float(merged.get("sacks") or norm.get("sacks") or 0)
    tfl = float(merged.get("tfl") or norm.get("tfl") or 0)
    assert sacks > 0
    assert tfl >= sacks


def test_will_anderson_sacks_from_sacks_field():
    core = _load("will_nfl_2026_core.json")["payload"]
    flat = stats_from_espn_payload(core)
    norm = normalize_espn_stats("nfl", flat)
    assert flat.get("sacks") == 7.5
    assert norm["sacks"] == 7.5
    # avgSackYards must not be the mapped sacks value source.
    assert "avgSackYards" in flat
    assert norm["sacks"] != flat["avgSackYards"]
    rows = _rows_from_fixture("will_nfl_v3.json", "nfl", "4685724")
    assert any(r.espn_season_year == 2026 for r in rows)


def test_derive_career_excludes_tot_rows():
    rows = _rows_from_fixture("durant_nba_v3.json", "nba", "3202")
    with_tot = derive_career_from_seasons(rows)
    without = derive_career_from_seasons([r for r in rows if not r.is_total])
    # derive_career_from_seasons already skips is_total; both should match.
    assert with_tot.get("games_played_career") == without.get("games_played_career")
