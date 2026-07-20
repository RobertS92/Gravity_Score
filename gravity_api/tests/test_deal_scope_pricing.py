from datetime import datetime, timedelta, timezone
from pathlib import Path

from gravity_api.services.athlete_eligibility import live_eligibility_reason
from gravity_api.services.deal_scope_pricing import DEAL_SCOPES, price_all_deal_scopes, price_deal_scope


SIGNALS = {
    "brand_score": 75,
    "proof_score": 70,
    "exposure_score": 80,
    "velocity_score": 65,
    "risk_score": 20,
}


def test_every_commercial_scope_has_an_independent_versioned_model():
    estimates = price_all_deal_scopes(annual_benchmark=1_000_000, signals=SIGNALS)
    assert set(estimates) == set(DEAL_SCOPES)
    assert len({row["model_version"] for row in estimates.values()}) == len(DEAL_SCOPES)
    assert len({row["mid"] for row in estimates.values()}) == len(DEAL_SCOPES)


def test_prior_only_output_never_claims_confidence():
    estimate = price_deal_scope(
        "standard_activation",
        annual_benchmark=1_000_000,
        signals=SIGNALS,
        qualified_transactions=99,
        calibration={
            "validation_transactions": 30,
            "target_coverage": .8,
            "empirical_coverage": .8,
            "median_absolute_percentage_error": .15,
            "log_residual_lower": -.4,
            "log_residual_upper": .4,
        },
    )
    assert estimate.calibrated is False
    assert estimate.confidence == "Uncalibrated"
    assert estimate.readiness == "insufficient_data"


def test_calibrated_interval_and_confidence_use_measured_error():
    estimate = price_deal_scope(
        "season_partnership",
        annual_benchmark=1_000_000,
        signals=SIGNALS,
        qualified_transactions=130,
        calibration={
            "validation_transactions": 25,
            "target_coverage": .8,
            "empirical_coverage": .80,
            "median_absolute_percentage_error": .20,
            "log_residual_lower": -.5,
            "log_residual_upper": .6,
            "evaluated_through": "2026-06-30",
        },
    )
    assert estimate.calibrated is True
    assert estimate.confidence == "High"
    assert estimate.low < estimate.mid < estimate.high
    assert estimate.readiness == "pilot"


def test_live_eligibility_rejects_departed_and_stale_athletes():
    now = datetime(2026, 7, 20, tzinfo=timezone.utc)
    active = {
        "is_active": True,
        "roster_status": "active_on_roster",
        "roster_verified_at": now - timedelta(days=2),
    }
    assert live_eligibility_reason(active, now=now) is None
    assert live_eligibility_reason({**active, "is_active": False}, now=now)
    assert live_eligibility_reason({**active, "roster_status": "left_for_draft"}, now=now)
    assert live_eligibility_reason(
        {**active, "roster_verified_at": now - timedelta(days=22)}, now=now
    )


def test_governed_transaction_schema_requires_structured_verification():
    migration = (
        Path(__file__).parents[2] / "migrations" / "036_scoped_deal_pricing_governance.sql"
    ).read_text()
    assert "source_url TEXT NOT NULL" in migration
    assert "primary_document_verified" in migration
    assert "two_source_verified" in migration
    assert "source_evidence JSONB NOT NULL" in migration
    assert "score_snapshot_id UUID REFERENCES athlete_score_snapshots" in migration
