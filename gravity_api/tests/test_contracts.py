"""Lightweight shape checks (no database)."""

import asyncio
from datetime import datetime, timedelta, timezone

from gravity_api.services.compatibility import compatibility_score
from gravity_api.services.csc_report_builder import build_csc_report_json


def test_compatibility_score_shape():
    out = compatibility_score(
        {
            "brand_score": 60,
            "proof_score": 55,
            "proximity_score": 50,
            "velocity_score": 50,
            "risk_score": 20,
        },
        {
            "reach_score": 70,
            "authenticity_score": 60,
            "value_score": 65,
            "fit_score": 70,
            "stability_score": 80,
        },
        {},
    )
    assert "compatibility_score" in out
    assert "subscores" in out
    assert 0 <= float(out["compatibility_score"]) <= 100


def test_compatibility_risk_alignment_prefers_high_safety_score():
    safe = compatibility_score(
        {"brand_score": 60, "proof_score": 55, "proximity_score": 50, "velocity_score": 50, "risk_score": 80},
        {"stability_score": 80},
        {},
    )
    risky = compatibility_score(
        {"brand_score": 60, "proof_score": 55, "proximity_score": 50, "velocity_score": 50, "risk_score": 20},
        {"stability_score": 80},
        {},
    )
    assert safe["subscores"]["alignment_risk_stability"] > risky["subscores"]["alignment_risk_stability"]


def test_csc_report_keys_minimal():
    sample = {
        "value": {
            "total_benchmark": 10000,
            "range_low": 7000,
            "range_high": 15000,
            "tier_tag": "Mid-tier",
            "confidence_tag": "Moderate Confidence",
        },
        "explanation": {
            "executive_summary": "x",
            "key_value_drivers": [],
            "driver_takeaway": "y",
        },
        "validation": {
            "market_context": "z",
            "comparable_tier": "t",
            "example_comparables": [],
            "takeaway": "k",
            "comparable_state": "sufficient",
            "positional_reference_athletes": [],
        },
        "confidence_risk": {
            "confidence_level": "Moderate",
            "confidence_note": "c",
            "risk_level": "Moderate",
            "risk_note": "r",
        },
        "detail": {
            "shap_attribution": "s",
            "methodology": "m",
            "inputs": "i",
        },
        "metadata": {
            "tier_version": "tier_v1",
            "tier_v1": "Mid-tier",
            "tier_v2": "Mid-tier",
            "cohort_window_days_used": 21,
            "season_state": "in_season",
            "cohort_size": 24,
            "cohort_fallback_step": 0,
            "comparable_state": "sufficient",
            "comparable_sets_computed_at": "2026-05-20T00:00:00Z",
            "exposure_formula_version": "exposure_formula_v1",
            "exposure_formula_weights": {"proximity_weight": 0.6, "velocity_weight": 0.4},
            "rollout_phase": "phase1",
            "low_cohort_data": False,
            "athlete_benchmark_percentile_in_cohort": 55.0,
        },
    }
    required = set(sample.keys())
    assert required == {
        "value",
        "explanation",
        "validation",
        "confidence_risk",
        "detail",
        "metadata",
    }
    assert sample["confidence_risk"]["confidence_level"] in {"High", "Moderate", "Low"}
    assert sample["confidence_risk"]["risk_level"] in {"High", "Moderate", "Low"}


# ---------------------------------------------------------------------------
# Tier-version invariant: metadata.tier_version must reflect the methodology
# that produced value.tier_tag. tier_v1 (absolute) labels never carry "*";
# tier_v2 (cohort percentile) labels gain "*" only when cohort fallback hits
# step 3 (the absolute-methodology footnote).
# ---------------------------------------------------------------------------

class _MiniFakeDb:
    def __init__(self, rollout_phase: str, cohort_rows):
        self._rollout_phase = rollout_phase
        self._cohort_rows = cohort_rows
        self._call = 0

    async def fetchrow(self, query, *args):
        if "FROM athletes WHERE id = $1" in query:
            return {
                "id": "subject-1",
                "name": "Test Player",
                "sport": "CFB",
                "conference": "SEC",
                "school": "",
                "position": "QB",
                "position_group": "QB",
                "nil_valuation_raw": 250000,
            }
        if "jsonb_typeof(shap_values)" in query:
            return None
        if "FROM athlete_gravity_scores" in query:
            return {
                "gravity_score": 81.2,
                "brand_score": 78.0,
                "proof_score": 70.0,
                "proximity_score": 62.0,
                "velocity_score": 58.0,
                "risk_score": 18.0,
                "confidence": 0.7,
                "dollar_p10_usd": 150000,
                "dollar_p50_usd": 250000,
                "dollar_p90_usd": 400000,
                "model_version": "gravity_v1_2026-04-14",
                "calculated_at": "2026-05-12T10:15:00Z",
            }
        if "FROM season_states" in query:
            return {"state": "in_season", "cohort_window_days": 21}
        if "SELECT current_phase FROM csc_tier_rollout" in query:
            return {"current_phase": self._rollout_phase}
        if "FROM csc_tier_account_overrides" in query:
            return None
        return None

    async def fetch(self, query, *args):
        if "FROM exposure_formulas" in query:
            return [
                {
                    "version": "exposure_formula_v1",
                    "proximity_weight": 0.6,
                    "velocity_weight": 0.4,
                    "is_active": True,
                }
            ]
        if "FROM comparable_sets cs" in query:
            return []
        if "WITH latest AS" in query:
            self._call += 1
            return self._cohort_rows
        if "ORDER BY ABS(s.gravity_score - $5) ASC" in query:
            return []
        return []

    async def fetchval(self, query, *args):
        if "SELECT MIN(calculated_at)" in query:
            return datetime.now(tz=timezone.utc) - timedelta(days=45)
        return None


