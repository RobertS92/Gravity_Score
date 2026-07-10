"""Partner API unit tests (no database)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gravity_api.database import get_db
from gravity_api.partner_types import PartnerContext
from gravity_api.partner_auth import require_partner
from gravity_api.routers import partner as partner_router
from gravity_api.services.partner_api import (
    format_partner_athlete_detail,
    format_partner_athlete_summary,
    format_partner_score_row,
    hash_api_key,
)


PARTNER_KEY = "gsk_live_test_partner_key_000000000000"
FIXED_ATHLETE_ID = "00000000-0000-4000-8000-000000000001"


def test_hash_api_key_is_stable():
    assert hash_api_key("abc") == hash_api_key("abc")
    assert hash_api_key("abc") != hash_api_key("abcd")


def test_format_partner_score_inverts_risk():
    out = format_partner_score_row(
        {
            "athlete_id": FIXED_ATHLETE_ID,
            "gravity_score": 80,
            "gravity_sport_percentile": 96,
            "value_score": 91,
            "value_sport_percentile": 98,
            "value_score_source": "ml_value_v1",
            "brand_score": 70,
            "proof_score": 65,
            "proximity_score": 72,
            "velocity_score": 88,
            "risk_score": 25,
            "confidence": 0.8,
            "model_version": "v2",
            "calculated_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
            "dollar_p50_usd": 500000,
            "dollar_confidence": {
                "score_tier": 1,
                "fallback_kind": None,
                "gravity_source": "commercial_ml",
            },
        }
    )
    assert out["gravity_score"] == 80.0
    assert out["gravity_sport_percentile"] == 96.0
    # Primary public field is impact_score; value_score kept as deprecated alias.
    assert out["impact_score"] == 91.0
    assert out["impact_sport_percentile"] == 98.0
    assert out["impact_score_source"] == "ml_value_v1"
    assert out["value_score"] == 91.0
    assert out["value_sport_percentile"] == 98.0
    assert out["value_score_source"] == "ml_value_v1"
    assert out["components"]["risk"] == 75.0
    assert out["nil_estimate_usd"]["p50"] == 500000.0
    assert out["score_tier"] == 1
    assert out["fallback_kind"] is None
    assert out["fallback_used"] is False
    assert out["gravity_source"] == "commercial_ml"
    assert "Powered by Gravity Score" in out["attribution"]["text"]


def test_format_partner_score_reads_impact_from_dollar_confidence():
    out = format_partner_score_row(
        {
            "athlete_id": FIXED_ATHLETE_ID,
            "gravity_score": 80,
            "brand_score": 70,
            "proof_score": 65,
            "proximity_score": 72,
            "velocity_score": 88,
            "risk_score": 25,
            "dollar_confidence": {"win_impact_score": 91.5},
        }
    )
    assert out["impact_score"] == 91.5
    assert out["value_score"] == 91.5
    assert out["impact_score_source"] == "win_impact_v0"


def test_format_partner_score_exposes_mid_fallback_quality():
    out = format_partner_score_row(
        {
            "athlete_id": FIXED_ATHLETE_ID,
            "gravity_score": 62,
            "value_score": 55,
            "model_version": "heuristic_gravity_v1",
            "dollar_confidence": {
                "score_tier": 2,
                "fallback_kind": "heuristic_gravity_v1",
                "quality": "moderate",
            },
        }
    )
    assert out["score_tier"] == 2
    assert out["fallback_kind"] == "heuristic_gravity_v1"
    assert out["fallback_used"] is True
    assert out["quality"] == "moderate"


def test_format_partner_athlete_summary_exposes_impact_score():
    out = format_partner_athlete_summary(
        {
            "id": FIXED_ATHLETE_ID,
            "name": "Test Athlete",
            "school": "Texas",
            "sport": "cfb",
            "gravity_score": 77,
            "value_score": 88.5,
            "value_sport_percentile": 94,
            "value_score_source": "win_impact_v1_additive",
            "risk_score": 80,
        }
    )
    assert out["athlete_id"] == FIXED_ATHLETE_ID
    assert out["name"] == "Test Athlete"
    assert out["impact_score"] == 88.5
    assert out["impact_sport_percentile"] == 94.0
    assert out["impact_score_source"] == "win_impact_v1_additive"
    assert out["value_score"] == 88.5


def test_format_score_history_point_exposes_impact_score():
    from gravity_api.services.partner_api import format_score_history_point

    out = format_score_history_point(
        {
            "gravity_score": 70,
            "value_score": 82,
            "value_sport_percentile": 90,
            "value_score_source": "ml_value_v1",
            "brand_score": 60,
            "proof_score": 60,
            "proximity_score": 60,
            "velocity_score": 60,
            "risk_score": 30,
            "confidence": 0.7,
            "calculated_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        }
    )
    assert out["impact_score"] == 82.0
    assert out["impact_sport_percentile"] == 90.0
    assert out["impact_score_source"] == "ml_value_v1"
    assert out["value_score"] == 82.0
    assert out["components"]["risk"] == 70.0


def test_format_partner_athlete_summary_shape():
    out = format_partner_athlete_summary(
        {
            "id": FIXED_ATHLETE_ID,
            "name": "Test Athlete",
            "school": "Texas",
            "sport": "cfb",
            "gravity_score": 77,
            "risk_score": 80,
        }
    )
    assert out["athlete_id"] == FIXED_ATHLETE_ID
    assert out["name"] == "Test Athlete"
    assert out["impact_score"] is None
    assert out["value_score"] is None


def test_format_partner_athlete_detail_includes_score():
    athlete = {"id": FIXED_ATHLETE_ID, "name": "A", "school": "S"}
    score = {
        "athlete_id": FIXED_ATHLETE_ID,
        "gravity_score": 60,
        "risk_score": 40,
        "brand_score": 50,
        "proof_score": 50,
        "proximity_score": 50,
        "velocity_score": 50,
        "confidence": 0.5,
        "model_version": "v1",
        "calculated_at": datetime.now(timezone.utc),
    }
    out = format_partner_athlete_detail(athlete, score)
    assert out["score"]["gravity_score"] == 60.0


def _mini_app(mock_conn: AsyncMock, partner_key: str = PARTNER_KEY) -> FastAPI:
    app = FastAPI()

    async def override_db():
        yield mock_conn

    async def override_partner():
        return PartnerContext(
            partner_id=uuid.UUID("00000000-0000-4000-8000-000000000099"),
            partner_name="test-partner",
            scopes=frozenset({"scores:read", "search:read"}),
            rate_limit_per_minute=1000,
            allowed_origins=None,
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_partner] = override_partner
    app.include_router(partner_router.router, prefix="/v2/partner")
    app.state.test_partner_key = partner_key
    return app


def test_partner_health_no_auth():
    conn = AsyncMock()
    client = TestClient(_mini_app(conn))
    r = client.get("/v2/partner/health")
    assert r.status_code == 200
    assert r.json()["service"] == "gravity-partner-api"


def test_partner_latest_score_404_when_missing():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetchrow = AsyncMock(return_value=None)
    client = TestClient(_mini_app(conn))
    r = client.get(
        f"/v2/partner/scores/{FIXED_ATHLETE_ID}",
        headers={"Authorization": f"Bearer {PARTNER_KEY}"},
    )
    assert r.status_code == 404


def test_partner_latest_score_success():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetchrow = AsyncMock(
        return_value={
            "athlete_id": FIXED_ATHLETE_ID,
            "gravity_score": 85,
            "gravity_sport_percentile": 92,
            "value_score": 88,
            "value_sport_percentile": 95,
            "value_score_source": "ml_value_v1",
            "brand_score": 80,
            "proof_score": 70,
            "proximity_score": 75,
            "velocity_score": 90,
            "risk_score": 20,
            "confidence": 0.9,
            "model_version": "athlete_v2",
            "calculated_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
            "dollar_p10_usd": 100000,
            "dollar_p50_usd": 250000,
            "dollar_p90_usd": 500000,
        }
    )
    client = TestClient(_mini_app(conn))
    r = client.get(
        f"/v2/partner/scores/{FIXED_ATHLETE_ID}",
        headers={"Authorization": f"Bearer {PARTNER_KEY}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["gravity_score"] == 85.0
    assert body["impact_score"] == 88.0
    assert body["impact_sport_percentile"] == 95.0
    assert body["impact_score_source"] == "ml_value_v1"
    assert body["value_score"] == 88.0  # deprecated alias
    assert body["components"]["risk"] == 80.0
