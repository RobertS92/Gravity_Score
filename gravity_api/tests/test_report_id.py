"""Report-id provenance helpers."""

from __future__ import annotations

import asyncio
from datetime import date

from gravity_api.services.csc_report_builder import (
    _allocate_report_id,
    _athlete_initials,
)


def test_athlete_initials_basic():
    assert _athlete_initials("Rocco Becht") == "RB"


def test_athlete_initials_three_part_name_caps_at_three():
    assert _athlete_initials("John Quincy Adams Smith") == "JQA"


def test_athlete_initials_single_name():
    assert _athlete_initials("Madonna") == "M"


def test_athlete_initials_blank_returns_default():
    assert _athlete_initials("") == "ATH"
    assert _athlete_initials(None) == "ATH"


def test_athlete_initials_skips_non_alpha_leading_characters():
    # When the leading char of a part isn't alphabetic, it's skipped — the
    # next valid character contributes. Mirrors how downstream renders names.
    assert _athlete_initials("St. John") == "SJ"


class _StubDb:
    def __init__(self) -> None:
        self.next_seq: dict[tuple, int] = {}

    async def fetchrow(self, query, *args):
        assert "csc_report_sequence" in query
        d, initials = args
        key = (d, initials)
        self.next_seq[key] = self.next_seq.get(key, 0) + 1
        return {"next_seq": self.next_seq[key]}


def test_allocate_report_id_increments_seq_per_day_and_initials():
    db = _StubDb()
    first = asyncio.run(_allocate_report_id(db, report_date=date(2026, 5, 20), initials="RB"))
    second = asyncio.run(_allocate_report_id(db, report_date=date(2026, 5, 20), initials="RB"))
    third = asyncio.run(_allocate_report_id(db, report_date=date(2026, 5, 20), initials="JS"))
    assert first == "2026-05-20-RB-001"
    assert second == "2026-05-20-RB-002"
    assert third == "2026-05-20-JS-001"


def test_allocate_report_id_fallback_when_sequence_missing():
    class _BrokenDb:
        async def fetchrow(self, query, *args):
            raise RuntimeError("csc_report_sequence does not exist")

    rid = asyncio.run(_allocate_report_id(_BrokenDb(), report_date=date(2026, 5, 20), initials="ZZ"))
    assert rid == "2026-05-20-ZZ-001"
