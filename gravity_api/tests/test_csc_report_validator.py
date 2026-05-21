"""Tests for the CSC report output validator."""

from __future__ import annotations

import copy

from gravity_api.services.csc_report_validator import (
    ValidationError,
    validate_report,
)


def _good_report() -> dict:
    return {
        "value": {
            "total_benchmark": 17900,
            "range_low": 10700,
            "range_high": 32100,
            "tier_tag": "Mid-tier",
            "confidence_tag": "Moderate Confidence",
        },
        "explanation": {
            "executive_summary": (
                "Rocco Becht profiles as a mid-tier asset with a benchmark of "
                "$17.9K and a recommended range of $10.7K to $32.1K, in line with "
                "Big 12 quarterbacks. Verified deal depth is limited."
            ),
            "key_value_drivers": [
                {"label": "Brand Strength", "signal": "High", "explanation": "Brand leads peers."},
                {"label": "Market Proof", "signal": "Moderate", "explanation": "Activity steady."},
                {"label": "Exposure", "signal": "Moderate", "explanation": "Routine usage."},
                {"label": "Risk", "signal": "Low", "explanation": "Operational risk minimal."},
            ],
            "driver_takeaway": "Brand Strength is the dominant driver; verified depth caps upside.",
        },
        "validation": {
            "market_context": "Market Context (Big 12 QBs (n=24)) Range: $10K - $40K Median: $20K",
            "comparable_tier": "Mid-tier QBs",
            "example_comparables": [],
            "takeaway": "Becht's benchmark aligns with comparable Big 12 QBs.",
            "comparable_state": "sparse",
            "positional_reference_athletes": [],
        },
        "confidence_risk": {
            "confidence_level": "Moderate",
            "confidence_note": "Moderate confidence: comparable depth is limited.",
            "risk_level": "Low",
            "risk_note": "Low risk: driven by stable operational signals.",
        },
        "detail": {
            "shap_attribution": "Brand reach drives lift.",
            "methodology": "Component model.",
            "inputs": "Inputs summary.",
        },
        "metadata": {
            "tier_version": "tier_v2",
            "tier_v1": "Mid-tier",
            "tier_v2": "Mid-tier",
            "cohort_window_days_used": 21,
            "season_state": "in_season",
            "cohort_size": 24,
            "cohort_fallback_step": 0,
            "comparable_state": "sparse",
            "comparable_sets_computed_at": "2026-05-20T00:00:00Z",
            "exposure_formula_version": "exposure_formula_v1",
            "exposure_formula_weights": {"proximity_weight": 0.6, "velocity_weight": 0.4},
            "rollout_phase": "phase4",
            "low_cohort_data": False,
            "athlete_benchmark_percentile_in_cohort": 55,
            "conference": "Big 12",
            "conference_tier": "power_5",
            "model_status": "production",
            "model_version": "gravity_v1_2026-04-14",
            "cohort_fit": "good",
            "range_quality": "normal",
            "report_id": "2026-05-20-RB-001",
        },
    }


def test_validate_report_returns_empty_for_good_report():
    assert validate_report(_good_report()) == []


def test_validate_report_flags_placeholder_conference():
    report = _good_report()
    report["metadata"]["conference"] = "Conference"
    errors = validate_report(report)
    assert any(e.code == "conference_placeholder" for e in errors)


def test_validate_report_flags_missing_conference():
    report = _good_report()
    report["metadata"]["conference"] = ""
    errors = validate_report(report)
    assert any(e.code == "conference_missing" for e in errors)


def test_validate_report_flags_dollar_format_leak_in_prose():
    report = _good_report()
    report["validation"]["market_context"] = "Range: $0.018M – $0.032M"
    errors = validate_report(report)
    assert any(e.code == "dollar_format_leak" for e in errors)


def test_validate_report_flags_percentile_over_99():
    report = _good_report()
    report["metadata"]["athlete_benchmark_percentile_in_cohort"] = 100
    errors = validate_report(report)
    assert any(e.code == "percentile_uncapped" for e in errors)


def test_validate_report_flags_fallback_high_confidence():
    report = _good_report()
    report["metadata"]["model_status"] = "fallback"
    report["confidence_risk"]["confidence_level"] = "High"
    errors = validate_report(report)
    assert any(e.code == "fallback_high_confidence" for e in errors)


def test_validate_report_flags_no_comparables_with_high_confidence():
    report = _good_report()
    report["metadata"]["comparable_state"] = "none"
    report["confidence_risk"]["confidence_level"] = "Moderate"
    errors = validate_report(report)
    assert any(e.code == "no_comparables_confidence_too_high" for e in errors)


def test_validate_report_flags_fallback_banner_missing_version():
    report = _good_report()
    report["metadata"]["model_status"] = "fallback"
    report["metadata"]["model_version"] = None
    report["confidence_risk"]["confidence_level"] = "Low"
    errors = validate_report(report)
    assert any(e.code == "fallback_banner_missing_version" for e in errors)


def test_validate_report_flags_forbidden_term_in_prose():
    report = _good_report()
    report["explanation"]["executive_summary"] = "BPXVR drives this athlete."
    errors = validate_report(report)
    assert any(e.code == "forbidden_term_in_prose" for e in errors)


def test_validate_report_flags_missing_report_id():
    report = _good_report()
    report["metadata"]["report_id"] = ""
    errors = validate_report(report)
    assert any(e.code == "report_id_missing" for e in errors)


def test_validate_report_flags_tier_v1_with_asterisk():
    report = _good_report()
    report["metadata"]["tier_version"] = "tier_v1"
    report["value"]["tier_tag"] = "Top-tier*"
    errors = validate_report(report)
    assert any(e.code == "tier_version_mismatch" for e in errors)


def test_validate_report_handles_non_dict_input():
    errors = validate_report(None)  # type: ignore[arg-type]
    assert errors and errors[0].code == "invalid_payload"
