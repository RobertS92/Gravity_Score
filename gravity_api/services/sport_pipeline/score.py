"""Sport-specific ML scoring with BPXVR feature snapshot."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from gravity_api.config import get_settings
from gravity_api.feature_engineering.types import AthleteFeatureSnapshot
from gravity_api.services.cohort_latents import fetch_sport_cohort_latents
from gravity_api.services.gravity_calibration import apply_calibration_to_score
from gravity_api.services.heuristic_gravity import compute_heuristic_gravity_v1
from gravity_api.services.scoring_stack import (
    apply_tier2_fallback_if_needed,
    finalize_score_metadata,
)
from gravity_api.services.sport_pipeline.config import SportPipelineConfig, get_sport_pipeline_config
from gravity_api.services.sport_pipeline.raw_payload import merge_raw_with_bpxvr
from gravity_ml.brand.taxonomy import enrich_raw_with_partnerships

logger = logging.getLogger(__name__)


def _local_bundle_root() -> str:
    root = os.environ.get("MODEL_BUNDLE_ROOT") or os.environ.get("MODEL_BUNDLE_PATH")
    if root:
        return root
    from pathlib import Path

    return str(Path(__file__).resolve().parents[3] / "models" / "bundles")


def _score_with_local_bundle(
    *,
    athlete_id: str,
    sport: str,
    raw_data: dict[str, Any],
    pipeline: SportPipelineConfig,
    model_version: str,
) -> dict[str, Any]:
    """Run champion bundle inference in-process (bypasses Railway when weights are local)."""
    os.environ.setdefault("MODEL_BUNDLE_ROOT", _local_bundle_root())
    from gravity_ml.inference.predict import score_athlete
    from gravity_ml.schemas import ScoreAthleteRequest

    import gravity_ml.inference.bundle_loader as bundle_loader

    bundle_loader._loader = None
    req = ScoreAthleteRequest(
        athlete_id=athlete_id,
        sport=sport,
        model_key=pipeline.model_key,
        model_version=model_version,
        feature_schema_version=pipeline.feature_schema_version,
        raw_data=raw_data,
    )
    out = score_athlete(req)
    payload = out.model_dump()
    payload.setdefault("model_key", pipeline.model_key)
    return payload


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
    cohort_latent_scores: list[float] | None = None,
) -> dict[str, Any]:
    """Score via local bundles, remote ML HTTP, or heuristic fallback."""
    pipeline = pipeline or get_sport_pipeline_config(sport)
    enriched = merge_raw_with_bpxvr(raw_data, snapshot) if snapshot else raw_data
    enriched = enrich_raw_with_partnerships(enriched)

    cohort = cohort_latent_scores
    if cohort is None:
        try:
            cohort = await fetch_sport_cohort_latents(conn, sport)
        except Exception as exc:
            logger.debug("Cohort latents unavailable for %s: %s", sport, exc)
            cohort = None

    os.environ.setdefault("MODEL_BUNDLE_ROOT", _local_bundle_root())
    from gravity_ml.inference.bundle_loader import get_bundle_loader

    loader = get_bundle_loader()
    if not loader.has_model(pipeline.model_key):
        logger.info(
            "No champion bundle for %s — heuristic_gravity_v1",
            pipeline.model_key,
        )
        fallback = compute_heuristic_gravity_v1(enriched, sport, snapshot=snapshot, cohort_latent_scores=cohort)
        fallback["model_key"] = pipeline.model_key
        return finalize_score_metadata(fallback)

    champion_version = await fetch_champion_model_version(conn, pipeline.model_key)
    model_version = champion_version or pipeline.model_version

    scoring_mode = os.environ.get("SCORING_MODE", "").strip().lower()
    if scoring_mode in ("local", "local_ml"):
        payload = _score_with_local_bundle(
            athlete_id=athlete_id,
            sport=sport,
            raw_data=enriched,
            pipeline=pipeline,
            model_version=model_version,
        )
        payload = apply_tier2_fallback_if_needed(
            payload, enriched, sport, snapshot=snapshot, cohort_latent_scores=cohort
        )
        if cohort:
            payload = apply_calibration_to_score(payload, sport=sport, cohort_latents=cohort, raw=enriched)
        return finalize_score_metadata(payload)

    settings = get_settings()
    if not settings.ml_service_url or not settings.ml_api_key:
        raise RuntimeError("ML service not configured")

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
                if payload.get("fallback_used") and os.environ.get(
                    "LOCAL_ML_ON_REMOTE_FAIL", "1"
                ).strip().lower() in ("1", "true", "yes"):
                    local = _score_with_local_bundle(
                        athlete_id=athlete_id,
                        sport=sport,
                        raw_data=enriched,
                        pipeline=pipeline,
                        model_version=model_version,
                    )
                    if not local.get("fallback_used"):
                        payload = local
                payload = apply_tier2_fallback_if_needed(
                    payload, enriched, sport, snapshot=snapshot, cohort_latent_scores=cohort
                )
                if cohort:
                    payload = apply_calibration_to_score(
                        payload, sport=sport, cohort_latents=cohort, raw=enriched
                    )
                return finalize_score_metadata(payload)
            except Exception as exc:
                last_error = exc
                logger.warning("ML score failed sport=%s endpoint=%s: %s", sport, endpoint, exc)

    logger.warning("Sport ML scoring failed for %s, heuristic fallback: %s", athlete_id, last_error)
    fallback = compute_heuristic_gravity_v1(enriched, sport, snapshot=snapshot, cohort_latent_scores=cohort)
    fallback["model_key"] = pipeline.model_key
    return finalize_score_metadata(fallback)
