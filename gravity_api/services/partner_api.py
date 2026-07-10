"""Partner API response shaping and key management."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any

import asyncpg

from gravity_api.config import get_settings
from gravity_api.partner_types import DEFAULT_SCOPES, PartnerContext

ATTRIBUTION_TEXT = "Powered by Gravity Score"
ATTRIBUTION_URL = "https://gravityscore.ai"


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return f"gsk_live_{secrets.token_hex(24)}"


def key_prefix(raw_key: str) -> str:
    return raw_key[:12]


def _invert_risk(v: object) -> float | None:
    if v is None:
        return None
    try:
        return max(0.0, min(100.0, 100.0 - float(v)))
    except (TypeError, ValueError):
        return None


def _float_or_none(v: object) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _iso_dt(v: object) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def attribution_block(athlete_id: str | None = None) -> dict[str, str]:
    out: dict[str, str] = {
        "text": ATTRIBUTION_TEXT,
        "url": ATTRIBUTION_URL,
    }
    if athlete_id:
        out["profile_url"] = f"{ATTRIBUTION_URL}/athletes/{athlete_id}"
    return out


def _parse_dollar_confidence(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        import json

        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _impact_score_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Public Impact Score fields (winning impact) plus deprecated value_* aliases.

    Internal storage remains ``value_score``. Partner-facing primary name is
    ``impact_score`` / Impact Score. Gravity Score stays commercial.

    Also accepts ``win_impact_score`` on the row or inside ``dollar_confidence``
    so partners still get Impact before/without the value_score column backfill.
    """
    dc = _parse_dollar_confidence(data.get("dollar_confidence"))
    impact = _float_or_none(
        data.get("value_score")
        if data.get("value_score") is not None
        else data.get("win_impact_score")
        if data.get("win_impact_score") is not None
        else dc.get("win_impact_score")
        if dc.get("win_impact_score") is not None
        else dc.get("value_score")
    )
    impact_pct = _float_or_none(
        data.get("value_sport_percentile")
        if data.get("value_sport_percentile") is not None
        else dc.get("value_sport_percentile")
    )
    impact_source = (
        data.get("value_score_source")
        or dc.get("value_score_source")
        or ("win_impact_v0" if impact is not None and data.get("value_score") is None else None)
    )
    return {
        "impact_score": impact,
        "impact_sport_percentile": impact_pct,
        "impact_score_source": impact_source,
        # Deprecated aliases — prefer impact_* for new integrations.
        "value_score": impact,
        "value_sport_percentile": impact_pct,
        "value_score_source": impact_source,
    }


