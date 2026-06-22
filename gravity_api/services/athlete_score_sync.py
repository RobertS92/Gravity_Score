"""Pull athlete + program scores from gravity-ml and append athlete_gravity_scores row."""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, Optional

import asyncpg
import httpx

from gravity_api.config import get_settings
from gravity_api.services.nil_valuation import (
    elite_signal_strength,
    nil_from_row,
    sanitize_nil_valuation_usd,
)
from gravity_api.services.score_imputation import (
    apply_heuristic_imputations,
    apply_manual_imputations,
    load_manual_imputations,
)
from gravity_composite.composite import compute_gravity_raw

logger = logging.getLogger(__name__)


def _coerce_effective_dq(value: Any) -> Optional[float]:
    """Clamp the effective data-quality score to [0, 1] for persistence."""
    if value is None:
        return None
    try:
        dq = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, dq))


def brand_gravity_score(brand: float, velocity: float, proof: float) -> float:
    b, v, p = float(brand), float(velocity), float(proof)
    return round(min(100.0, 0.45 * b + 0.35 * v + 0.20 * p), 4)


def program_row_to_team_raw(program: asyncpg.Record) -> Dict[str, Any]:
    bud = program.get("collective_budget_usd")
    dma = program.get("dma_rank")
    nil_env = program.get("nil_environment_score")
    tv = program.get("annual_tv_appearances")
    # NOTE: `google_trends_score` and `program_social_followers` are placeholder
    # defaults — the programs table does not yet carry scraped program-level
    # search/social signals. They keep the team-gravity vector non-zero; replace
    # them with scraped values once the program scrapers populate those fields.
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
    *,
    scraped_raw: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build ML raw_data for scoring.

    Priority: latest scraper ``raw_athlete_data`` (richest), athlete-row NIL/recruiting,
    then social snapshot overlay for follower counts.
    """
    row: Dict[str, Any] = dict(scraped_raw) if scraped_raw else {}

    identity = {
        "sport": athlete["sport"],
        "player_name": athlete["name"],
        "team": athlete.get("team") or athlete["school"],
        "college": athlete["school"],
        "conference": athlete.get("conference"),
        "position": athlete.get("position"),
        "class_year": athlete.get("class_year"),
        "recruiting_rank_national": athlete.get("recruiting_rank_national"),
        "recruiting_stars": athlete.get("recruiting_stars"),
        "recruiting_rank_position": athlete.get("recruiting_rank_position"),
    }
    for key, val in identity.items():
        if val is not None and val != "":
            row[key] = val

    nil_usd = nil_from_row(row) or nil_from_row(dict(athlete))
    if nil_usd is not None:
        row["nil_valuation"] = nil_usd

    if row.get("data_quality_score") in (None, "", 0):
        row["data_quality_score"] = float(athlete.get("data_quality_score") or 0.72)

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


async def fetch_latest_scraped_raw(
    conn: asyncpg.Connection, athlete_id: str
) -> Dict[str, Any]:
    """Latest raw_athlete_data.raw_data dict for an athlete (empty if none)."""
    import json as _json

    try:
        row = await conn.fetchrow(
            """SELECT raw_data FROM raw_athlete_data
               WHERE athlete_id = $1::uuid
               ORDER BY scraped_at DESC NULLS LAST
               LIMIT 1""",
            athlete_id,
        )
    except Exception:
        return {}
    if not row or not row["raw_data"]:
        return {}
    rd = row["raw_data"]
    if isinstance(rd, str):
        return dict(_json.loads(rd))
    return dict(rd)


_SHAP_KEY_ALIASES = {
    "brand_score": "brand",
    "proof_score": "proof",
    "proximity_score": "proximity",
    "velocity_score": "velocity",
    "risk_score": "risk",
}


def _normalize_shap_key(raw_key: Any) -> str:
    key = str(raw_key).strip().lower().replace("-", "_").replace(" ", "_")
    if key.startswith("shap_"):
        key = key[5:]
    return _SHAP_KEY_ALIASES.get(key, key)


def _coerce_shap_value(raw_value: Any) -> Optional[float]:
    if raw_value is None:
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    if isinstance(raw_value, Mapping):
        for nested_key in ("shap", "value", "contribution", "impact", "weight"):
            nested_value = raw_value.get(nested_key)
            if nested_value is None:
                continue
            try:
                return float(nested_value)
            except (TypeError, ValueError):
                continue
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def _iter_shap_containers(score_data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    containers: list[Mapping[str, Any]] = [score_data]
    top_level_keys = (
        "shap_values",
        "shap",
        "shap_breakdown",
        "feature_attributions",
        "component_attributions",
    )
    for key in top_level_keys:
        value = score_data.get(key)
        if isinstance(value, Mapping):
            containers.append(value)

    nested_wrappers = ("explainability", "explanations", "attribution")
    for wrapper_key in nested_wrappers:
        wrapper = score_data.get(wrapper_key)
        if not isinstance(wrapper, Mapping):
            continue
        for key in top_level_keys:
            value = wrapper.get(key)
            if isinstance(value, Mapping):
                containers.append(value)
    return containers


def shap_values_from_ml(score_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse SHAP outputs across score revisions.

    Some revisions emit legacy `shap_<component>` fields while newer revisions
    return nested explainability payloads (e.g. `shap_values` or
    `explainability.shap_values`). We normalize all supported shapes into a
    stable `{component: contribution}` dictionary for persistence.
    """
    out: Dict[str, float] = {}
    containers = _iter_shap_containers(score_data)
    for index, container in enumerate(containers):
        allow_unprefixed = index > 0
        for raw_key, raw_value in container.items():
            normalized_key = _normalize_shap_key(raw_key)
            if not allow_unprefixed and not str(raw_key).startswith("shap_"):
                continue
            value = _coerce_shap_value(raw_value)
            if value is None:
                continue
            out[normalized_key] = value
    return out


