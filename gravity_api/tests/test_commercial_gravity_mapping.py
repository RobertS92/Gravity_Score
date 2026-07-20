"""Commercial Gravity mapping and calibration passthrough."""

from __future__ import annotations

import asyncio
import math
from unittest.mock import AsyncMock

from gravity_api.services.gravity_calibration import apply_calibration_to_score
from gravity_api.services.market_value_anchor import enrich_raw_with_market_value_anchor
from gravity_ml.inference.predict import (
    _commercial_market_score,
    commercial_gravity_from_log_usd,
)


def test_commercial_gravity_spreads_apy_range():
    clifford = commercial_gravity_from_log_usd(math.log1p(1_075_000))
    huntley = commercial_gravity_from_log_usd(math.log1p(2_500_000))
    sutton = commercial_gravity_from_log_usd(math.log1p(23_000_000))
    mahomes = commercial_gravity_from_log_usd(math.log1p(64_000_000))
    assert clifford < huntley < sutton < mahomes
    assert 90 <= mahomes <= 95
    assert clifford < 60
    assert sutton < 80


def test_observed_contract_anchor_dominates_noisy_model():
    score, effective_usd, metadata = _commercial_market_score(
        math.log1p(9_600_000),
        {
            "observed_market_value_usd": 64_000_000,
            "observed_market_value_confidence": 0.9,
            "observed_market_value_type": "contract_apy",
            "observed_market_value_source": "verified",
        },
        "nfl",
    )
    assert 90 <= score <= 95
    assert effective_usd > 45_000_000
    assert metadata["market_anchor_used"] is True


def test_nba_salary_curve_keeps_non_supermax_below_90():
    bam = commercial_gravity_from_log_usd(math.log1p(37_096_620), "nba")
    ingram = commercial_gravity_from_log_usd(math.log1p(38_095_238), "nba")
    lebron = commercial_gravity_from_log_usd(math.log1p(52_627_153), "nba")
    jokic = commercial_gravity_from_log_usd(math.log1p(55_224_526), "nba")
    assert bam < 90
    assert ingram < 90
    assert lebron > ingram
    assert jokic > ingram


def test_market_anchor_enrichment_is_request_scoped():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        return_value={
            "value_usd": 64_000_000,
            "label_type": "contract_apy",
            "confidence": 0.9,
            "source": "verified",
        }
    )
    original = {"games_played_season": 17}
    enriched = asyncio.run(
        enrich_raw_with_market_value_anchor(conn, "00000000-0000-0000-0000-000000000001", "nfl", original)
    )
    assert "observed_market_value_usd" not in original
    assert enriched["observed_market_value_usd"] == 64_000_000


def test_calibration_preserves_commercial_ml_rank():
    cohort = [55.0] * 100  # would push any latent to ~p50 under BPXVR knots
    mahomes = apply_calibration_to_score(
        {
            "gravity_score": 98.5,
            "dollar_p50_usd": 9_600_000,
            "fallback_used": False,
            "gravity_source": "commercial_ml",
            "dollar_confidence": {"gravity_source": "commercial_ml", "quality": "moderate"},
            "brand_score": 80,
            "proof_score": 75,
            "proximity_score": 70,
            "velocity_score": 60,
            "risk_score": 40,
        },
        sport="nfl",
        cohort_latents=cohort,
    )
    clifford = apply_calibration_to_score(
        {
            "gravity_score": 52.0,
            "dollar_p50_usd": 1_600_000,
            "fallback_used": False,
            "gravity_source": "commercial_ml",
            "dollar_confidence": {"gravity_source": "commercial_ml", "quality": "moderate"},
            "brand_score": 50,
            "proof_score": 40,
            "proximity_score": 40,
            "velocity_score": 40,
            "risk_score": 50,
        },
        sport="nfl",
        cohort_latents=cohort,
    )
    assert mahomes["gravity_score"] > clifford["gravity_score"]
    assert mahomes["gravity_source"] == "commercial_ml"
    assert mahomes["dollar_confidence"]["calibration_version"] == "commercial_ml_passthrough"
