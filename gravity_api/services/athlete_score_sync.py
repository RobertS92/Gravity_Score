"""Pull athlete + program scores from gravity-ml and append athlete_gravity_scores row."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import asyncpg
import httpx

from gravity_api.config import get_settings

logger = logging.getLogger(__name__)


def brand_gravity_score(brand: float, velocity: float, proof: float) -> float:
    b, v, p = float(brand), float(velocity), float(proof)
    return round(min(100.0, 0.45 * b + 0.35 * v + 0.20 * p), 4)


def program_row_to_team_raw(program: asyncpg.Record) -> Dict[str, Any]:
    bud = program.get("collective_budget_usd")
    dma = program.get("dma_rank")
    nil_env = program.get("nil_environment_score")
    tv = program.get("annual_tv_appearances")
    return {
        "nil_collective_budget_est": float(bud or 0) / 1_000_000.0,
        "school_market_rank": float(dma or 40),
        "conference_media_index": float(nil_env or 50),
        "news_count_30d": float(tv or 0),
        "google_trends_score": 52.0,
        "program_social_followers": float(dma or 50) * 1e5,
    }


def athlete_to_raw_data(
    athlete: asyncpg.Record,
    snap: Optional[asyncpg.Record],
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "sport": athlete["sport"],
        "player_name": athlete["name"],
        "team": athlete["school"],
        "college": athlete["school"],
        "conference": athlete["conference"],
        "position": athlete["position"],
        "data_quality_score": 0.72,
    }
    jn = athlete.get("jersey_number")
    if jn is not None and str(jn).strip():
        try:
            row["jersey_number"] = int(str(jn).strip()[:3])
        except ValueError:
            pass
    if snap:
        if snap.get("instagram_followers") is not None:
            row["instagram_followers"] = snap["instagram_followers"]
        if snap.get("tiktok_followers") is not None:
            row["tiktok_followers"] = snap["tiktok_followers"]
        if snap.get("twitter_followers") is not None:
            row["twitter_followers"] = snap["twitter_followers"]
        if snap.get("news_mentions_30d") is not None:
            row["news_count_30d"] = snap["news_mentions_30d"]
    return row


def shap_values_from_ml(score_data: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, float] = {}
    for k in ("brand", "proof", "proximity", "velocity", "risk"):
        v = score_data.get(f"shap_{k}")
        if v is not None:
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                pass
    return out


async def sync_athlete_score_from_ml(conn: asyncpg.Connection, athlete_id: str) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.ml_service_url or not settings.ml_api_key:
        raise RuntimeError("ML_SERVICE_URL (or ML_API_URL) and ML_API_KEY must be set")

    athlete = await conn.fetchrow("SELECT * FROM athletes WHERE id = $1", athlete_id)
    if not athlete:
        raise ValueError("Athlete not found")

    snap = await conn.fetchrow(
        """SELECT * FROM social_snapshots
           WHERE athlete_id = $1
           ORDER BY scraped_at DESC
           LIMIT 1""",
        athlete_id,
    )
    # Inject pre-computed program and brand context from athletes table (populated by scrapers pipeline)
    raw = athlete_to_raw_data(athlete, snap)
    pg_score = athlete.get("program_gravity_score")
    deal_brand_gravity = athlete.get("active_deal_brand_gravity")
    if pg_score is not None:
        raw["program_gravity_score"] = float(pg_score)
    if deal_brand_gravity is not None:
        raw["active_deal_brand_gravity"] = float(deal_brand_gravity)

    headers = {"Authorization": f"Bearer {settings.ml_api_key}"}
    base = settings.ml_service_url

    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{base}/score/athlete",
            params={"include_shap": "true"},
            json={
                "athlete_id": str(athlete["id"]),
                "sport": athlete["sport"],
                "raw_data": raw,
                "partial_scoring": False,
            },
            headers=headers,
        )
        r.raise_for_status()
        score_data = r.json()

    program = await conn.fetchrow(
        """SELECT * FROM programs
           WHERE lower(trim(school)) = lower(trim($1)) AND sport = $2
           LIMIT 1""",
        athlete["school"],
        athlete["sport"],
    )
    company_g: Optional[float] = None
    if program:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r2 = await client.post(
                    f"{base}/score/team",
                    json={
                        "team_id": str(program["id"]),
                        "raw_data": program_row_to_team_raw(program),
                    },
                    headers=headers,
                )
            if r2.status_code == 200:
                body = r2.json()
                cg = body.get("gravity_score")
                if cg is not None:
                    company_g = float(cg)
        except Exception as e:
            logger.warning("Team/program gravity skipped: %s", e)

    brand = float(score_data.get("brand_score") or 0)
    vel = float(score_data.get("velocity_score") or 0)
    proof = float(score_data.get("proof_score") or 0)
    bg = score_data.get("brand_gravity_score")
    brand_g = float(bg) if bg is not None else brand_gravity_score(brand, vel, proof)

    dconf = score_data.get("dollar_confidence")
    dconf_param: Any = None
    if isinstance(dconf, dict):
        dconf_param = dconf  # asyncpg serializes dict → jsonb automatically

    shap = shap_values_from_ml(score_data)

    import json as _json

    def _to_jsonb(v: Any) -> str | None:
        if v is None:
            return None
        return _json.dumps(v) if not isinstance(v, str) else v

    await conn.execute(
        """INSERT INTO athlete_gravity_scores (
            athlete_id, gravity_score, brand_score, proof_score, proximity_score,
            velocity_score, risk_score, confidence, model_version,
            dollar_p10_usd, dollar_p50_usd, dollar_p90_usd, dollar_confidence,
            company_gravity_score, brand_gravity_score,
            shap_values
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9,
            $10, $11, $12, $13::jsonb, $14, $15, $16::jsonb
        )""",
        athlete["id"],
        float(score_data["gravity_score"]),
        float(score_data.get("brand_score") or 0),
        float(score_data.get("proof_score") or 0),
        float(score_data.get("proximity_score") or 0),
        float(score_data.get("velocity_score") or 0),
        float(score_data.get("risk_score") or 0),
        float(score_data.get("confidence") or 0.5),
        str(score_data.get("model_version") or "ml_sync"),
        score_data.get("dollar_p10_usd"),
        score_data.get("dollar_p50_usd"),
        score_data.get("dollar_p90_usd"),
        _to_jsonb(dconf_param),
        company_g,
        brand_g,
        _to_jsonb(shap if shap else {}),
    )

    return {
        "ok": True,
        "athlete_id": str(athlete["id"]),
        "gravity_score": score_data["gravity_score"],
        "company_gravity_score": company_g,
        "brand_gravity_score": brand_g,
        "dollar_p50_usd": score_data.get("dollar_p50_usd"),
    }
