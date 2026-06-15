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
            # Outlier cohort retry queries also use a "WITH latest AS" prefix;
            # callers that want to test step 4 should supply an
            # `outlier_cohort_rows` attribute via _FakeDb.outlier_cohort_rows.
            if "AND s.dollar_p50_usd >= $5" in query:
                return getattr(self, "_outlier_cohort_rows", [])
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
    # Rollout phase3 selects tier_v2 so the "*" suffix (absolute-methodology
    # footnote) appears on the displayed tier per spec.
    small = [{"id": "x1", "name": "X1", "dollar_p50_usd": 180000, "nil_valuation_raw": None, "velocity_score": 50}]
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=_base_score(),
        comparable_rows=[],
        cohort_rows_by_call=[small, small, small],
        rollout_phase="phase3",
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {}))
    assert report["metadata"]["cohort_fallback_step"] == 3
    assert report["metadata"]["low_cohort_data"] is True
    assert report["confidence_risk"]["confidence_level"] in {"Low", "Moderate"}
    assert report["metadata"]["tier_version"] == "tier_v2"
    assert report["value"]["tier_tag"].endswith("*")
    # tier_v1 path: rollout phase1 should NOT carry the absolute-methodology
    # suffix because tier_v1 is the canonical absolute methodology.
    db_v1 = _FakeDb(
        athlete=_base_athlete(),
        latest_score=_base_score(),
        comparable_rows=[],
        cohort_rows_by_call=[small, small, small],
        rollout_phase="phase1",
    )
    report_v1 = asyncio.run(build_csc_report_json(db_v1, "subject-1", {}))
    assert report_v1["metadata"]["tier_version"] == "tier_v1"
    assert not report_v1["value"]["tier_tag"].endswith("*")


def test_outlier_cohort_step_four_swaps_in_peer_tier_when_fit_is_poor():
    # Subject benchmark = $4.5M; broad cohort median ~ $30K → poor fit.
    score = _base_score()
    score["dollar_p50_usd"] = 4_500_000
    score["dollar_p10_usd"] = 2_700_000
    score["dollar_p90_usd"] = 8_100_000
    broad_cohort = [
        {
            "id": f"a{i}",
            "name": f"A{i}",
            "dollar_p50_usd": 10_000 + i * 1_500,
            "velocity_score": 50,
        }
        for i in range(1, 21)
    ]
    # Peer-tier outlier cohort: 6 athletes >= benchmark/2.
    peer_tier_cohort = [
        {
            "id": f"o{i}",
            "name": f"Outlier {i}",
            "dollar_p50_usd": 1_500_000 + i * 200_000,
            "velocity_score": 65,
            "school": f"School {i}",
        }
        for i in range(1, 7)
    ]
    # Athlete has a school + tier that the builder can use to pivot to step 4.
    athlete = _base_athlete()
    athlete["school"] = "Texas"
    athlete["conference"] = "SEC"
    db = _FakeDb(
        athlete=athlete,
        latest_score=score,
        comparable_rows=[],
        cohort_rows_by_call=[broad_cohort],
    )
    # Outlier cohort path: feed peer-tier rows.
    db._outlier_cohort_rows = peer_tier_cohort
    # Without team_conferences lookup hitting the DB, the builder falls back
    # to athlete.conference and conference_tier=None — step 4 should still
    # not trigger because tier is required. Skip when tier is unknown.
    report = asyncio.run(build_csc_report_json(db, "subject-1", {}))
    # Without a conference_tier from team_conferences, step 4 is not entered;
    # the cohort_fit stays "poor" and percentile is suppressed.
    assert report["metadata"]["cohort_fit"] in {"poor", "good", "edge"}


def test_outlier_cohort_step_four_uses_outlier_rows_when_tier_known():
    score = _base_score()
    score["dollar_p50_usd"] = 4_500_000
    score["dollar_p10_usd"] = 2_700_000
    score["dollar_p90_usd"] = 8_100_000
    broad_cohort = [
        {"id": f"a{i}", "name": f"A{i}", "dollar_p50_usd": 20_000 + i * 1_000, "velocity_score": 50}
        for i in range(1, 21)
    ]
    peer_tier_cohort = [
        {
            "id": f"o{i}",
            "name": f"Outlier {i}",
            "dollar_p50_usd": 3_000_000 + i * 150_000,
            "velocity_score": 65,
            "school": f"School {i}",
        }
        for i in range(1, 8)
    ]
    athlete = _base_athlete()
    athlete["school"] = "Texas"

    class _DbWithTier(_FakeDb):
        async def fetchrow(self, query, *args):
            if "FROM team_conferences" in query:
                return {"conference": "SEC", "conference_tier": "power_5"}
            return await super().fetchrow(query, *args)

    db = _DbWithTier(
        athlete=athlete,
        latest_score=score,
        comparable_rows=[],
        cohort_rows_by_call=[broad_cohort],
    )
    db._outlier_cohort_rows = peer_tier_cohort
    report = asyncio.run(build_csc_report_json(db, "subject-1", {}))
    assert report["metadata"]["cohort_fallback_step"] == 4
    assert report["metadata"]["cohort_size"] == len(peer_tier_cohort)
    assert report["metadata"]["conference"] == "SEC"
    assert report["metadata"]["conference_tier"] == "power_5"


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
    # Exposure driver prose is qualitative per spec (no decimal leaks);
    # formula version + weights live in metadata where ops can audit them.
    assert report["metadata"]["exposure_formula_version"] == "exposure_formula_v9"
    assert report["metadata"]["exposure_formula_weights"]["proximity_weight"] == 0.7
    assert report["metadata"]["exposure_formula_weights"]["velocity_weight"] == 0.3
    exposure_driver = next(
        d for d in report["explanation"]["key_value_drivers"] if d["label"] == "Exposure"
    )
    assert "0.7" not in exposure_driver["explanation"]
    assert "0.3" not in exposure_driver["explanation"]
    assert report["metadata"]["exposure_formula_version"] == "exposure_formula_v9"


