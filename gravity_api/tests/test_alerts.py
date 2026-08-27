"""Alert Center feed: persisted events, live watchlist signals, mark-read."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gravity_api.auth_deps import require_user_id
from gravity_api.database import get_db
from gravity_api.routers import alerts

FIXED_UID = uuid.UUID("00000000-0000-4000-8000-000000000001")
ATHLETE_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
ALERT_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


def _mini_app(mock_conn: AsyncMock) -> FastAPI:
    app = FastAPI()

    async def override_db():
        yield mock_conn

    async def override_uid():
        return FIXED_UID

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_user_id] = override_uid
    app.include_router(alerts.router, prefix="/v1/alerts")
    return app


def test_alert_type_from_reason_prefix():
    assert alerts._alert_type_from_reason("SCORE_MOVE: Gravity score moved +4.2") == "SCORE_MOVE"
    assert alerts._alert_type_from_reason("NIL_SIGNAL: Model NIL P50 updated") == "NIL_SIGNAL"
    assert alerts._alert_type_from_reason("plain text") == "SCORE_MOVE"


def test_get_alerts_includes_school_and_parses_type():
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "id": ALERT_ID,
                    "user_id": FIXED_UID,
                    "athlete_id": ATHLETE_ID,
                    "previous_score": 80.0,
                    "new_score": 84.2,
                    "delta": 4.2,
                    "trigger_reason": "SCORE_MOVE: Gravity score moved +4.2",
                    "read": False,
                    "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
                    "athlete_name": "Caleb Downs",
                    "school": "Ohio State",
                    "sport": "cfb",
                }
            ],
            [],  # derived watchlist query
        ]
    )
    client = TestClient(_mini_app(conn))
    r = client.get("/v1/alerts?sports=CFB")
    assert r.status_code == 200
    body = r.json()
    assert body["unread"] == 1
    item = body["items"][0]
    assert item["athlete_name"] == "Caleb Downs"
    assert item["school"] == "Ohio State"
    assert item["alert_type"] == "SCORE_MOVE"
    assert item["source"] == "event"
    assert item["delta"] == 4.2


def test_get_alerts_adds_live_signals_without_duplicating_events():
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [],  # no persisted events
            [
                {
                    "athlete_id": ATHLETE_ID,
                    "athlete_name": "Caleb Downs",
                    "school": "Ohio State",
                    "sport": "cfb",
                    "gravity_score": 88.0,
                    "past_gravity": 80.0,
                    "dollar_p50_usd": 400_000.0,
                    "risk_score": 20.0,
                    "calculated_at": datetime.now(timezone.utc),
                }
            ],
        ]
    )
    client = TestClient(_mini_app(conn))
    r = client.get("/v1/alerts")
    assert r.status_code == 200
    types = {it["alert_type"] for it in r.json()["items"]}
    assert "SCORE_MOVE" in types
    assert "NIL_SIGNAL" in types
    assert "RISK_FLAG" not in types
    assert all(it["source"] == "live" for it in r.json()["items"])


def test_mark_read_updates_uuid_rows_and_ignores_live_ids():
    conn = AsyncMock()
    conn.execute = AsyncMock()
    client = TestClient(_mini_app(conn))
    r = client.post(
        "/v1/alerts/mark-read",
        json={"alert_ids": [str(ALERT_ID), f"live:SCORE_MOVE:{ATHLETE_ID}"]},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    conn.execute.assert_awaited_once()
    args = conn.execute.await_args.args
    assert args[1] == FIXED_UID
    assert ALERT_ID in args[2]


def test_mark_all_read():
    conn = AsyncMock()
    conn.execute = AsyncMock()
    client = TestClient(_mini_app(conn))
    r = client.post("/v1/alerts/mark-read", json={"mark_all": True})
    assert r.status_code == 200
    conn.execute.assert_awaited_once()
