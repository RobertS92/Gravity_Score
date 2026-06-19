"""Gravity Network v2 orchestration and prediction persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import asyncpg
import httpx

from gravity_api.config import get_settings
from gravity_api.services.athlete_score_sync import (
    athlete_to_raw_data,
    fetch_latest_scraped_raw,
)


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
    athlete = await conn.fetchrow("SELECT * FROM athletes WHERE id = $1", athlete_id)
    if not athlete:
        raise ValueError("Athlete not found")
    social = await conn.fetchrow(
        """SELECT * FROM social_snapshots
           WHERE athlete_id = $1 ORDER BY scraped_at DESC LIMIT 1""",
        athlete_id,
    )
    scraped = await fetch_latest_scraped_raw(conn, athlete_id)
    raw = athlete_to_raw_data(athlete, social, scraped_raw=scraped)
    raw["collection_timestamp"] = (
        social.get("scraped_at").isoformat() if social and social.get("scraped_at") else None
    )
    payload = await _post_ml(
        "/score/athlete/v2",
        {
            "athlete_id": str(athlete["id"]),
            "sport": str(athlete["sport"]),
            "raw_data": raw,
        },
    )
    await _persist_prediction(
        conn, entity_type="athlete", entity_id=str(athlete["id"]), payload=payload
    )
    components = payload.get("component_scores") or {}
    value = payload.get("value_usd") or {}
    updated = await conn.execute(
        """UPDATE athlete_gravity_scores SET
             gravity_score = $2, brand_score = $3, proof_score = $4,
             proximity_score = $5, velocity_score = $6, risk_score = $7,
             confidence = $8, model_version = $9,
             dollar_p10_usd = $10, dollar_p50_usd = $11, dollar_p90_usd = $12,
             dollar_confidence = $13::jsonb, calculated_at = NOW()
           WHERE athlete_id = $1""",
        athlete["id"],
        payload.get("gravity_score"),
        components.get("brand"),
        components.get("proof"),
        components.get("proximity"),
        components.get("velocity"),
        components.get("risk"),
        payload.get("confidence"),
        payload.get("model_version"),
        value.get("p10"),
        value.get("p50"),
        value.get("p90"),
        json.dumps(
            {
                "confidence": payload.get("confidence"),
                "data_quality_score": payload.get("data_quality_score"),
                "out_of_distribution_score": payload.get("out_of_distribution_score"),
                "fallback_used": payload.get("fallback_used"),
            }
        ),
    )
    if updated == "UPDATE 0":
        await conn.execute(
            """INSERT INTO athlete_gravity_scores (
                 athlete_id, gravity_score, brand_score, proof_score, proximity_score,
                 velocity_score, risk_score, confidence, model_version,
                 dollar_p10_usd, dollar_p50_usd, dollar_p90_usd, dollar_confidence
               ) VALUES (
                 $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb
               )""",
            athlete["id"],
            payload.get("gravity_score"),
            components.get("brand"),
            components.get("proof"),
            components.get("proximity"),
            components.get("velocity"),
            components.get("risk"),
            payload.get("confidence"),
            payload.get("model_version"),
            value.get("p10"),
            value.get("p50"),
            value.get("p90"),
            json.dumps(
                {
                    "confidence": payload.get("confidence"),
                    "data_quality_score": payload.get("data_quality_score"),
                    "out_of_distribution_score": payload.get("out_of_distribution_score"),
                    "fallback_used": payload.get("fallback_used"),
                }
            ),
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
        "/score/team", {"entity_id": str(team["id"]), "raw_data": raw}
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
        "/score/brand", {"entity_id": str(brand["id"]), "raw_data": raw}
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
