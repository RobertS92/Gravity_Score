"""Unified ML prediction — bundles + heuristic fallback."""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

from gravity_composite.composite import (
    component_confidences_from_raw,
    compute_gravity_confidence_weighted,
    get_composite_weights,
    shap_from_components,
)
from gravity_ml.brand.taxonomy import (
    apply_proof_partnership_boost,
    blend_brand_with_partnerships,
    enrich_raw_with_partnerships,
)
from gravity_ml.inference.bundle_loader import get_bundle_loader
from gravity_ml.inference.promotion_policy import (
    allow_ml_quality_models,
    beta_ranker_config,
    is_blocked_inference_model,
)
from gravity_ml.inference.vectorizer import stacked_features
from gravity_ml.schemas import (
    ScoreAthleteRequest,
    ScoreAthleteResponse,
    ScoreBrandRequest,
    ScoreBrandResponse,
    ScoreTeamRequest,
    ScoreTeamResponse,
)

logger = logging.getLogger(__name__)

SUPPORTED_SPORTS = (
    "cfb",
    "ncaab_mens",
    "ncaab_womens",
    "ncaa_baseball",
    "ncaa_volleyball",
    "nfl",
    "nba",
    "wnba",
)


def model_key(entity: str, sport: str, objective: str) -> str:
    return f"gravity_{entity}_{sport}_{objective}_v1"


def _f(raw: dict[str, Any], key: str, default: float = 0.0) -> float:
    val = raw.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _predict_from_bundle(bundle, raw: dict[str, Any]) -> dict[str, float] | None:
    try:
        model = bundle.load_model()
        vectorizer = bundle.load_vectorizer()
        values, mask = vectorizer.vectorize(raw)
        X = stacked_features(values, mask).reshape(1, -1)
        pred = model.predict(X)
        if isinstance(pred, np.ndarray):
            pred = float(pred.ravel()[0])
        else:
            pred = float(pred)
        return {"primary": pred}
    except Exception as exc:
        logger.warning("Bundle predict failed for %s: %s", bundle.model_key, exc)
        return None


PRO_SPORTS = frozenset({"nfl", "nba", "wnba"})


def _market_value_usd(raw: dict[str, Any], sport: str) -> float:
    """Primary dollar anchor: NIL for college, contract/endorsement for pro."""
    if sport in PRO_SPORTS:
        return max(
            _f(raw, "contract_aav_usd"),
            _f(raw, "contract_aav"),
            _f(raw, "contract_guaranteed_usd"),
            _f(raw, "endorsement_value_usd"),
            _f(raw, "endorsement_earnings"),
            _f(raw, "total_earnings_usd"),
        )
    return _f(raw, "nil_valuation")


def _components_from_raw(raw: dict[str, Any], sport: str) -> dict[str, float]:
    raw = enrich_raw_with_partnerships(raw)
    reach = _f(raw, "instagram_followers") + _f(raw, "tiktok_followers") + _f(raw, "twitter_followers")
    trends = _f(raw, "google_trends_score", 50.0)
    news = _f(raw, "news_count_30d")
    dqs = _f(raw, "data_quality_score", 0.72)
    market_val = _market_value_usd(raw, sport)
    sport_adj = {
        "cfb": 1.05, "ncaab_mens": 1.0, "ncaab_womens": 0.98,
        "ncaa_baseball": 0.92, "ncaa_volleyball": 0.96,
        "nfl": 1.08, "nba": 1.10, "wnba": 1.02,
    }.get(sport, 1.0)

    social_brand = min(100.0, max(15.0, 18.0 + math.log1p(reach) * 4.5 + trends * 0.18)) * sport_adj
    brand = blend_brand_with_partnerships(social_brand, _f(raw, "partnership_brand_score"))

    proof = min(100.0, max(15.0, 25.0 + news * 1.5 + dqs * 22.0)) * sport_adj
    pctile = raw.get("proof_composite_pctile") or raw.get("proof_performance_index_pctile")
    if pctile is not None:
        proof = 0.55 * proof + 0.45 * float(pctile)
    proof = apply_proof_partnership_boost(proof, _f(raw, "partnership_proof_boost"))

    proximity = min(100.0, max(20.0, 30.0 + math.log1p(market_val) * 3.0 + trends * 0.25))
    velocity = min(100.0, max(12.0, 18.0 + news * 2.0 + trends * 0.28))
    risk = min(95.0, max(8.0, 62.0 - dqs * 28.0 - news * 0.5))

    return {
        "brand": brand,
        "proof": proof,
        "proximity": proximity,
        "velocity": velocity,
        "risk": risk,
    }


