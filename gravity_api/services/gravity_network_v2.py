"""Gravity Network v2 orchestration and prediction persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import asyncpg
import httpx

from gravity_api.config import get_settings


def _headers() -> dict[str, str]:
    key = get_settings().ml_api_key
    return {"Authorization": f"Bearer {key}"} if key else {}


async def _post_ml(path: str, body: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.ml_service_url or not settings.ml_api_key:
        raise RuntimeError("Gravity ML service is not configured")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.ml_service_url}{path}",
            json=body,
            headers=_headers(),
        )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Gravity ML returned an invalid payload")
    return payload


async def _persist_prediction(
    conn: asyncpg.Connection,
    *,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any],
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
) -> None:
    await conn.execute(
        """INSERT INTO gravity_predictions (
             entity_type, entity_id, related_entity_type, related_entity_id,
             model_key, model_version, as_of, gravity_score, component_scores,
             predictions, intervals, confidence, data_quality_score,
             out_of_distribution_score, fallback_used, metadata
           ) VALUES (
             $1, $2::uuid, $3, $4::uuid, $5, $6, $7, $8, $9::jsonb,
             $10::jsonb, $11::jsonb, $12, $13, $14, $15, $16::jsonb
           )""",
        entity_type,
        entity_id,
        related_entity_type,
        related_entity_id,
        f"gravity_{entity_type}_v2",
        str(payload.get("model_version") or "unknown"),
        datetime.now(tz=timezone.utc),
        payload.get("gravity_score") or payload.get("fit_score"),
        json.dumps(payload.get("component_scores") or {}),
        json.dumps(
            {
                "growth_probability": payload.get("growth_probability"),
                "transfer_probability": payload.get("transfer_probability"),
                "fit_score": payload.get("fit_score"),
            }
        ),
        json.dumps(payload.get("value_usd") or {}),
        float(payload.get("confidence") or 0),
        float(payload.get("data_quality_score") or 0),
        payload.get("out_of_distribution_score"),
        bool(payload.get("fallback_used")),
        json.dumps({"ml_payload": payload}),
    )


async def score_athlete_v2(conn: asyncpg.Connection, athlete_id: str) -> dict[str, Any]:
    from gravity_api.services.sport_pipeline.run import run_athlete_pipeline

    result = await run_athlete_pipeline(conn, athlete_id, score=True)
    score = result.get("score") or {}
    row = await conn.fetchrow(
        """SELECT gravity_score, brand_score, proof_score, proximity_score,
                  velocity_score, risk_score, confidence, model_version,
                  dollar_p10_usd, dollar_p50_usd, dollar_p90_usd
           FROM athlete_gravity_scores WHERE athlete_id = $1
           ORDER BY calculated_at DESC LIMIT 1""",
        athlete_id,
    )
    payload = {
        "gravity_score": float(row["gravity_score"]) if row else score.get("gravity_score"),
        "component_scores": {
            "brand": float(row["brand_score"]) if row else None,
            "proof": float(row["proof_score"]) if row else None,
            "proximity": float(row["proximity_score"]) if row else None,
            "velocity": float(row["velocity_score"]) if row else None,
            "risk": float(row["risk_score"]) if row else None,
        },
        "model_version": row["model_version"] if row else score.get("model_version"),
        "confidence": float(row["confidence"]) if row and row["confidence"] else 0.5,
        "value_usd": {
            "p10": row["dollar_p10_usd"] if row else None,
            "p50": row["dollar_p50_usd"] if row else None,
            "p90": row["dollar_p90_usd"] if row else None,
        },
        "pipeline": result,
        "fallback_used": score.get("fallback_used", False),
    }
    await _persist_prediction(
        conn, entity_type="athlete", entity_id=str(athlete_id), payload=payload
    )
    return payload


async def score_team_v2(conn: asyncpg.Connection, team_id: str) -> dict[str, Any]:
    team = await conn.fetchrow("SELECT * FROM gravity_teams WHERE id = $1", team_id)
    if not team:
        raise ValueError("Team not found")
    aggregate = await conn.fetchrow(
        """SELECT
             COUNT(*)::int AS roster_size,
             AVG(s.gravity_score)::float AS roster_value,
             AVG(s.velocity_score)::float AS roster_velocity,
             AVG(100.0 - s.risk_score)::float AS roster_stability
           FROM athletes a
           LEFT JOIN LATERAL (
             SELECT * FROM athlete_gravity_scores
             WHERE athlete_id = a.id ORDER BY calculated_at DESC LIMIT 1
           ) s ON TRUE
           WHERE lower(trim(a.school)) = lower(trim($1))
             AND a.sport = $2 AND a.is_active IS DISTINCT FROM FALSE""",
        team["school"],
        team["sport"],
    )
    raw = {
        **dict(team),
        **dict(aggregate or {}),
        "retention": (aggregate or {}).get("roster_stability"),
        "performance": (aggregate or {}).get("roster_value"),
        "market_reach": (aggregate or {}).get("roster_velocity"),
        "data_quality_score": 0.7 if aggregate and aggregate["roster_size"] else 0.35,
    }
    payload = await _post_ml(
        "/score/team",
        {"team_id": str(team["id"]), "sport": team["sport"], "raw_data": raw},
    )
    await _persist_prediction(
        conn, entity_type="team", entity_id=str(team["id"]), payload=payload
    )
    return payload


async def score_brand_v2(conn: asyncpg.Connection, brand_id: str) -> dict[str, Any]:
    brand = await conn.fetchrow("SELECT * FROM gravity_brands WHERE id = $1", brand_id)
    if not brand:
        raise ValueError("Brand not found")
    outcomes = await conn.fetchrow(
        """SELECT
             COUNT(*)::int AS campaign_count,
             AVG(CASE WHEN impressions > 0 THEN engagements / impressions END)::float AS engagement_rate,
             AVG(CASE WHEN engagements > 0 THEN conversions / engagements END)::float AS conversion_rate,
             AVG(CASE WHEN renewed THEN 1.0 ELSE 0.0 END)::float AS renewal_rate,
             AVG(CASE WHEN completed THEN 1.0 ELSE 0.0 END)::float AS completion_rate
           FROM gravity_campaign_outcomes WHERE brand_id = $1""",
        brand_id,
    )
    row = dict(outcomes or {})
    raw = {
        **dict(brand),
        **row,
        "audience_demand": min(100.0, float(row.get("engagement_rate") or 0) * 1000),
        "activation_quality": float(row.get("completion_rate") or 0.5) * 100,
        "conversion": min(100.0, float(row.get("conversion_rate") or 0) * 1000),
        "renewal": float(row.get("renewal_rate") or 0.5) * 100,
        "brand_safety": 75.0,
        "data_quality_score": min(1.0, float(row.get("campaign_count") or 0) / 20.0),
    }
    payload = await _post_ml(
        "/score/brand", {"brand_id": str(brand["id"]), "raw_data": raw}
    )
    await _persist_prediction(
        conn, entity_type="brand", entity_id=str(brand["id"]), payload=payload
    )
    return payload


async def score_fit_v2(
    conn: asyncpg.Connection,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    context: list[float] | None = None,
) -> dict[str, Any]:
    async def entity_payload(entity_type: str, entity_id: str) -> dict[str, Any]:
        table = {
            "athlete": "athletes",
            "team": "gravity_teams",
            "brand": "gravity_brands",
        }.get(entity_type)
        if not table:
            raise ValueError("Unsupported entity type")
        row = await conn.fetchrow(f"SELECT * FROM {table} WHERE id = $1", entity_id)
        if not row:
            raise ValueError(f"{entity_type.title()} not found")
        return dict(row)

    source_data = await entity_payload(source_type, source_id)
    target_data = await entity_payload(target_type, target_id)
    payload = await _post_ml(
        "/score/fit",
        {
            "source_type": source_type,
            "source_id": source_id,
            "source_data": source_data,
            "target_type": target_type,
            "target_id": target_id,
            "target_data": target_data,
            "context": context or [],
        },
    )
    await _persist_prediction(
        conn,
        entity_type="relationship",
        entity_id=source_id,
        related_entity_type=target_type,
        related_entity_id=target_id,
        payload=payload,
    )
    return payload


__all__ = [
    "score_athlete_v2",
    "score_brand_v2",
    "score_fit_v2",
    "score_team_v2",
]
