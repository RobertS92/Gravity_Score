"""Model health probe for the gravity-ml scoring service.

The CSC report spec requires that a fallback scorer (heuristic / composite)
must never silently back a binding valuation. This service surfaces the
current model status so:

  - The `/health` endpoint and ops dashboards can show a precise status.
  - `POST /v1/reports/csc` can return HTTP 503 when fallback is active.
  - Startup can hard-fail in production (`MODEL_FAIL_ON_FALLBACK=1`).

The probe is intentionally tolerant of a missing/unreachable ML service: it
records the cause and exposes `status='unknown'` rather than crashing the
API. Per-report enforcement still occurs against the actual `model_version`
stored on `athlete_gravity_scores`, so reports never ship over a fallback
even when the startup probe is inconclusive.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

import httpx

from gravity_api.config import get_settings

logger = logging.getLogger(__name__)


ModelStatus = Literal["production", "fallback", "unknown"]


_FALLBACK_VERSION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^heuristic_fallback", re.IGNORECASE),
    re.compile(r"^composite_fallback", re.IGNORECASE),
    re.compile(r"^ml_sync$", re.IGNORECASE),
    re.compile(r"fallback", re.IGNORECASE),
)


def classify_model_version(model_version: str | None) -> ModelStatus:
    """Return 'production' for a real bundle, 'fallback' for any heuristic.

    `None` / blank version strings are treated as unknown.
    """
    if not model_version:
        return "unknown"
    version = str(model_version).strip()
    if not version:
        return "unknown"
    for pattern in _FALLBACK_VERSION_PATTERNS:
        if pattern.search(version):
            return "fallback"
    return "production"


@dataclass
class ModelHealth:
    status: ModelStatus = "unknown"
    model_version: str | None = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    ml_service_url: str | None = None
    reason: str | None = None

    @property
    def is_fallback(self) -> bool:
        return self.status == "fallback"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "model_version": self.model_version,
            "checked_at": self.checked_at.isoformat(),
            "ml_service_url": self.ml_service_url,
            "reason": self.reason,
        }


_cached_health: ModelHealth = ModelHealth(reason="not_probed")


def get_model_health() -> ModelHealth:
    """Return the most recent cached probe result.

    Safe to call from any request handler — it is non-blocking.
    """
    return _cached_health


def set_model_health(health: ModelHealth) -> None:
    """Replace the cached probe (used by `probe_model_health` and tests)."""
    global _cached_health
    _cached_health = health


async def probe_model_health(
    *,
    client: httpx.AsyncClient | None = None,
    timeout_s: float = 5.0,
) -> ModelHealth:
    """Probe the configured gravity-ml service and update the cached state.

    Tries `<ML_SERVICE_URL>/health` first (lightweight), falling back to
    `<ML_SERVICE_URL>/model/info` if the former does not expose a
    `model_version`. Network errors are recorded but never raised.
    """
    settings = get_settings()
    ml_url = settings.ml_service_url
    health = ModelHealth(ml_service_url=ml_url)
    if not ml_url:
        health.status = "unknown"
        health.reason = "ml_service_url_not_configured"
        set_model_health(health)
        return health

    headers: dict[str, str] = {}
    if settings.ml_api_key:
        headers["X-API-Key"] = settings.ml_api_key

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=timeout_s)
    assert client is not None  # narrow for type-checker

    try:
        version: str | None = None
        bundle_loaded: bool | None = None
        wrong_service: str | None = None
        # `/health/ready` exposes ``model_bundle`` (true/false) on the real
        # gravity-ml service; `/health` and `/model/info` may carry an
        # explicit version. Probe in order — first hit with usable info wins.
        for path in ("/health/ready", "/health", "/model/info", "/models/status"):
            try:
                resp = await client.get(f"{ml_url}{path}", headers=headers)
            except httpx.HTTPError as exc:
                health.reason = f"probe_failed:{type(exc).__name__}"
                continue
            if resp.status_code >= 500:
                health.reason = f"probe_status_{resp.status_code}"
                continue
            if resp.status_code == 404:
                continue
            try:
                data = resp.json()
            except Exception:
                continue
            if not isinstance(data, dict):
                continue

            # Detect when ML_SERVICE_URL is mistakenly pointing at a
            # *different* Railway service (e.g. gravity-scrapers). The
            # ``service`` discriminator is the cheapest signal.
            service = data.get("service")
            if isinstance(service, str) and service.strip():
                lowered = service.strip().lower()
                if (
                    "ml" not in lowered
                    and "score" not in lowered
                    and "gravity-ml" not in lowered
                ):
                    wrong_service = service.strip()

            # Bundle presence (gravity-ml `/health/ready` shape).
            if "model_bundle" in data and isinstance(data["model_bundle"], bool):
                bundle_loaded = data["model_bundle"]

            candidate = (
                data.get("model_version")
                or data.get("modelVersion")
                or data.get("bundle_version")
                or (
                    data.get("active_bundle")
                    if isinstance(data.get("active_bundle"), str)
                    else None
                )
            )
            if candidate:
                version = str(candidate).strip()
                break

        health.model_version = version
        # gravity-ml `/health/ready` reports bundle presence without a version string.
        if version is None and bundle_loaded is True:
            health.status = "production"
            health.model_version = "gravity_athlete_v2"
            health.reason = "ml_service_reports_bundle_loaded"
        # Explicit `model_bundle: false` from gravity-ml beats any heuristic
        # — the service is telling us directly that it's serving fallback.
        elif version is None and bundle_loaded is False:
            health.status = "fallback"
            health.model_version = "composite_fallback"
            health.reason = "ml_service_reports_no_bundle"
        elif wrong_service:
            health.status = "unknown"
            health.reason = f"wrong_service:{wrong_service}"
        else:
            health.status = classify_model_version(version)
            if health.status == "production":
                health.reason = "ok"
            elif health.status == "fallback":
                health.reason = "fallback_version_detected"
            elif not health.reason:
                health.reason = "model_version_missing_from_probe"
    finally:
        if owns_client:
            await client.aclose()

    set_model_health(health)
    return health


def should_fail_on_fallback() -> bool:
    """Whether the process should exit if the startup probe reports a fallback."""
    raw = (os.environ.get("MODEL_FAIL_ON_FALLBACK") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def should_abort_startup_on_fallback(health: ModelHealth) -> bool:
    """Return True when startup should hard-fail because of ML fallback.

    ``MODEL_FAIL_ON_FALLBACK=1`` is meant to block binding valuations backed
    by a *confirmed* heuristic scorer. When gravity-ml is still deploying its
    bundle it may briefly report ``model_bundle=false``; in that transient case
    we warn and let the API boot — ``/health`` re-probes every 60s and CSC
    routes still enforce per-row ``model_version`` before shipping reports.
    """
    if not health.is_fallback or not should_fail_on_fallback():
        return False
    if health.reason in {
        "ml_service_reports_no_bundle",
        "model_version_missing_from_probe",
        "ml_service_url_not_configured",
    }:
        return False
    if health.reason and health.reason.startswith("probe_failed:"):
        return False
    if health.reason and health.reason.startswith("probe_status_"):
        return False
    if health.reason and health.reason.startswith("wrong_service:"):
        return False
    return True