def _quality_from_components(components: dict[str, float], raw: dict[str, Any], *, sport: str) -> float:
    """On-field quality — de-emphasizes pure social/brand."""
    proof = components["proof"]
    perf = _f(raw, "proof_composite_pctile") or _f(raw, "proof_performance_index_pctile") or proof
    stability = 100.0 - components["risk"] * 0.5
    if sport in PRO_SPORTS:
        tenure = min(100.0, _f(raw, "games_played_season") * 4.0) if raw.get("games_played_season") else 50.0
        q = 0.58 * perf + 0.27 * proof + 0.07 * tenure + 0.08 * stability
    else:
        recruiting = min(100.0, _f(raw, "recruiting_stars") * 20.0) if raw.get("recruiting_stars") else 50.0
        q = 0.55 * perf + 0.25 * proof + 0.12 * recruiting + 0.08 * stability
    return max(0.0, min(100.0, q))


def _dollar_bands(gravity: float, market_value_usd: float, sport: str) -> tuple[float, float, float]:
    base = max(25_000.0, min(75_000_000.0, gravity * 22_000.0 + math.log1p(market_value_usd) * 8000))
    if market_value_usd > 0:
        anchor = 0.35 if sport not in PRO_SPORTS else 0.55
        base = max(base, market_value_usd * anchor)
    if sport in PRO_SPORTS:
        base = max(base, gravity * 45_000.0)
    return base * 0.65, base, base * 1.55


def score_athlete(req: ScoreAthleteRequest) -> ScoreAthleteResponse:
    sport = req.sport
    raw = enrich_raw_with_partnerships(dict(req.raw_data))
    components = _components_from_raw(raw, sport)
    loader = get_bundle_loader()

    value_key = req.model_key or model_key("athlete", sport, "value")
    quality_key = model_key("athlete", sport, "quality")
    fallback_used = True
    model_version = req.model_version or "1.0.0-heuristic"
    gravity = None
    quality = None
    dollar_p50 = None

    value_bundle = loader.resolve(value_key) or loader.resolve(f"gravity_athlete_{sport}_v1")
    beta_cfg = beta_ranker_config(value_key) if value_bundle else None
    rank_only = bool(beta_cfg and beta_cfg.get("suppress_dollar_calibration"))

    if value_bundle:
        pred = _predict_from_bundle(value_bundle, raw)
        if pred:
            log_val = pred["primary"]
            if not rank_only:
                dollar_p50 = max(25_000.0, math.expm1(log_val))
            gravity = min(100.0, max(0.0, 20.0 + log_val * 8.5))
            model_version = value_bundle.version
            fallback_used = False

    quality_bundle = None
    if allow_ml_quality_models() and not is_blocked_inference_model(quality_key):
        quality_bundle = loader.resolve(quality_key)
    if quality_bundle:
        pred = _predict_from_bundle(quality_bundle, raw)
        if pred:
            quality = min(100.0, max(0.0, pred["primary"]))

    if gravity is None:
        weights = get_composite_weights(sport)
        confidences = component_confidences_from_raw(raw)
        gravity = compute_gravity_confidence_weighted(
            brand=components["brand"],
            proof=components["proof"],
            proximity=components["proximity"],
            velocity=components["velocity"],
            risk=components["risk"],
            confidences=confidences,
            weights=weights,
            sport=sport,
        )
        weights_prov = weights.provenance
        model_version = req.model_version or f"1.0.0-composite-{weights_prov}"

    if quality is None:
        quality = _quality_from_components(components, raw, sport=sport)

    market_val = _market_value_usd(raw, sport)
    if dollar_p50 is None:
        p10, dollar_p50, p90 = _dollar_bands(gravity, market_val, sport)
    elif rank_only:
        p10, _, p90 = _dollar_bands(gravity, market_val, sport)
    else:
        p10, _, p90 = _dollar_bands(gravity, market_val, sport)
        p10 = dollar_p50 * 0.65
        p90 = dollar_p50 * 1.55

    brand_g = 0.45 * components["brand"] + 0.35 * components["velocity"] + 0.20 * components["proof"]
    weights = get_composite_weights(sport)

    return ScoreAthleteResponse(
        athlete_id=req.athlete_id,
        sport=sport,
        model_key=value_key,
        model_version=model_version,
        gravity_score=round(gravity, 4),
        quality_score=round(quality, 4),
        brand_score=round(components["brand"], 4),
        proof_score=round(components["proof"], 4),
        proximity_score=round(components["proximity"], 4),
        velocity_score=round(components["velocity"], 4),
        risk_score=round(components["risk"], 4),
        confidence=0.78 if not fallback_used else (0.72 if raw.get("proof_performance_index_pctile") else 0.55),
        brand_gravity_score=round(brand_g, 4),
        partnership_brand_score=_f(raw, "partnership_brand_score") or None,
        partnership_top_brands=raw.get("partnership_top_brands"),
        dollar_p10_usd=round(p10, 2) if not rank_only else None,
        dollar_p50_usd=round(dollar_p50, 2) if not rank_only else None,
        dollar_p90_usd=round(p90, 2) if not rank_only else None,
        dollar_confidence={
            "source": "ml" if not fallback_used else "heuristic",
            "quality": "beta_rank_only" if rank_only else "moderate",
        },
        shap_values=shap_from_components(
            brand=components["brand"],
            proof=components["proof"],
            proximity=components["proximity"],
            velocity=components["velocity"],
            risk=components["risk"],
            weights=weights,
            sport=sport,
        ),
        fallback_used=fallback_used,
        feature_schema_version=req.feature_schema_version,
    )


