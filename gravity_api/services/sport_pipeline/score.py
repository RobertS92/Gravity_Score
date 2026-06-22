"""Sport-specific ML scoring with BPXVR feature snapshot."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from gravity_api.config import get_settings
from gravity_api.feature_engineering.types import AthleteFeatureSnapshot
from gravity_api.services.athlete_score_sync import _heuristic_score_from_raw
from gravity_api.services.sport_pipeline.config import SportPipelineConfig, get_sport_pipeline_config
from gravity_api.services.sport_pipeline.raw_payload import merge_raw_with_bpxvr
from gravity_ml.brand.taxonomy import enrich_raw_with_partnerships

logger = logging.getLogger(__name__)


async def fetch_champion_model_version(
    conn,
    model_key: str,
) -> str | None:
    try:
        row = await conn.fetchrow(
            """SELECT model_version FROM gravity_model_registry
               WHERE model_key = $1 AND stage = 'champion'
               LIMIT 1""",
            model_key,
        )
        return str(row["model_version"]) if row else None
    except Exception:
        return None


async def score_with_sport_model(
    conn,
    *,
    athlete_id: str,
    sport: str,
    raw_data: dict[str, Any],
    snapshot: AthleteFeatureSnapshot | None = None,
    pipeline: SportPipelineConfig | None = None,
) -> dict[str, Any]:
    """POST to sport-specific ML endpoint; fallback to generic /score/athlete."""
    settings = get_settings()
    if not settings.ml_service_url or not settings.ml_api_key:
        raise RuntimeError("ML service not configured")

    pipeline = pipeline or get_sport_pipeline_config(sport)
    enriched = merge_raw_with_bpxvr(raw_data, snapshot) if snapshot else raw_data
    enriched = enrich_raw_with_partnerships(enriched)

    champion_version = await fetch_champion_model_version(conn, pipeline.model_key)
    model_version = champion_version or pipeline.model_version

    body = {
        "athlete_id": athlete_id,
        "sport": sport,
        "model_key": pipeline.model_key,
        "model_version": model_version,
        "feature_schema_version": pipeline.feature_schema_version,
        "raw_data": enriched,
        "partial_scoring": False,
    }
    if snapshot:
        body["feature_snapshot"] = snapshot.to_dict()

    headers = {"Authorization": f"Bearer {settings.ml_api_key}"}
    endpoints = [pipeline.ml_endpoint, pipeline.fallback_endpoint]

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=120.0) as client:
        for endpoint in endpoints:
            try:
                r = await client.post(
                    f"{settings.ml_service_url}{endpoint}",
                    params={"include_shap": "true"},
                    json=body,
                    headers=headers,
                )
                if r.status_code == 404 and endpoint != pipeline.fallback_endpoint:
                    continue
                r.raise_for_status()
                payload = r.json()
                if not isinstance(payload, dict) or payload.get("gravity_score") is None:
                    raise ValueError("ML response missing gravity_score")
                payload.setdefault("model_version", model_version)
                payload.setdefault("model_key", pipeline.model_key)
                return payload
            except Exception as exc:
                last_error = exc
                logger.warning("ML score failed sport=%s endpoint=%s: %s", sport, endpoint, exc)

    logger.warning("Sport ML scoring failed for %s, heuristic fallback: %s", athlete_id, last_error)
    fallback = _heuristic_score_from_raw(enriched, sport)
    fallback["model_version"] = f"heuristic_{sport}"
    fallback["model_key"] = pipeline.model_key
    fallback["fallback_used"] = True
    return fallback