def _heuristic_score_from_raw(raw: Dict[str, Any], sport: str | None) -> Dict[str, Any]:
    """
    Conservative deterministic fallback when ML scoring is unavailable.
    Keeps athlete rows score-complete instead of null while signaling low confidence.
    """
    ig = float(raw.get("instagram_followers") or 0)
    tt = float(raw.get("tiktok_followers") or 0)
    tw = float(raw.get("twitter_followers") or 0)
    news = float(raw.get("news_count_30d") or 0)
    trends = float(raw.get("google_trends_score") or 50)
    dqs = float(raw.get("data_quality_score") or 0.55)

    reach = ig + tt + tw
    sport_adj = 1.0
    if sport == "cfb":
        sport_adj = 1.05
    elif sport in {"ncaab_mens", "mcbb"}:
        sport_adj = 1.0
    elif sport in {"ncaab_womens", "wcbb"}:
        sport_adj = 0.95

    # Map rough signals into 0-100 component ranges.
    brand = min(100.0, max(20.0, 20.0 + (reach / 2500.0) + (trends * 0.20))) * sport_adj
    proof = min(100.0, max(20.0, 30.0 + (news * 1.8) + (dqs * 20.0))) * sport_adj
    proximity = min(100.0, max(25.0, 35.0 + (trends * 0.35) + (news * 0.6)))
    velocity = min(100.0, max(15.0, 20.0 + (news * 2.2) + (trends * 0.30)))
    # Lower risk when data quality is higher and signal is richer.
    risk = min(95.0, max(15.0, 65.0 - (dqs * 30.0) - (news * 0.8)))
    gravity = compute_gravity_raw(
        brand=brand,
        proof=proof,
        proximity=proximity,
        velocity=velocity,
        risk=risk,
        sport=sport,
    )

    # Component-derived band (gravity proxy). Historically this capped the
    # heuristic P50 at $2M, which made it impossible to model elite media
    # anchors (e.g. a sanitized NIL valuation of ~$21.9M) when ML was down —
    # the score row and the downstream CSC benchmark would disagree.
    base_p50 = max(25_000.0, min(2_000_000.0, gravity * 18_000.0))

    # `nil_valuation` is the already-sanitized USD anchor that
    # athlete_to_raw_data writes via nil_from_row. When it's present and the
    # athlete shows elite commercial signal, blend the heuristic P50 toward it
    # so the fallback agrees with the media anchor instead of being clamped.
    nil_anchor = float(raw.get("nil_valuation") or 0) or None
    elite = elite_signal_strength(raw)
    if nil_anchor and nil_anchor > 0:
        weight = min(0.9, 0.5 + 0.4 * elite)
        dollar_p50 = base_p50 * (1.0 - weight) + nil_anchor * weight
        dollar_p50 = max(25_000.0, min(75_000_000.0, dollar_p50))
        p10 = dollar_p50 * 0.6
        p90 = dollar_p50 * 1.8
        dollar_quality = "moderate" if elite >= 0.55 else "low"
    else:
        dollar_p50 = base_p50
        p10 = dollar_p50 * 0.65
        p90 = dollar_p50 * 1.45
        dollar_quality = "low"
    return {
        "gravity_score": round(gravity, 4),
        "brand_score": round(max(0.0, min(100.0, brand)), 4),
        "proof_score": round(max(0.0, min(100.0, proof)), 4),
        "proximity_score": round(max(0.0, min(100.0, proximity)), 4),
        "velocity_score": round(max(0.0, min(100.0, velocity)), 4),
        "risk_score": round(max(0.0, min(100.0, risk)), 4),
        "confidence": 0.35,
        "model_version": "heuristic_fallback_v1",
        "dollar_p10_usd": round(p10, 2),
        "dollar_p50_usd": round(dollar_p50, 2),
        "dollar_p90_usd": round(p90, 2),
        "dollar_confidence": {
            "source": "heuristic",
            "quality": dollar_quality,
            "nil_anchored": bool(nil_anchor),
        },
        "brand_gravity_score": brand_gravity_score(brand, velocity, proof),
    }


