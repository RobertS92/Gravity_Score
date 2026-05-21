"""Table-driven tests for the CSC confidence override chain.

The spec mandates that all five degradation sources are composed in a
single deterministic helper. These tests pin the exact behavior of each
override individually and in combination so regressions surface fast.
"""

from __future__ import annotations

import pytest

from gravity_api.services.csc_report_builder import compute_final_confidence


# ---------------------------------------------------------------------------
# Base path: no overrides fire — the base confidence flows through unchanged.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("base", ["Low", "Moderate", "High"])
def test_no_overrides_returns_base_confidence(base):
    assert (
        compute_final_confidence(
            base,
            cohort_fallback_step=0,
            comparable_state="sufficient",
            model_status="production",
            cohort_fit="good",
        )
        == base
    )


def test_invalid_base_defaults_to_moderate():
    assert (
        compute_final_confidence(
            "Catastrophic",
            cohort_fallback_step=0,
            comparable_state="sufficient",
            model_status="production",
            cohort_fit="good",
        )
        == "Moderate"
    )


# ---------------------------------------------------------------------------
# Each override in isolation.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "step,expected",
    [
        (0, "High"),
        (1, "Moderate"),
        (2, "Low"),
        (3, "Low"),
    ],
)
def test_cohort_fallback_step_caps_confidence(step, expected):
    assert (
        compute_final_confidence(
            "High",
            cohort_fallback_step=step,
            comparable_state="sufficient",
            model_status="production",
            cohort_fit="good",
        )
        == expected
    )


@pytest.mark.parametrize(
    "state,expected",
    [
        ("sufficient", "High"),
        ("sparse", "Moderate"),
        ("none", "Low"),
    ],
)
def test_comparable_state_caps_confidence(state, expected):
    assert (
        compute_final_confidence(
            "High",
            cohort_fallback_step=0,
            comparable_state=state,
            model_status="production",
            cohort_fit="good",
        )
        == expected
    )


def test_fallback_model_is_hard_cap_to_low_regardless_of_other_inputs():
    # Best possible inputs in every other dimension; fallback wins.
    assert (
        compute_final_confidence(
            "High",
            cohort_fallback_step=0,
            comparable_state="sufficient",
            model_status="fallback",
            cohort_fit="good",
        )
        == "Low"
    )


@pytest.mark.parametrize(
    "fit,expected",
    [
        ("good", "High"),
        ("edge", "High"),
        ("poor", "Moderate"),
    ],
)
def test_cohort_fit_caps_confidence_at_moderate_when_poor(fit, expected):
    assert (
        compute_final_confidence(
            "High",
            cohort_fallback_step=0,
            comparable_state="sufficient",
            model_status="production",
            cohort_fit=fit,
        )
        == expected
    )


# ---------------------------------------------------------------------------
# Combined overrides — lowest result wins.
# ---------------------------------------------------------------------------

def test_combined_overrides_take_the_lowest():
    # Step 1 (cap=Moderate) + sparse (cap=Moderate) + poor cohort (cap=Moderate)
    # against a base of High → Moderate.
    assert (
        compute_final_confidence(
            "High",
            cohort_fallback_step=1,
            comparable_state="sparse",
            model_status="production",
            cohort_fit="poor",
        )
        == "Moderate"
    )


def test_none_comparables_beats_sparse_when_both_apply():
    # Only one comparable_state can fire; spec uses 'none' as the lower cap.
    assert (
        compute_final_confidence(
            "High",
            cohort_fallback_step=1,
            comparable_state="none",
            model_status="production",
            cohort_fit="good",
        )
        == "Low"
    )


def test_step_two_with_high_base_is_low():
    assert (
        compute_final_confidence(
            "High",
            cohort_fallback_step=2,
            comparable_state="sufficient",
            model_status="production",
            cohort_fit="good",
        )
        == "Low"
    )


def test_fallback_overrides_all_other_inputs():
    assert (
        compute_final_confidence(
            "Low",
            cohort_fallback_step=0,
            comparable_state="sufficient",
            model_status="fallback",
            cohort_fit="good",
        )
        == "Low"
    )


def test_moderate_base_unchanged_when_no_caps_apply():
    assert (
        compute_final_confidence(
            "Moderate",
            cohort_fallback_step=0,
            comparable_state="sufficient",
            model_status="production",
            cohort_fit=None,
        )
        == "Moderate"
    )


def test_step_three_treated_like_step_two_for_cap_chain():
    assert (
        compute_final_confidence(
            "High",
            cohort_fallback_step=3,
            comparable_state="sufficient",
            model_status="production",
            cohort_fit="good",
        )
        == "Low"
    )
