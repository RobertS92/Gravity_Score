"""SMU demo cohort fixture integrity (+ optional live ESPN Jennings check)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COHORT_PATH = ROOT / "data" / "demo" / "smu_demo_cohort.json"


@pytest.fixture(scope="module")
def cohort() -> dict:
    assert COHORT_PATH.is_file(), f"missing {COHORT_PATH}"
    return json.loads(COHORT_PATH.read_text(encoding="utf-8"))


def test_cohort_has_smu_team_and_jennings(cohort: dict) -> None:
    school = cohort["school"]
    assert school["espn_team_id"] == "2567"
    assert school["short_name"] == "SMU"

    primary = cohort["primary_demo_athlete"]
    assert primary["name"] == "Kevin Jennings"
    assert primary["espn_id"] == "5084084"
    assert primary["sport"] == "cfb"
    assert primary["position"] == "QB"

    by_espn = {
        str(a["espn_id"]): a
        for a in cohort["athletes"]
        if a.get("espn_id")
    }
    assert "5084084" in by_espn
    assert by_espn["5084084"]["name"] == "Kevin Jennings"


def test_cohort_espn_ids_unique_and_digit(cohort: dict) -> None:
    ids: list[str] = []
    for row in cohort["athletes"]:
        if row.get("coverage") == "gap":
            continue
        espn_id = row.get("espn_id")
        assert espn_id, f"curated athlete missing espn_id: {row.get('name')}"
        espn_s = str(espn_id)
        assert espn_s.isdigit(), espn_s
        ids.append(espn_s)
    assert len(ids) == len(set(ids))
    assert len(ids) >= 15


def test_cohort_covers_cfb_and_mbb(cohort: dict) -> None:
    sports = {a["sport"] for a in cohort["athletes"] if a.get("espn_id")}
    assert "cfb" in sports
    assert "ncaab_mens" in sports


def test_smoke_queries_include_jennings(cohort: dict) -> None:
    qs = cohort.get("smoke_queries") or []
    assert any(
        (q.get("expect_name") == "Kevin Jennings")
        or (str(q.get("q", "")).lower().find("jennings") >= 0)
        for q in qs
    )


def test_live_espn_smu_roster_includes_jennings() -> None:
    """Live canary: SMU CFB roster must still list Kevin Jennings #5084084."""
    import asyncio

    from gravity_api.scrapers.clients.espn import EspnClient

    async def _fetch() -> list[dict]:
        client = EspnClient()
        payload = await client.fetch_roster_payload("cfb", "2567")
        return EspnClient.flatten_roster_players(payload) if payload else []

    players = asyncio.run(_fetch())
    assert len(players) >= 40, f"unexpectedly thin SMU roster: {len(players)}"
    espn_ids = {str(p.get("id") or p.get("espn_id") or "") for p in players}
    names = {
        str(p.get("displayName") or p.get("fullName") or "").lower() for p in players
    }
    assert "5084084" in espn_ids
    assert any("kevin jennings" in n for n in names)
