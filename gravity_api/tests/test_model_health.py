"""Unit tests for the model health probe + classifier."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from gravity_api.services import model_health as model_health_mod
from gravity_api.services.model_health import (
    ModelHealth,
    classify_model_version,
    get_model_health,
    probe_model_health,
    set_model_health,
)


@pytest.mark.parametrize(
    "version,expected",
    [
        ("gravity_v1_2026-04-14", "production"),
        ("gravity_v2", "production"),
        ("v3.2", "production"),
        ("heuristic_fallback_v1", "fallback"),
        ("composite_fallback_v0", "fallback"),
        ("composite_fallback_anything", "fallback"),
        ("ml_sync", "fallback"),
        ("some-build-fallback", "fallback"),
        (None, "unknown"),
        ("", "unknown"),
        ("   ", "unknown"),
    ],
)
def test_classify_model_version(version, expected):
    assert classify_model_version(version) == expected


class _FakeTransport(httpx.AsyncBaseTransport):
    """Stub httpx transport returning a canned JSON payload per path."""

    def __init__(self, responses: dict[str, dict[str, Any] | int]) -> None:
        self._responses = responses

    async def handle_async_request(
        self, request: httpx.Request
    ) -> httpx.Response:
        path = request.url.path
        payload = self._responses.get(path)
        if isinstance(payload, int):
            return httpx.Response(status_code=payload)
        return httpx.Response(status_code=200, json=payload or {})


def _run(coro):
    return asyncio.run(coro)


def test_probe_returns_unknown_when_no_ml_url(monkeypatch):
    monkeypatch.delenv("ML_SERVICE_URL", raising=False)
    monkeypatch.delenv("ML_API_URL", raising=False)
    from gravity_api.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    health = _run(probe_model_health())
    assert health.status == "unknown"
    assert health.reason == "ml_service_url_not_configured"
    # Cached state matches the returned object.
    assert get_model_health() is health


def test_probe_marks_production_when_health_reports_real_version(monkeypatch):
    monkeypatch.setenv("ML_SERVICE_URL", "http://ml.test")
    from gravity_api.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    transport = _FakeTransport({"/health": {"model_version": "gravity_v1_2026-04-14"}})
    client = httpx.AsyncClient(transport=transport, base_url="http://ml.test")
    try:
        health = _run(probe_model_health(client=client))
    finally:
        _run(client.aclose())
    assert health.status == "production"
    assert health.model_version == "gravity_v1_2026-04-14"
    assert health.is_fallback is False


def test_probe_marks_fallback_when_health_reports_heuristic(monkeypatch):
    monkeypatch.setenv("ML_SERVICE_URL", "http://ml.test")
    from gravity_api.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    transport = _FakeTransport({"/health": {"model_version": "heuristic_fallback_v1"}})
    client = httpx.AsyncClient(transport=transport, base_url="http://ml.test")
    try:
        health = _run(probe_model_health(client=client))
    finally:
        _run(client.aclose())
    assert health.status == "fallback"
    assert health.is_fallback is True


def test_probe_falls_through_to_model_info_when_health_missing_version(monkeypatch):
    monkeypatch.setenv("ML_SERVICE_URL", "http://ml.test")
    from gravity_api.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    transport = _FakeTransport(
        {
            "/health": {},
            "/model/info": {"model_version": "gravity_v1"},
        }
    )
    client = httpx.AsyncClient(transport=transport, base_url="http://ml.test")
    try:
        health = _run(probe_model_health(client=client))
    finally:
        _run(client.aclose())
    assert health.status == "production"
    assert health.model_version == "gravity_v1"


def test_set_model_health_replaces_cache(monkeypatch):
    set_model_health(ModelHealth(status="fallback", reason="manual"))
    assert get_model_health().status == "fallback"
    set_model_health(ModelHealth(status="production", reason="manual"))
    assert get_model_health().status == "production"


def test_probe_detects_fallback_when_ml_reports_no_bundle(monkeypatch):
    """gravity-ml /health/ready: ``{"model_bundle": false, ...}`` must be
    surfaced as fallback even when no version string is exposed."""
    monkeypatch.setenv("ML_SERVICE_URL", "http://ml.test")
    from gravity_api.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    transport = _FakeTransport(
        {
            "/health/ready": {
                "status": "ready",
                "model_bundle": False,
                "path": "models",
                "event_processor": True,
                "note": "Serving composite fallback until bundle present",
            },
            "/health": {"status": "healthy", "service": "gravity-ml"},
            "/model/info": 404,
            "/models/status": 404,
        }
    )
    client = httpx.AsyncClient(transport=transport, base_url="http://ml.test")
    try:
        health = _run(probe_model_health(client=client))
    finally:
        _run(client.aclose())
    assert health.status == "fallback"
    assert health.model_version == "composite_fallback"
    assert health.reason == "ml_service_reports_no_bundle"
    assert health.is_fallback is True


def test_probe_detects_wrong_service_pointed_at_scrapers(monkeypatch):
    """If ML_SERVICE_URL is mis-pointed at gravity-scrapers, surface that
    explicitly so ops can read the right diagnostic on /v1/health."""
    monkeypatch.setenv("ML_SERVICE_URL", "http://ml.test")
    from gravity_api.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    transport = _FakeTransport(
        {
            "/health/ready": 404,
            "/health": {"status": "healthy", "service": "gravity-scrapers"},
            "/model/info": 404,
            "/models/status": 404,
        }
    )
    client = httpx.AsyncClient(transport=transport, base_url="http://ml.test")
    try:
        health = _run(probe_model_health(client=client))
    finally:
        _run(client.aclose())
    assert health.status == "unknown"
    assert health.reason == "wrong_service:gravity-scrapers"


def test_probe_accepts_bundle_version_field(monkeypatch):
    """Some ML deploys expose ``bundle_version`` instead of ``model_version``."""
    monkeypatch.setenv("ML_SERVICE_URL", "http://ml.test")
    from gravity_api.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    transport = _FakeTransport(
        {
            "/health/ready": {"model_bundle": True, "bundle_version": "gravity_v2"},
        }
    )
    client = httpx.AsyncClient(transport=transport, base_url="http://ml.test")
    try:
        health = _run(probe_model_health(client=client))
    finally:
        _run(client.aclose())
    assert health.status == "production"
    assert health.model_version == "gravity_v2"