async def sync_athlete_score_from_ml(conn: asyncpg.Connection, athlete_id: str) -> Dict[str, Any]:
    settings = get_settings()

    athlete = await conn.fetchrow("SELECT * FROM athletes WHERE id = $1", athlete_id)
    if not athlete:
        raise ValueError("Athlete not found")

    prev_score = await conn.fetchval(
        """SELECT gravity_score FROM athlete_gravity_scores
           WHERE athlete_id = $1 ORDER BY calculated_at DESC LIMIT 1""",
        athlete["id"],
    )

    from gravity_api.services.sport_pipeline.run import run_athlete_pipeline

    pipeline_result = await run_athlete_pipeline(conn, athlete_id, score=True)
    score_data = pipeline_result.get("score") or {}

    row = await conn.fetchrow(
        """SELECT * FROM athlete_gravity_scores WHERE athlete_id = $1
           ORDER BY calculated_at DESC LIMIT 1""",
        athlete["id"],
    )
    if not row:
        raise RuntimeError("Pipeline did not persist a score row")

    headers = {"Authorization": f"Bearer {settings.ml_api_key}"} if settings.ml_api_key else {}
    base = settings.ml_service_url

    program = await conn.fetchrow(
        """SELECT * FROM programs
           WHERE lower(trim(school)) = lower(trim($1)) AND sport = $2
           LIMIT 1""",
        athlete["school"],
        athlete["sport"],
    )
    company_g: Optional[float] = None
    if program and base and settings.ml_api_key:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r2 = await client.post(
                    f"{base}/score/team/{athlete['sport']}",
                    json={
                        "team_id": str(program["id"]),
                        "sport": athlete["sport"],
                        "raw_data": program_row_to_team_raw(program),
                    },
                    headers=headers,
                )
            if r2.status_code == 200:
                body = r2.json()
                cg = body.get("gravity_score")
                if cg is not None:
                    company_g = float(cg)
                    await conn.execute(
                        """UPDATE athlete_gravity_scores SET company_gravity_score = $2
                           WHERE athlete_id = $1""",
                        athlete["id"],
                        company_g,
                    )
        except Exception as e:
            logger.warning("Team/program gravity skipped: %s", e)

    brand_g = float(row.get("brand_gravity_score") or 0)
    new_score = float(row["gravity_score"])

    if prev_score is not None:
        try:
            delta = new_score - float(prev_score)
            watchers = await conn.fetch(
                "SELECT DISTINCT user_id FROM watchlists WHERE athlete_id = $1",
                athlete["id"],
            )
            alert_rows: list[tuple[str, str]] = []
            if abs(delta) >= 3.0:
                alert_rows.append(("SCORE_MOVE", f"Gravity score moved {delta:+.1f}"))
            p50 = row.get("dollar_p50_usd")
            if p50 is not None and float(p50) >= 250_000:
                alert_rows.append(("NIL_SIGNAL", f"Model NIL P50 updated to {float(p50):,.0f}"))
            for wrow in watchers:
                for kind, reason in alert_rows:
                    await conn.execute(
                        """INSERT INTO score_alerts
                           (user_id, athlete_id, previous_score, new_score, delta, trigger_reason, read)
                           VALUES ($1, $2, $3, $4, $5, $6, false)""",
                        wrow["user_id"],
                        athlete["id"],
                        float(prev_score),
                        new_score,
                        delta,
                        f"{kind}: {reason}",
                    )
        except Exception as exc:
            logger.warning("score_alerts insert failed for %s: %s", athlete_id, exc)

    return {
        "ok": True,
        "athlete_id": str(athlete["id"]),
        "gravity_score": new_score,
        "company_gravity_score": company_g,
        "brand_gravity_score": brand_g,
        "dollar_p50_usd": row.get("dollar_p50_usd"),
        "pipeline": pipeline_result,
        "model_key": score_data.get("model_key"),
        "proof_pctile": pipeline_result.get("proof_pctile"),
        "proof_trajectory": pipeline_result.get("proof_trajectory"),
    }
