"""Demo login catalog, enablement, and auth listing (DB mocked)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import bcrypt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gravity_api.routers import auth
from gravity_api.services import demo_accounts as da


def test_catalog_emails_are_unique_and_cover_roles():
    emails = [a.email for a in da.DEMO_ACCOUNTS]
    assert len(emails) == len(set(emails))
    roles = {a.role for a in da.DEMO_ACCOUNTS}
    assert roles >= {"school_admin", "school_coach", "agent", "brand", "admin"}
    assert all("@" in a.email for a in da.DEMO_ACCOUNTS)


def test_hash_password_roundtrip():
    hashed = da.hash_password("demo1234")
    assert hashed.startswith("$2")
    assert bcrypt.checkpw(b"demo1234", hashed.encode("utf-8"))


def test_is_enabled_defaults_off_in_production():
    assert da.is_enabled(environment="production", flag=None) is False
    assert da.is_enabled(environment="production", flag="") is False
    assert da.is_enabled(environment="development", flag=None) is True
    assert da.is_enabled(environment="staging", flag=None) is True


def test_is_enabled_flag_overrides_environment():
    assert da.is_enabled(environment="production", flag="1") is True
    assert da.is_enabled(environment="development", flag="0") is False
    assert da.is_enabled(environment="production", flag="false") is False


def test_public_catalog_includes_shared_password():
    payload = da.public_catalog(password="demo1234")
    assert payload["password"] == "demo1234"
    assert payload["accounts"][0]["email"] == "demo@gravity.local"
    assert {row["email"] for row in payload["accounts"]} == {a.email for a in da.DEMO_ACCOUNTS}


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth.router, prefix="/v1/auth")
    return app


def test_demo_accounts_endpoint_404_when_disabled():
    client = TestClient(_app())
    with patch.object(auth, "is_demo_accounts_enabled", return_value=False):
        r = client.get("/v1/auth/demo-accounts")
    assert r.status_code == 404


def test_demo_accounts_endpoint_returns_catalog_when_enabled():
    client = TestClient(_app())
    with (
        patch.object(auth, "is_demo_accounts_enabled", return_value=True),
        patch.object(auth, "demo_catalog", return_value=da.public_catalog(password="demo1234")),
    ):
        r = client.get("/v1/auth/demo-accounts")
    assert r.status_code == 200
    body = r.json()
    assert body["password"] == "demo1234"
    assert any(a["email"] == "admin@gravity.local" for a in body["accounts"])


def test_seed_upserts_org_and_each_account():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()
    n = asyncio.run(da.seed_demo_accounts(conn, password="demo1234"))
    assert n == len(da.DEMO_ACCOUNTS)
    # org insert + 5 user inserts + 2 memberships (school admin + coach)
    assert conn.execute.await_count >= 1 + len(da.DEMO_ACCOUNTS)
