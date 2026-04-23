"""HTTP behavior for onboarding + preferences with DB dependencies mocked."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gravity_api.auth_deps import require_user_id
from gravity_api.database import get_db
from gravity_api.routers import auth, user_preferences

FIXED_UID = uuid.UUID("00000000-0000-4000-8000-000000000099")


def _mini_app(mock_conn: AsyncMock) -> FastAPI:
    app = FastAPI()

    async def override_db():
        yield mock_conn

    async def override_uid():
        return FIXED_UID

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_user_id] = override_uid
    app.include_router(auth.router, prefix="/v1/auth")
    app.include_router(user_preferences.router, prefix="/v1/user")
    return app


def test_onboarding_409_when_already_completed():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=datetime.now(timezone.utc))
    client = TestClient(_mini_app(conn))
    r = client.post(
        "/v1/auth/onboarding",
        json={"org_type": "school", "sport_preferences": ["CFB"]},
    )
    assert r.status_code == 409
    conn.execute.assert_not_called()


def test_onboarding_400_invalid_org_type():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    client = TestClient(_mini_app(conn))
    r = client.post(
        "/v1/auth/onboarding",
        json={"org_type": "not_real", "sport_preferences": ["CFB"]},
    )
    assert r.status_code == 400
    conn.execute.assert_not_called()


def test_onboarding_success_updates_row():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    now = datetime.now(timezone.utc)
    conn.fetchrow = AsyncMock(
        return_value={
            "id": FIXED_UID,
            "email": "t@example.com",
            "role": "agent",
            "org_type": "school",
            "sport_preferences": ["CFB", "NCAAB"],
            "org_name": None,
            "team_or_athlete_seed": None,
            "default_dashboard_tab": "roster",
            "athletes_default_sort": None,
            "onboarding_completed_at": now,
            "display_name": "T",
            "onboarding_goal": None,
        }
    )
    client = TestClient(_mini_app(conn))
    r = client.post(
        "/v1/auth/onboarding",
        json={"org_type": "school", "sport_preferences": ["CFB", "NCAAB"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["default_dashboard_tab"] == "roster"
    assert body["sport_preferences"] == ["CFB", "NCAAB"]
    conn.execute.assert_called_once()


def test_patch_preferences_invalid_dashboard_tab():
    conn = AsyncMock()
    client = TestClient(_mini_app(conn))
    r = client.patch("/v1/user/preferences", json={"default_dashboard_tab": "widgets"})
    assert r.status_code == 400
    conn.execute.assert_not_called()


def test_patch_preferences_invalid_sport_list():
    conn = AsyncMock()
    client = TestClient(_mini_app(conn))
    r = client.patch("/v1/user/preferences", json={"sport_preferences": ["NFL"]})
    assert r.status_code == 400
    conn.execute.assert_not_called()


def test_patch_preferences_empty_sports_rejected():
    conn = AsyncMock()
    client = TestClient(_mini_app(conn))
    r = client.patch("/v1/user/preferences", json={"sport_preferences": []})
    assert r.status_code == 400
    conn.execute.assert_not_called()


def test_patch_preferences_ok():
    conn = AsyncMock()
    conn.execute = AsyncMock()
    now = datetime.now(timezone.utc)
    conn.fetchrow = AsyncMock(
        return_value={
            "org_type": "school",
            "sport_preferences": ["NCAAB"],
            "org_name": "Demo U",
            "team_or_athlete_seed": None,
            "default_dashboard_tab": "market",
            "athletes_default_sort": None,
            "onboarding_completed_at": now,
            "display_name": "Coach",
            "onboarding_goal": "Win",
        }
    )
    client = TestClient(_mini_app(conn))
    r = client.patch(
        "/v1/user/preferences",
        json={"sport_preferences": ["NCAAB"], "default_dashboard_tab": "market"},
    )
    assert r.status_code == 200
    conn.execute.assert_called_once()
    assert r.json()["sport_preferences"] == ["NCAAB"]
