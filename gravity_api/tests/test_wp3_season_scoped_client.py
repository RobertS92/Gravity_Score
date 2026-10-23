"""WP3 acceptance: season-scoped EspnClient stat lines (fixes B1, B8)."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from gravity_api.scrapers.clients.espn import EspnClient, _strip_capture

FIXTURES = Path(__file__).parent / "fixtures" / "espn"


def _load_json(path: Path) -> dict[str, Any]:
    assert path.exists(), f"missing fixture {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture_router(league: str, espn_id: str):
    root = FIXTURES / league / espn_id
    seasons_files = {
        int(m.group(1)): p
        for p in root.glob("seasons_*.json")
        if (m := re.search(r"seasons_(\d+)\.json$", p.name))
    }
    athlete_files = {
        int(m.group(1)): p
        for p in root.glob("athlete_season_*.json")
        if (m := re.search(r"athlete_season_(\d+)\.json$", p.name))
    }
    stats_files = {
        (int(m.group(1)), int(m.group(2))): p
        for p in root.glob("statistics_*_*.json")
        if (m := re.search(r"statistics_(\d+)_(\d+)\.json$", p.name))
    }
    v3_path = root / "v3_stats.json"
    log_path = root / "statisticslog.json"
    career_path = root / "statistics_career_unscoped.json"
    teams_by_id: dict[str, dict[str, Any]] = {}
    if v3_path.exists():
        v3 = _load_json(v3_path)
        for slug, team in (v3.get("teams") or {}).items():
            if isinstance(team, dict) and team.get("id") is not None:
                teams_by_id[str(team["id"])] = {**team, "slug": slug}

    async def fake_get(url: str, *, allow_empty: bool = True) -> dict[str, Any]:
        u = url.replace("http://", "https://")
        path: Path | None = None
        if "/statisticslog" in u:
            path = log_path
        elif re.search(r"/athletes/\d+/stats", u):
            path = v3_path
        elif "/statistics" in u and "/seasons/" in u and "/types/" in u:
            ym = re.search(r"/seasons/(\d+)/types/(\d+)/", u)
            if ym:
                key = (int(ym.group(1)), int(ym.group(2)))
                path = stats_files.get(key)
        elif re.search(r"/seasons/\d+/athletes/\d+", u) and "/statistics" not in u:
            ym = re.search(r"/seasons/(\d+)/athletes/", u)
            if ym:
                path = athlete_files.get(int(ym.group(1)))
        elif re.search(r"/seasons/\d+(?:\?|$)", u) and "/types/" not in u:
            ym = re.search(r"/seasons/(\d+)", u)
            if ym:
                path = seasons_files.get(int(ym.group(1)))
        elif "/athletes/" in u and u.rstrip("/").endswith("/statistics"):
            path = career_path if career_path.exists() else None
        elif "/teams/" in u:
            tid_m = re.search(r"/teams/(\d+)", u)
            if tid_m and tid_m.group(1) in teams_by_id:
                team = teams_by_id[tid_m.group(1)]
                return {
                    "id": team.get("id"),
                    "abbreviation": team.get("abbreviation"),
                    "shortDisplayName": team.get("shortDisplayName"),
                    "displayName": team.get("displayName"),
                }

        if path is None or not path.exists():
            return {}
        raw = _load_json(path)
        clean, capture = _strip_capture(raw)
        # Attach capture meta the same way EspnClient._get would.
        client = fake_get.client  # type: ignore[attr-defined]
        client._record_fetch_meta(u, capture=capture)
        return clean

    return fake_get


@pytest.fixture
def lebron_client(monkeypatch: pytest.MonkeyPatch) -> EspnClient:
    client = EspnClient()
    router = _fixture_router("nba", "1966")
    router.client = client  # type: ignore[attr-defined]
    monkeypatch.setattr(client, "_get", router)
    return client


@pytest.fixture
def durant_client(monkeypatch: pytest.MonkeyPatch) -> EspnClient:
    client = EspnClient()
    router = _fixture_router("nba", "3202")
    router.client = client  # type: ignore[attr-defined]
    monkeypatch.setattr(client, "_get", router)
    return client


@pytest.mark.asyncio
async def test_list_stat_seasons_lebron_covers_log_years(lebron_client: EspnClient):
    seasons = await lebron_client.list_stat_seasons("1966", "nba")
    assert seasons
    years = sorted({y for y, _stype, _ref in seasons})
    assert years == list(range(2004, 2028))
    for year, stype, ref in seasons:
        assert isinstance(year, int)
        assert stype in {"regular", "postseason"}
        assert "/seasons/" in ref and "/types/" in ref
        assert "statistics" in ref


@pytest.mark.asyncio
async def test_lebron_regular_season_lines_for_all_log_seasons(
    lebron_client: EspnClient,
):
    seasons = await lebron_client.list_stat_seasons("1966", "nba")
    log_years = sorted({y for y, _stype, _ref in seasons})
    assert log_years == list(range(2004, 2028))

    all_lines = []
    for year in log_years:
        lines = await lebron_client.get_season_stat_lines(
            "1966", "nba", year, "regular"
        )
        assert lines, f"expected regular-season lines for {year}"
        assert all(ln.season_year == year for ln in lines)
        assert all(ln.season_type == "regular" for ln in lines)
        assert any(ln.is_total and ln.team_id == "TOT" for ln in lines)
        all_lines.extend(lines)

    assert {ln.season_year for ln in all_lines} == set(log_years)
    assert all(ln.stats_as_of is not None for ln in all_lines)
    assert all(isinstance(ln.stats_as_of, datetime) for ln in all_lines)
    # Never a season-label string (B8)
    assert all(not isinstance(ln.stats_as_of, str) for ln in all_lines)


@pytest.mark.asyncio
async def test_durant_2023_bkn_phx_tot(durant_client: EspnClient):
    lines = await durant_client.get_season_stat_lines("3202", "nba", 2023, "regular")
    assert lines
    by_team = {ln.team_id: ln for ln in lines}
    assert "TOT" in by_team
    assert by_team["TOT"].is_total is True

    team_lines = [ln for ln in lines if not ln.is_total]
    assert len(team_lines) == 2
    team_ids = {ln.team_id for ln in team_lines}
    abbrs = {ln.team_name for ln in team_lines}
    assert team_ids == {"17", "21"}
    assert abbrs == {"BKN", "PHX"}

    assert all(ln.stats_as_of is not None for ln in lines)
    assert all(isinstance(ln.stats_as_of, datetime) for ln in lines)
    # Completed 2022-23 → endDate-based as_of (not None / not label)
    for ln in lines:
        assert ln.stats_as_of.tzinfo is not None


@pytest.mark.asyncio
async def test_no_line_has_null_stats_as_of(lebron_client: EspnClient, durant_client: EspnClient):
    lines = []
    for year in (2004, 2026, 2027):
        lines.extend(
            await lebron_client.get_season_stat_lines("1966", "nba", year, "regular")
        )
    lines.extend(
        await durant_client.get_season_stat_lines("3202", "nba", 2023, "regular")
    )
    assert lines
    assert all(ln.stats_as_of is not None for ln in lines)


@pytest.mark.asyncio
async def test_get_season_stats_does_not_use_unscoped_as_season(
    lebron_client: EspnClient, monkeypatch: pytest.MonkeyPatch
):
    """B1: unscoped core aggregate must not become season_stats."""
    calls: list[str] = []
    real_get = lebron_client._get

    async def tracking_get(url: str, *, allow_empty: bool = True) -> dict[str, Any]:
        calls.append(url)
        return await real_get(url, allow_empty=allow_empty)

    monkeypatch.setattr(lebron_client, "_get", tracking_get)
    packed = await lebron_client.get_season_stats("1966", "nba")
    # Unscoped career URL must not be the source of season_stats.
    unscoped = [
        u
        for u in calls
        if u.rstrip("/").endswith("/athletes/1966/statistics")
        and "/seasons/" not in u
    ]
    assert not unscoped or not (packed.get("season_stats") and packed.get("stats_source") == "espn_core")
    # If season_stats present, they came from site/v3 history path.
    if packed.get("season_stats"):
        assert packed.get("stats_source") in {"espn", "espn_core_season"}