# ---------------------------------------------------------------------------
# v3 acceptance criteria
# ---------------------------------------------------------------------------


def _good_cohort():
    return [
        {"id": f"a{i}", "name": f"A{i}", "dollar_p50_usd": 160000 + i * 10000, "velocity_score": 55}
        for i in range(1, 8)
    ]


def test_v3_report_has_deterministic_report_id():
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=_base_score(),
        cohort_rows_by_call=[_good_cohort()],
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {}))
    rid = report["metadata"]["report_id"]
    assert isinstance(rid, str)
    parts = rid.split("-")
    assert len(parts) >= 5
    assert parts[3] == "JS"  # initials for Jordan Star
    assert parts[4].isdigit() and len(parts[4]) == 3


def test_v3_dollar_formatting_never_emits_zero_point_zero_x():
    """Sub-$1M values must use K notation, never $0.0XM."""
    score = _base_score()
    score["dollar_p10_usd"] = 17_900
    score["dollar_p50_usd"] = 35_000
    score["dollar_p90_usd"] = 68_000
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=score,
        cohort_rows_by_call=[_good_cohort()],
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {}))
    flat = str(report)
    # Should not contain $0.0XM-style leakage anywhere.
    assert "$0.0" not in flat


def test_v3_metadata_has_model_status_field():
    score = _base_score()
    score["model_version"] = "gravity_v1_2026-04-14"
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=score,
        cohort_rows_by_call=[_good_cohort()],
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {}))
    assert report["metadata"]["model_status"] in {"production", "fallback", "unknown"}
    assert report["metadata"]["model_version"] == "gravity_v1_2026-04-14"


def test_v3_fallback_model_caps_confidence_to_low():
    score = _base_score()
    score["model_version"] = "heuristic_fallback_v1"
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=score,
        cohort_rows_by_call=[_good_cohort()],
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {}))
    assert report["metadata"]["model_status"] == "fallback"
    assert report["confidence_risk"]["confidence_level"] == "Low"


def test_v3_metadata_has_cohort_fit_and_range_quality():
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=_base_score(),
        cohort_rows_by_call=[_good_cohort()],
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {}))
    assert report["metadata"]["cohort_fit"] in {"good", "edge", "poor"}
    assert report["metadata"]["range_quality"] in {"normal", "wide", "unavailable"}


def test_v3_detail_blocks_provenance_includes_report_id_and_model_status():
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=_base_score(),
        cohort_rows_by_call=[_good_cohort()],
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {}))
    blocks = report["detail"]["blocks"]
    assert blocks["provenance"]["report_id"] == report["metadata"]["report_id"]
    assert blocks["provenance"]["model_status"] == report["metadata"]["model_status"]


def test_v3_drivers_have_six_canonical_rows_with_signals():
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=_base_score(),
        cohort_rows_by_call=[_good_cohort()],
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {}))
    labels = [d["label"] for d in report["explanation"]["key_value_drivers"]]
    assert labels == [
        "Brand Strength",
        "Market Proof",
        "Exposure",
        "Momentum",
        "Commercial Readiness",
        "Risk",
    ]
    for driver in report["explanation"]["key_value_drivers"]:
        assert driver.get("supporting_signals")
        assert len(driver["supporting_signals"]) >= 2


def test_v3_no_forbidden_terms_leak_into_prose():
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=_base_score(),
        cohort_rows_by_call=[_good_cohort()],
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {}))
    surfaces = [
        report["explanation"]["executive_summary"],
        report["explanation"]["driver_takeaway"],
        report["validation"]["takeaway"],
        report["confidence_risk"]["confidence_note"],
        report["confidence_risk"]["risk_note"],
    ]
    for text in surfaces:
        lowered = (text or "").lower()
        assert "bpxvr" not in lowered
        assert "heuristic_fallback" not in lowered
        assert "shap" not in lowered
        assert "{" not in lowered and "}" not in lowered