def _score_quality_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Expose scoring-stack quality so partners can label high / mid / low.

    - score_tier 1 + no fallback → model (high)
    - mid fallbacks (heuristic_gravity_v1, ml_composite, …) → mid
    - low fallbacks (commercial_viability, composite_fallback, …) → low
    """
    dc = _parse_dollar_confidence(data.get("dollar_confidence"))
    score_tier = data.get("score_tier")
    if score_tier is None:
        score_tier = dc.get("score_tier")
    try:
        score_tier_int = int(score_tier) if score_tier is not None else None
    except (TypeError, ValueError):
        score_tier_int = None

    fallback_kind = data.get("fallback_kind")
    if fallback_kind is None:
        fallback_kind = dc.get("fallback_kind")

    fallback_used = data.get("fallback_used")
    if fallback_used is None and score_tier_int is not None:
        fallback_used = score_tier_int != 1
    if fallback_used is None and fallback_kind is not None:
        fallback_used = True

    quality = data.get("quality") or dc.get("quality")
    gravity_source = data.get("gravity_source") or dc.get("gravity_source")

    return {
        "score_tier": score_tier_int,
        "fallback_kind": fallback_kind,
        "fallback_used": bool(fallback_used) if fallback_used is not None else None,
        "quality": quality,
        "gravity_source": gravity_source,
    }


def format_partner_score_row(row: asyncpg.Record | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    athlete_id = str(data.get("athlete_id") or data.get("id") or "")
    return {
        "athlete_id": athlete_id,
        # Gravity = commercial / market value; Impact = winning impact.
        "gravity_score": _float_or_none(data.get("gravity_score")),
        "gravity_sport_percentile": _float_or_none(data.get("gravity_sport_percentile")),
        **_impact_score_fields(data),
        "components": {
            "brand": _float_or_none(data.get("brand_score")),
            "proof": _float_or_none(data.get("proof_score")),
            "proximity": _float_or_none(data.get("proximity_score")),
            "velocity": _float_or_none(data.get("velocity_score")),
            "risk": _invert_risk(data.get("risk_score")),
        },
        "nil_estimate_usd": {
            "p10": _float_or_none(data.get("dollar_p10_usd")),
            "p50": _float_or_none(data.get("dollar_p50_usd")),
            "p90": _float_or_none(data.get("dollar_p90_usd")),
        },
        "confidence": _float_or_none(data.get("confidence")),
        "model_version": data.get("model_version"),
        **_score_quality_fields(data),
        "calculated_at": _iso_dt(data.get("calculated_at")),
        "attribution": attribution_block(athlete_id),
    }


def format_partner_athlete_summary(row: asyncpg.Record | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    athlete_id = str(data.get("id") or data.get("athlete_id") or "")
    return {
        "athlete_id": athlete_id,
        "name": data.get("name"),
        "school": data.get("school"),
        "conference": data.get("conference"),
        "sport": data.get("sport"),
        "position": data.get("position"),
        "gravity_score": _float_or_none(data.get("gravity_score")),
        "gravity_sport_percentile": _float_or_none(data.get("gravity_sport_percentile")),
        **_impact_score_fields(data),
        "components": {
            "brand": _float_or_none(data.get("brand_score")),
            "proof": _float_or_none(data.get("proof_score")),
            "proximity": _float_or_none(data.get("proximity_score")),
            "velocity": _float_or_none(data.get("velocity_score")),
            "risk": _float_or_none(data.get("risk_score")),
        },
        "nil_estimate_usd": {
            "p50": _float_or_none(data.get("dollar_p50_usd") or data.get("nil_estimate")),
        },
        "confidence": _float_or_none(data.get("confidence")),
        "model_version": data.get("model_version"),
        **_score_quality_fields(data),
        "calculated_at": _iso_dt(data.get("score_date") or data.get("calculated_at")),
        "attribution": attribution_block(athlete_id),
    }


def format_partner_athlete_detail(
    athlete: asyncpg.Record | dict[str, Any],
    latest_score: asyncpg.Record | dict[str, Any] | None,
) -> dict[str, Any]:
    athlete_data = dict(athlete)
    athlete_id = str(athlete_data.get("id") or "")
    score_payload = format_partner_score_row(latest_score or {}) if latest_score else None
    if score_payload and not score_payload.get("athlete_id"):
        score_payload["athlete_id"] = athlete_id
    return {
        "athlete_id": athlete_id,
        "name": athlete_data.get("name"),
        "school": athlete_data.get("school"),
        "conference": athlete_data.get("conference"),
        "sport": athlete_data.get("sport"),
        "position": athlete_data.get("position"),
        "position_group": athlete_data.get("position_group"),
        "photo_url": athlete_data.get("photo_url"),
        "score": score_payload,
        "attribution": attribution_block(athlete_id),
    }


def format_score_history_point(row: asyncpg.Record | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    return {
        "gravity_score": _float_or_none(data.get("gravity_score")),
        "gravity_sport_percentile": _float_or_none(data.get("gravity_sport_percentile")),
        **_impact_score_fields(data),
        "components": {
            "brand": _float_or_none(data.get("brand_score")),
            "proof": _float_or_none(data.get("proof_score")),
            "proximity": _float_or_none(data.get("proximity_score")),
            "velocity": _float_or_none(data.get("velocity_score")),
            "risk": _invert_risk(data.get("risk_score")),
        },
        "confidence": _float_or_none(data.get("confidence")),
        "calculated_at": _iso_dt(data.get("calculated_at")),
    }


async def resolve_partner_context(conn: asyncpg.Connection, raw_key: str) -> PartnerContext | None:
    settings = get_settings()
    bootstrap = (settings.partner_api_key or "").strip()
    if bootstrap and raw_key == bootstrap:
        return PartnerContext(
            partner_id=None,
            partner_name="env-bootstrap",
            scopes=DEFAULT_SCOPES,
            rate_limit_per_minute=settings.partner_api_rate_limit_per_minute,
            allowed_origins=None,
        )

    key_hash = hash_api_key(raw_key)
    try:
        row = await conn.fetchrow(
            """SELECT id, partner_name, scopes, allowed_origins, rate_limit_per_minute, expires_at
               FROM partner_api_keys
               WHERE key_hash = $1 AND is_active = TRUE""",
            key_hash,
        )
    except asyncpg.UndefinedTableError:
        return None

    if not row:
        return None
    if row["expires_at"] is not None:
        expires = row["expires_at"]
        now = datetime.now(tz=expires.tzinfo or timezone.utc)
        if expires < now:
            return None

    scopes = frozenset(row["scopes"] or list(DEFAULT_SCOPES))
    origins_raw = row["allowed_origins"]
    origins = tuple(origins_raw) if origins_raw else None
    return PartnerContext(
        partner_id=row["id"],
        partner_name=row["partner_name"],
        scopes=scopes,
        rate_limit_per_minute=int(row["rate_limit_per_minute"]),
        allowed_origins=origins,
    )


async def create_partner_api_key(
    conn: asyncpg.Connection,
    *,
    partner_name: str,
    scopes: list[str] | None = None,
    allowed_origins: list[str] | None = None,
    rate_limit_per_minute: int = 120,
    expires_at: datetime | None = None,
) -> dict[str, Any]:
    raw_key = generate_api_key()
    scopes_list = scopes or sorted(DEFAULT_SCOPES)
    row = await conn.fetchrow(
        """INSERT INTO partner_api_keys (
               partner_name, key_hash, key_prefix, scopes, allowed_origins,
               rate_limit_per_minute, expires_at
           ) VALUES ($1, $2, $3, $4, $5, $6, $7)
           RETURNING id, partner_name, key_prefix, scopes, allowed_origins,
                     rate_limit_per_minute, created_at, expires_at""",
        partner_name.strip(),
        hash_api_key(raw_key),
        key_prefix(raw_key),
        scopes_list,
        allowed_origins,
        rate_limit_per_minute,
        expires_at,
    )
    return {
        "id": str(row["id"]),
        "partner_name": row["partner_name"],
        "api_key": raw_key,
        "key_prefix": row["key_prefix"],
        "scopes": list(row["scopes"] or []),
        "allowed_origins": list(row["allowed_origins"] or []),
        "rate_limit_per_minute": row["rate_limit_per_minute"],
        "created_at": _iso_dt(row["created_at"]),
        "expires_at": _iso_dt(row["expires_at"]),
        "warning": "Store api_key securely; it cannot be retrieved again.",
    }