def score_team(req: ScoreTeamRequest) -> ScoreTeamResponse:
    sport = req.sport
    raw = dict(req.raw_data)
    components = _components_from_raw(raw, sport)
    loader = get_bundle_loader()
    value_key = model_key("team", sport, "value")
    quality_key = model_key("team", sport, "quality")
    fallback_used = True
    gravity = _f(raw, "roster_value") or components["proof"]
    quality = _f(raw, "performance") or components["proof"]

    vb = loader.resolve(value_key)
    if vb:
        pred = _predict_from_bundle(vb, raw)
        if pred:
            gravity = min(100.0, max(0.0, pred["primary"]))
            fallback_used = False

    quality_bundle = None
    if allow_ml_quality_models() and not is_blocked_inference_model(quality_key):
        quality_bundle = loader.resolve(quality_key)
    if quality_bundle:
        pred = _predict_from_bundle(quality_bundle, raw)
        if pred:
            quality = min(100.0, max(0.0, pred["primary"]))

    if gravity is None:
        gravity = min(100.0, 0.35 * _f(raw, "roster_value", 50) + 0.25 * _f(raw, "market_reach", 50)
                      + 0.25 * _f(raw, "performance", 50) + 0.15 * _f(raw, "retention", 50))

    return ScoreTeamResponse(
        team_id=req.team_id,
        sport=sport,
        model_key=value_key,
        model_version=vb.version if vb else "1.0.0-heuristic-team",
        gravity_score=round(gravity, 4),
        quality_score=round(quality, 4),
        brand_score=round(components["brand"], 4),
        proof_score=round(components["proof"], 4),
        proximity_score=round(components["proximity"], 4),
        velocity_score=round(components["velocity"], 4),
        risk_score=round(components["risk"], 4),
        confidence=0.7 if not fallback_used else 0.45,
        fallback_used=fallback_used,
    )


def score_brand(req: ScoreBrandRequest) -> ScoreBrandResponse:
    from gravity_ml.brand.taxonomy import get_taxonomy

    raw = dict(req.raw_data)
    name = str(raw.get("name") or raw.get("brand_name") or "")
    taxonomy = get_taxonomy()
    entry = taxonomy.match_brand(name)
    prestige = entry.prestige if entry else 55.0
    category = entry.category if entry else "unknown"

    reach = _f(raw, "reach_score", prestige)
    authenticity = _f(raw, "authenticity_score", prestige * 0.9)
    value = _f(raw, "value_score", prestige * 0.85)
    fit = _f(raw, "fit_score", 60.0)
    stability = _f(raw, "stability_score", 70.0)
    gravity = 0.25 * reach + 0.2 * authenticity + 0.25 * value + 0.15 * fit + 0.15 * stability

    loader = get_bundle_loader()
    bk = "gravity_brand_sponsor_v1"
    bundle = loader.resolve(bk)
    fallback_used = True
    if bundle:
        pred = _predict_from_bundle(bundle, raw)
        if pred:
            gravity = min(100.0, max(0.0, pred["primary"]))
            fallback_used = False

    return ScoreBrandResponse(
        brand_id=req.brand_id,
        model_key=bk,
        model_version=bundle.version if bundle else "1.0.0-heuristic-brand",
        gravity_score=round(gravity, 4),
        reach_score=round(reach, 4),
        authenticity_score=round(authenticity, 4),
        value_score=round(value, 4),
        fit_score=round(fit, 4),
        stability_score=round(stability, 4),
        category=category,
        prestige_score=round(prestige, 4),
        fallback_used=fallback_used,
    )