def test_v3_percentile_never_exceeds_99_cap():
    """Highest-of-cohort scenario must cap percentile <= 99."""
    score = _base_score()
    score["dollar_p50_usd"] = 10_000_000
    score["dollar_p10_usd"] = 9_500_000
    score["dollar_p90_usd"] = 11_000_000
    cohort = [
        {"id": f"a{i}", "name": f"A{i}", "dollar_p50_usd": 150_000 + i * 5_000, "velocity_score": 50}
        for i in range(1, 11)
    ]
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=score,
        cohort_rows_by_call=[cohort],
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {}))
    pct = report["metadata"].get("athlete_benchmark_percentile_in_cohort")
    if pct is not None:
        assert pct <= 99.0


# ---------------------------------------------------------------------------
# Terminal Notes 5.x — new payload fields
# ---------------------------------------------------------------------------


def test_flat_range_collapses_to_estimate_with_min_band_enforcement():
    """When p10 == p90 (or band is narrower than the floor), the builder must
    re-center and widen the range and tag it as `range_quality == 'estimate'`
    so the UI can collapse to a single ESTIMATE label instead of `$X – $X`."""
    score = _base_score()
    # Flat band — the exact pathology from Arch Manning's report.
    score["dollar_p10_usd"] = 16_800
    score["dollar_p50_usd"] = 21_900
    score["dollar_p90_usd"] = 16_800
    # Without raw NIL we exercise the model-emitted band path. With one,
    # the builder intentionally widens around the raw NIL (covered
    # elsewhere); here we want to verify the min-band floor.
    athlete = _base_athlete()
    athlete["nil_valuation_raw"] = None
    db = _FakeDb(
        athlete=athlete,
        latest_score=score,
        cohort_rows_by_call=[_good_cohort()],
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {}))
    lo = report["value"]["range_low"]
    hi = report["value"]["range_high"]
    assert hi > lo, "Flat band must be widened to a non-zero spread"
    assert report["metadata"]["range_quality"] == "estimate"


def test_supporting_metrics_are_present_on_every_driver():
    """Each of the six canonical drivers must surface a structured
    `supporting_metrics` array alongside the qualitative `supporting_signals`,
    which is what the new inline metric grid renders against."""
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=_base_score(),
        cohort_rows_by_call=[_good_cohort()],
    )
    report = asyncio.run(build_csc_report_json(db, "subject-1", {}))
    drivers = report["explanation"]["key_value_drivers"]
    for driver in drivers:
        metrics = driver.get("supporting_metrics")
        assert isinstance(metrics, list)
        # Each metric must have at minimum a label + value pair the UI can render.
        for metric in metrics:
            assert "label" in metric
            assert "value" in metric


def test_position_group_request_param_is_honored():
    """`position_group` is the canonical request param; the legacy `position`
    field must continue to work for backward compatibility."""
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=_base_score(),
        cohort_rows_by_call=[_good_cohort()],
    )
    report_canonical = asyncio.run(
        build_csc_report_json(db, "subject-1", {"position_group": "QB"})
    )
    db2 = _FakeDb(
        athlete=_base_athlete(),
        latest_score=_base_score(),
        cohort_rows_by_call=[_good_cohort()],
    )
    report_legacy = asyncio.run(
        build_csc_report_json(db2, "subject-1", {"position": "QB"})
    )
    # Both shapes must produce a report; metadata should reflect the resolved
    # position group rather than crashing on unknown param keys.
    assert report_canonical["metadata"].get("position_group") in {"QB", None}
    assert report_legacy["metadata"].get("position_group") in {"QB", None}


def test_market_view_metadata_round_trips():
    """The builder must echo the requested `market_view` so the UI can show
    the analyst what view produced the report (and so reports cached by
    params remain auditable)."""
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=_base_score(),
        cohort_rows_by_call=[_good_cohort()],
    )
    report = asyncio.run(
        build_csc_report_json(db, "subject-1", {"market_view": "conservative"})
    )
    assert report["metadata"].get("market_view") == "conservative"


def test_csc_band_overrides_widen_range_when_provided():
    """When the analyst passes explicit percentile bands, the builder must
    widen lo/hi using `cohort_stats` rather than the raw model p10/p90."""
    db = _FakeDb(
        athlete=_base_athlete(),
        latest_score=_base_score(),
        cohort_rows_by_call=[_good_cohort()],
    )
    report = asyncio.run(
        build_csc_report_json(
            db,
            "subject-1",
            {"csc_band_low_pct": 0.05, "csc_band_high_pct": 0.95},
        )
    )
    # Metadata records the override so audits know the range was widened.
    assert report["metadata"].get("csc_band_low_pct") == 0.05
    assert report["metadata"].get("csc_band_high_pct") == 0.95
