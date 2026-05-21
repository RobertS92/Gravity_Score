from datetime import date

import pytest

from gravity_api.services.csc_v2_invariants import (
    SeasonStateRow,
    validate_season_state_coverage,
    validate_single_active_exposure_formula,
)


def test_validate_single_active_exposure_formula_accepts_exactly_one():
    validate_single_active_exposure_formula(
        [
            {"version": "v1", "is_active": True},
            {"version": "v2", "is_active": False},
        ]
    )


def test_validate_single_active_exposure_formula_rejects_zero_or_many():
    with pytest.raises(ValueError):
        validate_single_active_exposure_formula(
            [
                {"version": "v1", "is_active": False},
                {"version": "v2", "is_active": False},
            ]
        )
    with pytest.raises(ValueError):
        validate_single_active_exposure_formula(
            [
                {"version": "v1", "is_active": True},
                {"version": "v2", "is_active": True},
            ]
        )


def test_validate_season_state_coverage_contiguous_for_year():
    rows = [
        SeasonStateRow("CFB", date(2026, 1, 1), date(2026, 8, 15)),
        SeasonStateRow("CFB", date(2026, 8, 16), date(2026, 12, 31)),
    ]
    validate_season_state_coverage(
        rows,
        start=date(2026, 1, 1),
        end=date(2026, 12, 31),
    )


def test_validate_season_state_coverage_detects_gap():
    rows = [
        SeasonStateRow("NCAAB", date(2026, 1, 1), date(2026, 4, 15)),
        SeasonStateRow("NCAAB", date(2026, 4, 17), date(2026, 12, 31)),
    ]
    with pytest.raises(ValueError):
        validate_season_state_coverage(
            rows,
            start=date(2026, 1, 1),
            end=date(2026, 12, 31),
        )
