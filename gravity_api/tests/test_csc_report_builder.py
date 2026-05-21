import asyncio
from datetime import datetime, timedelta, timezone

from gravity_api.services.csc_report_builder import build_csc_report_json


class _FakeDb:
    def __init__(
        self,
        *,
        athlete,
        latest_score,
        comparable_rows=None,
        latest_score_with_shap=None,
        cohort_rows_by_call=None,
        positional_refs=None,
        active_formula_rows=None,
        rollout_phase="phase1",
    ):
        self._athlete = athlete
        self._latest_score = latest_score
        self._comparable_rows = comparable_rows or []
        self._latest_score_with_shap = latest_score_with_shap
        self._cohort_rows_by_call = cohort_rows_by_call or [[], [], []]
        self._positional_refs = positional_refs or []
        self._active_formula_rows = active_formula_rows or [
            {
                "version": "exposure_formula_v1",
                "proximity_weight": 0.6,
                "velocity_weight": 0.4,
                "is_active": True,
            }
        ]
        self._rollout_phase = rollout_phase
        self._cohort_call = 0

    async def fetchrow(self, query, *args):
        if "FROM athletes WHERE id = $1" in query:
            return self._athlete
        if "jsonb_typeof(shap_values)" in query:
            return self._latest_score_with_shap
        if "FROM athlete_gravity_scores" in query:
            return self._latest_score
        if "FROM season_states" in query:
            return {"state": "in_season", "cohort_window_days": 21}
        if "SELECT current_phase FROM csc_tier_rollout" in query:
            return {"current_phase": self._rollout_phase}
        if "FROM csc_tier_account_overrides" in query:
            return None
        return None

    async def fetch(self, query, *args):
        if "FROM exposure_formulas" in query:
            return self._active_formula_rows
        if "FROM comparable_sets cs" in query:
            return self._comparable_rows
        if "WITH latest AS" in query:
            idx = min(self._cohort_call, len(self._cohort_rows_by_call) - 1)
            self._cohort_call += 1
            return self._cohort_rows_by_call[idx]
        if "ORDER BY ABS(s.gravity_score - $5) ASC" in query:
            return self._positional_refs
        return []

    async def fetchval(self, query, *args):
        if "SELECT MIN(calculated_at)" in query:
            return datetime.now(tz=timezone.utc) - timedelta(days=45)
        return None


def _base_athlete():
    return {
        "id": "subject-1",
        "name": "Jordan Star",
        "sport": "CFB",
        "conference": "Big 12",
        "position": "QB",
        "position_group": "QB",
        "nil_valuation_raw": 180000,
    }


def _base_score():
    return {
        "gravity_score": 81.2,
        "brand_score": 77.4,
        "proof_score": 70.1,
        "proximity_score": 62.0,
        "velocity_score": 58.0,
        "risk_score": 18.0,
        "confidence": 0.73,
        "dollar_p10_usd": 150000,
        "dollar_p50_usd": 210000,
        "dollar_p90_usd": 290000,
        "model_version": "v3.2",
        "calculated_at": "2026-05-12T10:15:00Z",
        "shap_values": {"brand_fit": 0.42},
    }


def test_csc_v2_metadata_and_structure_are_present():
    cohort_rows = [
        {
            "id": "a1",
            "name": "A1",
            "dollar_p50_usd": 190000,
            "nil_valuation_raw": None,
            "velocity_score": 50,
        },
        {
            "id": "a2",
            "name": "A2",
            "dollar_p50_usd": 210000,
            "nil_valuation_raw": None,
            "velocity_score": 58,
        },
        {
            "id": "a3",
            "name": "A3",
            "dollar_p50_usd": 230000,
            "nil_valuation_raw": None,
            "velocity_score": 61,
        },
        {
            "id": "a4",
            "name": "A4",
            "dollar_p50_usd": 260000,
            "nil_valuation_raw": None,
            "velocity_score": 65,
        },
        {
            "id": "a5",
            "name": "A5",
            "dollar_p50_usd": 280000,
            "nil_valuation_raw": None,
            "velocity_score": 70,
        },
    ]
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=_base_score(),
        comparable_rows=[],
        cohort_rows_by_call=[cohort_rows],
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {"confidence_min": 0.75}))
    assert report["value"]["tier_tag"] is not None
    assert report["metadata"]["tier_version"] in {"tier_v1", "tier_v2"}
    assert report["metadata"]["exposure_formula_version"] == "exposure_formula_v1"
    assert report["validation"]["comparable_state"] in {"sufficient", "sparse", "none"}


