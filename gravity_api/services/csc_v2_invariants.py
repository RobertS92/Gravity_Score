"""Helpers for CSC v2 config invariants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Sequence


@dataclass(frozen=True)
class SeasonStateRow:
    sport: str
    start_date: date
    end_date: date


def validate_single_active_exposure_formula(rows: Sequence[dict]) -> None:
    active = [r for r in rows if bool(r.get("is_active"))]
    if len(active) != 1:
        raise ValueError(f"expected exactly one active exposure formula, found {len(active)}")


def validate_season_state_coverage(
    rows: Iterable[SeasonStateRow],
    *,
    start: date,
    end: date,
) -> None:
    clipped = []
    for row in rows:
        if row.end_date < start or row.start_date > end:
            continue
        clipped.append(
            (
                max(row.start_date, start),
                min(row.end_date, end),
            )
        )
    clipped.sort()
    if not clipped:
        raise ValueError("no season state rows provided")
    cursor = start
    for seg_start, seg_end in clipped:
        if seg_start > cursor:
            raise ValueError("season state coverage has a gap")
        if seg_start < cursor:
            raise ValueError("season state coverage has overlap")
        cursor = seg_end + timedelta(days=1)
        if cursor > end:
            return
    if cursor <= end:
        raise ValueError("coverage ends before required end date")