def _build(rollout_phase: str, cohort_rows):
    db = _MiniFakeDb(rollout_phase, cohort_rows)
    return asyncio.run(build_csc_report_json(db, "subject-1", {}))


_LARGE_COHORT = [
    {
        "id": f"c{i}",
        "name": f"Cohort {i}",
        "dollar_p50_usd": 150000 + i * 5000,
        "velocity_score": 50 + (i % 10),
    }
    for i in range(20)
]


def test_tier_version_stamp_matches_label_methodology_tier_v1():
    report = _build("phase1", _LARGE_COHORT)
    assert report["metadata"]["tier_version"] == "tier_v1"
    # tier_v1 is absolute methodology — never carries the "*" footnote.
    assert not str(report["value"]["tier_tag"] or "").endswith("*")


def test_tier_version_stamp_matches_label_methodology_tier_v2():
    report = _build("phase3", _LARGE_COHORT)
    assert report["metadata"]["tier_version"] == "tier_v2"
    # tier_v2 with sufficient cohort: no "*" suffix.
    assert not str(report["value"]["tier_tag"] or "").endswith("*")


def test_tier_version_stamp_step_three_v2_has_asterisk():
    tiny = [
        {"id": "c1", "name": "Cohort 1", "dollar_p50_usd": 180000, "velocity_score": 50}
    ]
    report = _build("phase3", tiny)
    assert report["metadata"]["tier_version"] == "tier_v2"
    assert report["metadata"]["cohort_fallback_step"] >= 3
    assert str(report["value"]["tier_tag"] or "").endswith("*")


# ---------------------------------------------------------------------------
# v3 schema invariants — every build_csc_report_json output must carry the new
# metadata fields and the nested detail.blocks structure, regardless of tier
# methodology or cohort fallback step.
# ---------------------------------------------------------------------------

def test_v3_metadata_carries_report_id():
    report = _build("phase3", _LARGE_COHORT)
    report_id = report["metadata"].get("report_id")
    assert isinstance(report_id, str) and report_id
    # YYYY-MM-DD-INITIALS-NNN pattern.
    parts = report_id.split("-")
    assert len(parts) >= 5  # YYYY MM DD INITIALS NNN
    assert parts[4].isdigit() and len(parts[4]) == 3


def test_v3_metadata_carries_model_status():
    report = _build("phase3", _LARGE_COHORT)
    assert report["metadata"].get("model_status") in {"production", "fallback", "unknown"}
    assert report["metadata"].get("model_version")


def test_v3_metadata_carries_cohort_fit():
    report = _build("phase3", _LARGE_COHORT)
    assert report["metadata"].get("cohort_fit") in {"good", "edge", "poor"}


def test_v3_metadata_carries_range_quality():
    report = _build("phase3", _LARGE_COHORT)
    assert report["metadata"].get("range_quality") in {"normal", "wide", "unavailable"}


def test_v3_detail_blocks_populated():
    report = _build("phase3", _LARGE_COHORT)
    blocks = report["detail"].get("blocks")
    assert isinstance(blocks, dict)
    assert blocks.get("methodology")
    assert blocks.get("cohort")
    assert blocks.get("comparables")
    assert blocks.get("provenance")


def test_v3_provenance_block_carries_report_id_and_status():
    report = _build("phase3", _LARGE_COHORT)
    provenance = report["detail"]["blocks"]["provenance"]
    assert provenance.get("report_id") == report["metadata"]["report_id"]
    assert provenance.get("tier_version") == report["metadata"]["tier_version"]
    assert provenance.get("model_status") == report["metadata"]["model_status"]


def test_v3_percentile_never_exceeds_99():
    report = _build("phase3", _LARGE_COHORT)
    pct = report["metadata"].get("athlete_benchmark_percentile_in_cohort")
    if pct is not None:
        assert pct <= 99.0


def test_v3_confidence_caps_at_low_when_cohort_step_two_or_more():
    tiny = [
        {"id": "c1", "name": "Cohort 1", "dollar_p50_usd": 180000, "velocity_score": 50}
    ]
    report = _build("phase3", tiny)
    if report["metadata"]["cohort_fallback_step"] >= 2:
        assert report["confidence_risk"]["confidence_level"] == "Low"
