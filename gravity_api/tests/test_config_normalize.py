"""Tests for `_normalize_service_url` to keep Railway env quirks from
silently disabling outbound HTTP calls (e.g. probe_failed:UnsupportedProtocol)."""

from __future__ import annotations

from gravity_api.config import _normalize_service_url


def test_none_passes_through():
    assert _normalize_service_url(None) is None


def test_blank_string_becomes_none():
    assert _normalize_service_url("") is None
    assert _normalize_service_url("   ") is None


def test_strips_trailing_slash_and_whitespace():
    assert _normalize_service_url("  https://api.example.com/  ") == "https://api.example.com"


def test_preserves_existing_https_scheme():
    assert _normalize_service_url("https://api.example.com") == "https://api.example.com"


def test_preserves_existing_http_scheme():
    assert _normalize_service_url("http://api.example.com:8002") == "http://api.example.com:8002"


def test_prepends_https_for_bare_public_host():
    assert (
        _normalize_service_url("gravityscore-production.up.railway.app")
        == "https://gravityscore-production.up.railway.app"
    )


def test_prepends_http_for_railway_internal_host():
    """Railway private networking only speaks plain HTTP."""
    assert (
        _normalize_service_url("gravity-ml.railway.internal:8002")
        == "http://gravity-ml.railway.internal:8002"
    )


def test_case_insensitive_scheme_detection():
    assert _normalize_service_url("HTTPS://api.example.com") == "HTTPS://api.example.com"