def test_comparable_state_none_yields_positional_references_and_low_confidence():
    cohort_rows = [
        {"id": f"a{i}", "name": f"A{i}", "dollar_p50_usd": 150000 + i * 10000, "nil_valuation_raw": None, "velocity_score": 55}
        for i in range(1, 6)
    ]
    positional_refs = [
        {"id": "r1", "name": "Ref 1", "school": "U1", "position": "QB", "gravity_score": 79.0, "brand_score": 70.0, "dollar_p50_usd": 180000},
        {"id": "r2", "name": "Ref 2", "school": "U2", "position": "QB", "gravity_score": 78.0, "brand_score": 68.0, "dollar_p50_usd": 170000},
        {"id": "r3", "name": "Ref 3", "school": "U3", "position": "QB", "gravity_score": 77.0, "brand_score": 66.0, "dollar_p50_usd": 160000},
    ]
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=_base_score(),
        comparable_rows=[],
        cohort_rows_by_call=[cohort_rows],
        positional_refs=positional_refs,
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {"confidence_min": 0.8}))
    assert report["validation"]["comparable_state"] == "none"
    assert len(report["validation"]["positional_reference_athletes"]) == 3
    assert report["confidence_risk"]["confidence_level"] == "Low"


def test_sparse_comparables_state_and_metadata_stamp():
    cohort_rows = [
        {"id": f"a{i}", "name": f"A{i}", "dollar_p50_usd": 140000 + i * 10000, "nil_valuation_raw": None, "velocity_score": 50}
        for i in range(1, 6)
    ]
    comparables = [
        {
            "id": "comp-1",
            "name": "Taylor Comp",
            "school": "State U",
            "position": "QB",
            "gravity_score": 79.0,
            "brand_score": 73.0,
            "similarity_score": 0.89,
            "deal_type": None,
            "verified": False,
            "deal_value": None,
            "verified_deal_count": 0,
            "dollar_p50_usd": 265000,
            "created_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
        },
        {
            "id": "comp-2",
            "name": "Jordan Comp",
            "school": "Tech U",
            "position": "QB",
            "gravity_score": 78.0,
            "brand_score": 71.0,
            "similarity_score": 0.85,
            "deal_type": "hybrid",
            "verified": True,
            "deal_value": 230000,
            "verified_deal_count": 2,
            "dollar_p50_usd": 240000,
            "created_at": datetime(2026, 5, 2, tzinfo=timezone.utc),
        },
    ]
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=_base_score(),
        comparable_rows=comparables,
        cohort_rows_by_call=[cohort_rows],
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {"comparables_count": 5}))
    assert report["validation"]["comparable_state"] == "sparse"
    assert report["metadata"]["comparable_sets_computed_at"] is not None
    assert report["metadata"]["comparable_state"] == "sparse"


def test_cohort_fallback_step_three_caps_confidence_and_suffixes_tier():
    # All fallback calls return <5 rows, forcing step 3 absolute mode.
    small = [{"id": "x1", "name": "X1", "dollar_p50_usd": 180000, "nil_valuation_raw": None, "velocity_score": 50}]
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=_base_score(),
        comparable_rows=[],
        cohort_rows_by_call=[small, small, small],
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {}))
    assert report["metadata"]["cohort_fallback_step"] == 3
    assert report["metadata"]["low_cohort_data"] is True
    assert report["confidence_risk"]["confidence_level"] in {"Low", "Moderate"}
    assert report["value"]["tier_tag"].endswith("*")


def test_exposure_driver_uses_formula_weights_and_velocity():
    score = _base_score()
    score["proximity_score"] = 70.0
    score["velocity_score"] = 50.0
    cohort_rows = [
        {"id": f"a{i}", "name": f"A{i}", "dollar_p50_usd": 160000 + i * 10000, "nil_valuation_raw": None, "velocity_score": 55}
        for i in range(1, 6)
    ]
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=score,
        comparable_rows=[],
        cohort_rows_by_call=[cohort_rows],
        active_formula_rows=[
            {
                "version": "exposure_formula_v9",
                "proximity_weight": 0.7,
                "velocity_weight": 0.3,
                "is_active": True,
            }
        ],
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {}))
    exposure_driver = next(d for d in report["explanation"]["key_value_drivers"] if d["label"] == "Exposure")
    assert "0.7*proximity + 0.3*velocity" in exposure_driver["explanation"]
    assert report["metadata"]["exposure_formula_version"] == "exposure_formula_v9"
