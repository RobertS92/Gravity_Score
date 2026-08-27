"""Partner scoped deal-pricing tests (no live database)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import asyncpg
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gravity_api.database import get_db
from gravity_api.partner_auth import require_partner
from gravity_api.partner_types import PartnerContext
from gravity_api.routers import partner as partner_router
from gravity_api.services.deal_scope_pricing import DEAL_SCOPES
from gravity_api.services.partner_deal_pricing import build_partner_deal_pricing


FIXED_ATHLETE_ID = "00000000-0000-4000-8000-000000000001"
PARTNER_KEY = "gsk_live_test_partner_key_000000000000"


SCORE_ROW = {
    "athlete_id": FIXED_ATHLETE_ID,
    "gravity_score": 85,
    "brand_score": 80,
    "proof_score": 70,
    "proximity_score": 75,
    "velocity_score": 90,
    "risk_score": 20,
    "dollar_p50_usd": 1_000_000,
    "calculated_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
}


def _mini_app(mock_conn: AsyncMock, scopes: frozenset[str]) -> FastAPI:
    app = FastAPI()

    async def override_db():
        yield mock_conn

    async def override_partner():
        return PartnerContext(
            partner_id=uuid.UUID("00000000-0000-4000-8000-000000000099"),
            partner_name="test-partner",
            scopes=scopes,
            rate_limit_per_minute=1000,
            allowed_origins=None,
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_partner] = override_partner
    app.include_router(partner_router.router, prefix="/v2/partner")
    return app


def test_build_partner_deal_pricing_includes_all_scopes_uncalibrated():
    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=asyncpg.UndefinedTableError())

    payload = asyncio.run(
        build_partner_deal_pricing(
            conn, athlete_id=FIXED_ATHLETE_ID, score_row=SCORE_ROW
        )
    )

    assert payload["athlete_id"] == FIXED_ATHLETE_ID
    assert payload["annual_nil_benchmark"] == 1_000_000.0
    assert payload["annual_nil_benchmark_unit"] == "annual_usd"
    assert set(payload["deal_scopes"]) == set(DEAL_SCOPES)
    for scope in DEAL_SCOPES:
        est = payload["deal_scopes"][scope]
        assert est["scope"] == scope
        assert est["unit"] == "per_scope_usd"
        assert est["readiness"] == "insufficient_data"
        assert est["confidence"] == "Uncalibrated"
        assert est["calibrated"] is False
        assert est["qualified_transactions"] == 0
        assert est["low"] is not None and est["mid"] is not None and est["high"] is not None
    assert "selected_deal_scope" not in payload
    assert "Powered by Gravity Score" in payload["attribution"]["text"]


def test_build_partner_deal_pricing_null_benchmark_yields_null_ranges():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    row = {**SCORE_ROW, "dollar_p50_usd": None}
    payload = asyncio.run(
        build_partner_deal_pricing(
            conn, athlete_id=FIXED_ATHLETE_ID, score_row=row
        )
    )
    assert payload["annual_nil_benchmark"] is None
    for est in payload["deal_scopes"].values():
        assert est["low"] is None
        assert est["mid"] is None
        assert est["high"] is None
        assert est["confidence"] == "Uncalibrated"


def test_partner_deal_pricing_requires_pricing_scope():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetchrow = AsyncMock(return_value=SCORE_ROW)
    client = TestClient(
        _mini_app(conn, frozenset({"scores:read", "search:read"}))
    )
    r = client.get(
        f"/v2/partner/athletes/{FIXED_ATHLETE_ID}/deal-pricing",
        headers={"Authorization": f"Bearer {PARTNER_KEY}"},
    )
    assert r.status_code == 403
    assert "pricing:read" in r.json()["detail"]


def test_partner_deal_pricing_success():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetchrow = AsyncMock(return_value=SCORE_ROW)
    conn.fetch = AsyncMock(return_value=[])
    client = TestClient(
        _mini_app(conn, frozenset({"scores:read", "search:read", "pricing:read"}))
    )
    r = client.get(
        f"/v2/partner/athletes/{FIXED_ATHLETE_ID}/deal-pricing",
        headers={"Authorization": f"Bearer {PARTNER_KEY}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body["deal_scopes"]) == set(DEAL_SCOPES)
    assert body["deal_scopes"]["standard_activation"]["confidence"] == "Uncalibrated"
    assert body["annual_nil_benchmark_unit"] == "annual_usd"


def test_partner_deal_pricing_404_missing_athlete():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    client = TestClient(
        _mini_app(conn, frozenset({"pricing:read"}))
    )
    r = client.get(
        f"/v2/partner/athletes/{FIXED_ATHLETE_ID}/deal-pricing",
        headers={"Authorization": f"Bearer {PARTNER_KEY}"},
    )
    assert r.status_code == 404


def test_partner_deal_pricing_rejects_unknown_scope_query():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    client = TestClient(
        _mini_app(conn, frozenset({"pricing:read"}))
    )
    r = client.get(
        f"/v2/partner/athletes/{FIXED_ATHLETE_ID}/deal-pricing?scope=fantasy_bundle",
        headers={"Authorization": f"Bearer {PARTNER_KEY}"},
    )
    assert r.status_code == 422


def test_partner_athletes_passes_conference_filter():
    conn = AsyncMock()
    with patch(
        "gravity_api.routers.partner.run_athlete_search",
        new_callable=AsyncMock,
    ) as search:
        search.return_value = {
            "athletes": [],
            "total": 0,
            "returned": 0,
        }
        client = TestClient(
            _mini_app(conn, frozenset({"search:read"}))
        )
        r = client.get(
            "/v2/partner/athletes?conference=SEC&sport=cfb&limit=5",
            headers={"Authorization": f"Bearer {PARTNER_KEY}"},
        )
        assert r.status_code == 200
        assert search.await_count == 1
        kwargs = search.await_args.kwargs
        assert kwargs["conference"] == "SEC"
