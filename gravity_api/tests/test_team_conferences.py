"""Unit tests for the team_conferences lookup service."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest

from gravity_api.services.team_conferences import (
    ConferenceLookup,
    ConferenceNotMappedError,
    get_conference,
)


class _FakeDb:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    async def fetchrow(self, query: str, *args):
        team_id, sport, effective = args
        canonical_team = (team_id or "").strip().upper()
        matches = [
            r
            for r in self._rows
            if r["team_id"].strip().upper() == canonical_team
            and r["sport"] == sport
            and r["effective_from"] <= effective
            and (r.get("effective_to") is None or r["effective_to"] >= effective)
        ]
        if not matches:
            return None
        matches.sort(key=lambda r: r["effective_from"], reverse=True)
        return {
            "conference": matches[0]["conference"],
            "conference_tier": matches[0]["conference_tier"],
        }


SEED = [
    {
        "team_id": "Texas",
        "sport": "cfb",
        "conference": "Big 12",
        "conference_tier": "power_5",
        "effective_from": date(1996, 7, 1),
        "effective_to": date(2024, 6, 30),
    },
    {
        "team_id": "Texas",
        "sport": "cfb",
        "conference": "SEC",
        "conference_tier": "power_5",
        "effective_from": date(2024, 7, 1),
        "effective_to": None,
    },
    {
        "team_id": "Alabama",
        "sport": "cfb",
        "conference": "SEC",
        "conference_tier": "power_5",
        "effective_from": date(1992, 7, 1),
        "effective_to": None,
    },
    {
        "team_id": "UCLA",
        "sport": "cfb",
        "conference": "Big Ten",
        "conference_tier": "power_5",
        "effective_from": date(2024, 8, 2),
        "effective_to": None,
    },
]


def test_get_conference_returns_current_lookup():
    db = _FakeDb(SEED)
    result = asyncio.run(get_conference(db, "Alabama", "cfb", as_of=date(2026, 5, 1)))
    assert isinstance(result, ConferenceLookup)
    assert result.conference == "SEC"
    assert result.conference_tier == "power_5"


def test_get_conference_respects_realignment_window():
    db = _FakeDb(SEED)
    pre_realignment = asyncio.run(
        get_conference(db, "Texas", "cfb", as_of=date(2023, 12, 1))
    )
    post_realignment = asyncio.run(
        get_conference(db, "Texas", "cfb", as_of=date(2024, 9, 1))
    )
    assert pre_realignment.conference == "Big 12"
    assert post_realignment.conference == "SEC"


def test_get_conference_is_case_insensitive_on_team_id():
    db = _FakeDb(SEED)
    a = asyncio.run(get_conference(db, "  texas ", "cfb", as_of=date(2026, 5, 1)))
    b = asyncio.run(get_conference(db, "TEXAS", "cfb", as_of=date(2026, 5, 1)))
    assert a.conference == b.conference == "SEC"


def test_get_conference_accepts_sport_aliases():
    db = _FakeDb(SEED)
    result = asyncio.run(get_conference(db, "Texas", "NCAAF", as_of=date(2026, 5, 1)))
    assert result.conference == "SEC"


def test_get_conference_raises_on_missing_mapping():
    db = _FakeDb(SEED)
    with pytest.raises(ConferenceNotMappedError) as excinfo:
        asyncio.run(get_conference(db, "Slippery Rock", "cfb", as_of=date(2026, 5, 1)))
    err = excinfo.value
    assert err.team_id == "Slippery Rock"
    assert err.sport == "cfb"


def test_get_conference_raises_on_blank_team_id():
    db = _FakeDb(SEED)
    with pytest.raises(ConferenceNotMappedError):
        asyncio.run(get_conference(db, "", "cfb", as_of=date(2026, 5, 1)))


def test_get_conference_raises_on_unknown_sport():
    db = _FakeDb(SEED)
    with pytest.raises(ConferenceNotMappedError):
        asyncio.run(get_conference(db, "Texas", "lacrosse", as_of=date(2026, 5, 1)))
