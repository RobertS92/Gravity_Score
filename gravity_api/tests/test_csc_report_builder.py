import asyncio

from gravity_api.services.csc_report_builder import build_csc_report_json


class _FakeDb:
    def __init__(
        self,
        athlete,
        latest_score,
        comparable_rows,
        subject_deals,
        latest_score_with_shap=None,
    ):
        self._athlete = athlete
        self._latest_score = latest_score
        self._comparable_rows = comparable_rows
        self._subject_deals = subject_deals
        self._latest_score_with_shap = latest_score_with_shap

    async def fetchrow(self, query, *args):
        if "FROM athletes WHERE id = $1" in query:
            return self._athlete
        if "jsonb_typeof(shap_values)" in query:
            return self._latest_score_with_shap
        if "FROM athlete_gravity_scores" in query:
            return self._latest_score
        return None

    async def fetch(self, query, *args):
        if "FROM comparable_sets cs" in query:
            return self._comparable_rows
        if "SELECT deal_value FROM athlete_nil_deals" in query:
            return self._subject_deals
        return []


def test_comparable_nil_estimate_falls_back_to_model_value():
    db = _FakeDb(
        athlete={
            "id": "subject-1",
            "name": "Jordan Star",
            "sport": "CFB",
            "position": "QB",
            "nil_valuation_raw": 180000,
        },
        latest_score={
            "gravity_score": 81.2,
            "brand_score": 77.4,
            "proof_score": 70.1,
            "risk_score": 18.0,
            "dollar_p10_usd": 150000,
            "dollar_p50_usd": 210000,
            "dollar_p90_usd": 290000,
            "shap_values": {"brand_fit": 0.42},
        },
        comparable_rows=[
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
                "nil_valuation_raw": None,
            }
        ],
        subject_deals=[],
    )

    report = asyncio.run(build_csc_report_json(db, "subject-1", {"confidence_min": 0.75}))
    row = report["comparables_analysis"][0]
    assert row["nil_valuation_consensus"] == 265000.0
    assert row["verified_source"] == "Model Estimate"
    assert row["deal_structure"] == "Structure pending verification"


def test_executive_summary_is_fully_composed_and_not_partial():
    db = _FakeDb(
        athlete={
            "id": "subject-2",
            "name": "Avery Profile",
            "sport": "CFB",
            "position": "WR",
            "nil_valuation_raw": 240000,
        },
        latest_score={
            "gravity_score": 74.5,
            "brand_score": 69.0,
            "proof_score": 66.3,
            "risk_score": 23.7,
            "dollar_p10_usd": 180000,
            "dollar_p50_usd": 250000,
            "dollar_p90_usd": 340000,
            "shap_values": {"proof": 0.31},
        },
        comparable_rows=[
            {
                "id": "comp-2",
                "name": "Riley Match",
                "school": "Tech",
                "position": "WR",
                "gravity_score": 73.2,
                "brand_score": 71.1,
                "similarity_score": 0.82,
                "deal_type": "HYBRID",
                "verified": True,
                "deal_value": 315000,
                "verified_deal_count": 2,
                "dollar_p50_usd": 300000,
                "nil_valuation_raw": None,
            }
        ],
        subject_deals=[{"deal_value": 260000}, {"deal_value": 300000}],
    )

    report = asyncio.run(build_csc_report_json(db, "subject-2", {"confidence_min": 0.7}))
    summary = report["executive_summary"]
    assert len(summary) > 160
    assert "high-confidence comparables" in summary
    assert "within an estimated band" in summary
    assert "None" not in summary


