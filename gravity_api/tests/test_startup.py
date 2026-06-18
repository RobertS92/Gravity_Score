"""Startup guardrails for production deploys."""

from __future__ import annotations

import pytest

from gravity_api.database import _connection_error_message, validate_pg_dsn_for_startup
from gravity_api.services.model_health import ModelHealth, should_abort_startup_on_fallback


def test_validate_pg_dsn_rejects_localhost_in_production(monkeypatch):
    with pytest.raises(RuntimeError, match="localhost in production"):
        validate_pg_dsn_for_startup(
            environment="production",
            pg_dsn="postgresql://user:pass@localhost:5432/gravity",
        )


def test_validate_pg_dsn_allows_localhost_in_development():
    validate_pg_dsn_for_startup(
        environment="development",
        pg_dsn="postgresql://user:pass@localhost:5432/gravity",
    )


def test_validate_pg_dsn_rejects_empty():
    with pytest.raises(RuntimeError, match="PG_DSN is empty"):
        validate_pg_dsn_for_startup(environment="production", pg_dsn="  ")


@pytest.mark.parametrize(
    "reason",
    [
        "ml_service_reports_no_bundle",
        "model_version_missing_from_probe",
        "ml_service_url_not_configured",
        "probe_failed:ConnectError",
        "probe_status_503",
        "wrong_service:gravity-scrapers",
    ],
)
def test_startup_does_not_abort_on_transient_ml_probe(monkeypatch, reason):
    monkeypatch.setenv("MODEL_FAIL_ON_FALLBACK", "1")
    health = ModelHealth(
        status="fallback",
        model_version="composite_fallback",
        reason=reason,
    )
    assert should_abort_startup_on_fallback(health) is False


def test_startup_aborts_on_confirmed_fallback(monkeypatch):
    monkeypatch.setenv("MODEL_FAIL_ON_FALLBACK", "1")
    health = ModelHealth(
        status="fallback",
        model_version="heuristic_fallback_v1",
        reason="fallback_version_detected",
    )
    assert should_abort_startup_on_fallback(health) is True


def test_startup_never_aborts_when_flag_unset(monkeypatch):
    monkeypatch.delenv("MODEL_FAIL_ON_FALLBACK", raising=False)
    health = ModelHealth(
        status="fallback",
        model_version="heuristic_fallback_v1",
        reason="fallback_version_detected",
    )
    assert should_abort_startup_on_fallback(health) is False


def test_connection_error_message_for_nxdomain():
    err = OSError("[Errno -2] Name or service not known")
    err.errno = -2
    msg = _connection_error_message(
        host_hint="db.deadbeef.supabase.co:5432/postgres",
        exc=err,
    )
    assert "does not resolve" in msg
    assert "NXDOMAIN" in msg
    assert "Transaction pooler" in msg