def test_comparable_confidence_normalizes_percent_and_bps_scale():
    db = _FakeDb(
        athlete={
            "id": "subject-4",
            "name": "Scale Test",
            "sport": "CFB",
            "position": "QB",
            "nil_valuation_raw": 210000,
        },
        latest_score={
            "gravity_score": 77.0,
            "brand_score": 71.0,
            "proof_score": 67.4,
            "risk_score": 21.3,
            "dollar_p10_usd": 140000,
            "dollar_p50_usd": 220000,
            "dollar_p90_usd": 300000,
            "shap_values": {},
        },
        comparable_rows=[
            {
                "id": "comp-pct",
                "name": "Percent Input",
                "school": "State U",
                "position": "QB",
                "gravity_score": 76.3,
                "brand_score": 69.8,
                "similarity_score": 81.98,
                "deal_type": "HYBRID",
                "verified": True,
                "deal_value": 255000,
                "verified_deal_count": 1,
                "dollar_p50_usd": None,
                "nil_valuation_raw": None,
            },
            {
                "id": "comp-bps",
                "name": "Bps Input",
                "school": "State U",
                "position": "QB",
                "gravity_score": 75.9,
                "brand_score": 68.5,
                "similarity_score": 8198,
                "deal_type": "fixed fee",
                "verified": False,
                "deal_value": None,
                "verified_deal_count": 0,
                "dollar_p50_usd": 200000,
                "nil_valuation_raw": None,
            },
        ],
        subject_deals=[],
    )

    report = asyncio.run(build_csc_report_json(db, "subject-4", {"confidence_min": 0.7}))
    pct, bps = report["comparables_analysis"]
    assert round(float(pct["confidence"]), 4) == 0.8198
    assert round(float(bps["confidence"]), 4) == 0.8198
    assert pct["verified_source"] == "Direct Verification"
    assert bps["deal_structure"] == "Cash / Flat Fee"


def test_nil_range_note_uses_model_range_when_subject_deals_missing():
    db = _FakeDb(
        athlete={
            "id": "subject-3",
            "name": "Casey Value",
            "sport": "CFB",
            "position": "RB",
            "nil_valuation_raw": None,
        },
        latest_score={
            "gravity_score": 69.8,
            "brand_score": 64.0,
            "proof_score": 61.8,
            "risk_score": 29.0,
            "dollar_p10_usd": 120000,
            "dollar_p50_usd": 165000,
            "dollar_p90_usd": 240000,
            "shap_values": {},
        },
        comparable_rows=[],
        subject_deals=[],
    )

    report = asyncio.run(build_csc_report_json(db, "subject-3", {}))
    assert "model-derived valuation range" in report["nil_range_note"]
    assert "$120,000–$240,000" in report["nil_range_note"]
    assert "does not expose SHAP detail" in report["shap_narrative"]


def test_shap_narrative_uses_latest_explainable_revision_when_current_revision_lacks_shap():
    db = _FakeDb(
        athlete={
            "id": "subject-5",
            "name": "Harper Explainable",
            "sport": "CFB",
            "position": "WR",
            "nil_valuation_raw": 200000,
        },
        latest_score={
            "gravity_score": 76.2,
            "brand_score": 71.4,
            "proof_score": 67.2,
            "risk_score": 24.0,
            "dollar_p10_usd": 160000,
            "dollar_p50_usd": 220000,
            "dollar_p90_usd": 300000,
            "model_version": "v3.2",
            "calculated_at": "2026-05-12T10:15:00Z",
            "shap_values": {},
        },
        comparable_rows=[],
        subject_deals=[],
        latest_score_with_shap={
            "model_version": "v3.1",
            "calculated_at": "2026-05-06T09:00:00Z",
            "shap_values": {"brand": 0.42, "risk": -0.21},
        },
    )

    report = asyncio.run(build_csc_report_json(db, "subject-5", {}))
    narrative = report["shap_narrative"]
    assert "most recent explainable revision" in narrative
    assert "brand (+0.42)" in narrative
    assert "risk (-0.21)" in narrative
    assert "v3.1" in narrative


def test_shap_narrative_fallback_mentions_revision_when_no_shap_exists():
    db = _FakeDb(
        athlete={
            "id": "subject-6",
            "name": "Riley Unsupported",
            "sport": "CFB",
            "position": "QB",
            "nil_valuation_raw": 180000,
        },
        latest_score={
            "gravity_score": 70.3,
            "brand_score": 64.2,
            "proof_score": 61.5,
            "risk_score": 33.0,
            "dollar_p10_usd": 110000,
            "dollar_p50_usd": 165000,
            "dollar_p90_usd": 230000,
            "model_version": "v4.0-no-shap",
            "calculated_at": "2026-05-13T11:30:00Z",
            "shap_values": {},
        },
        comparable_rows=[],
        subject_deals=[],
        latest_score_with_shap=None,
    )

    report = asyncio.run(build_csc_report_json(db, "subject-6", {}))
    narrative = report["shap_narrative"]
    assert "v4.0-no-shap" in narrative
    assert "does not expose SHAP detail" in narrative
    assert "deterministic attribution" in narrative
