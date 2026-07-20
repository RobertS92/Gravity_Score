"""Unified ML prediction — bundles + heuristic fallback."""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

from gravity_composite.calibration import calibrate_display_score
from gravity_composite.composite import (
    component_confidences_from_raw,
    compute_gravity_confidence_weighted,
    get_composite_weights,
    perf_index_to_score,
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

_COMMERCIAL_USD_KNOTS: dict[str, tuple[tuple[float, float], ...]] = {
    "nfl": (
        (250_000.0, 35.0), (750_000.0, 45.0), (1_500_000.0, 52.0),
        (3_000_000.0, 58.0), (6_000_000.0, 64.0), (12_000_000.0, 70.0),
        (20_000_000.0, 75.0), (25_000_000.0, 79.0), (45_000_000.0, 87.0),
        (64_000_000.0, 93.0), (80_000_000.0, 96.0),
    ),
    "nba": (
        (500_000.0, 35.0), (1_000_000.0, 40.0), (3_000_000.0, 48.0),
        (8_000_000.0, 58.0), (15_000_000.0, 67.0), (25_000_000.0, 75.0),
        (40_000_000.0, 84.0), (55_000_000.0, 91.0), (70_000_000.0, 95.0),
    ),
}
_DEFAULT_COMMERCIAL_USD_KNOTS = _COMMERCIAL_USD_KNOTS["nfl"]


def commercial_gravity_from_log_usd(log_val: float, sport: str = "nfl") -> float:
    """Map log1p(market USD) to a conservative 0–96 commercial score."""
    x = float(log_val)
    knots = tuple(
        (math.log1p(usd), score)
        for usd, score in _COMMERCIAL_USD_KNOTS.get(sport, _DEFAULT_COMMERCIAL_USD_KNOTS)
    )
    if x <= knots[0][0]:
        return knots[0][1]
    if x >= knots[-1][0]:
        return knots[-1][1]
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if x <= x1:
            if x1 <= x0:
                return y1
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return knots[-1][1]


def _commercial_market_score(
    predicted_log_usd: float,
    raw: dict[str, Any],
    sport: str,
) -> tuple[float, float, dict[str, Any]]:
    predicted_usd = max(25_000.0, math.expm1(float(predicted_log_usd)))
    effective_log = float(predicted_log_usd)
    metadata: dict[str, Any] = {
        "predicted_market_value_usd": round(predicted_usd, 2),
        "market_anchor_used": False,
    }
    observed_usd = _f(raw, "observed_market_value_usd")
    if observed_usd > 0:
        confidence = min(1.0, max(0.0, _f(raw, "observed_market_value_confidence", 0.8)))
        anchor_weight = min(0.95, max(0.80, 0.70 + 0.25 * confidence))
        effective_log = (
            anchor_weight * math.log1p(observed_usd)
            + (1.0 - anchor_weight) * float(predicted_log_usd)
        )
        metadata.update(
            {
                "market_anchor_used": True,
                "observed_market_value_usd": round(observed_usd, 2),
                "observed_market_value_type": raw.get("observed_market_value_type"),
                "observed_market_value_source": raw.get("observed_market_value_source"),
                "market_anchor_weight": round(anchor_weight, 4),
            }
        )
    effective_usd = max(25_000.0, math.expm1(effective_log))
    score = commercial_gravity_from_log_usd(effective_log, sport)

    # Brand attention is a bounded secondary commercial signal. It may separate
    # similarly paid stars but can never turn an ordinary contract into 90+.
    reach = _trusted_social_reach(raw)
    wiki_views = _f(raw, "wikipedia_views_30d")
    if reach > 0 or wiki_views > 0:
        attention = max(
            math.log1p(reach) / math.log1p(5_000_000.0) if reach > 0 else 0.0,
            math.log1p(wiki_views) / math.log1p(1_000_000.0) if wiki_views > 0 else 0.0,
        )
        score += min(2.0, max(0.0, attention * 2.0))
    metadata["effective_market_value_usd"] = round(effective_usd, 2)
    return min(96.0, max(30.0, score)), effective_usd, metadata


def _market_value_usd(raw: dict[str, Any], sport: str) -> float:
    """Primary dollar anchor: NIL for college, contract/endorsement for pro."""
    if sport in PRO_SPORTS:
        return max(
            _f(raw, "observed_market_value_usd"),
            _f(raw, "contract_aav_usd"),
            _f(raw, "contract_aav"),
            _f(raw, "contract_guaranteed_usd"),
            _f(raw, "endorsement_value_usd"),
            _f(raw, "endorsement_earnings"),
            _f(raw, "total_earnings_usd"),
        )
    return _f(raw, "nil_valuation")


_TRUSTED_SOCIAL_AUTH_FLOOR = 70.0


def _social_audience_is_trusted(raw: dict[str, Any]) -> bool:
    verified = raw.get("social_account_verified")
    if verified is True or verified == 1:
        return True
    if isinstance(verified, str) and verified.strip().lower() in {"1", "true", "yes", "y"}:
        return True
    auth = _f(raw, "social_authenticity_score")
    return auth >= _TRUSTED_SOCIAL_AUTH_FLOOR


def _trusted_social_reach(raw: dict[str, Any]) -> float:
    """Follower reach usable for commercial brand. Drop untrusted team handles."""
    ig = _f(raw, "instagram_followers")
    tt = _f(raw, "tiktok_followers")
    tw = _f(raw, "twitter_followers")
    if _social_audience_is_trusted(raw):
        return ig + tt + tw
    return ig


def _components_from_raw(raw: dict[str, Any], sport: str) -> dict[str, float]:
    raw = enrich_raw_with_partnerships(raw)
    reach = _trusted_social_reach(raw)
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

    # Weak news/DQS prior — only used to fill gaps, NOT to dominate real on-field signal.
    proof_prior = min(100.0, max(15.0, 25.0 + news * 1.5 + dqs * 22.0)) * sport_adj
    pctile = raw.get("proof_composite_pctile")
    if pctile is None:
        pctile = raw.get("proof_performance_index_pctile")
    # z-sum performance index survives even when the cohort percentile is masked
    # (small/absent cohort). Normalize it so proof still tracks performance.
    perf_idx = raw.get("proof_composite_index")
    if perf_idx is None:
        perf_idx = raw.get("proof_performance_index_raw")
    if pctile is not None:
        # Real within-position percentile is the trustworthy on-field signal.
        proof = 0.80 * float(pctile) + 0.20 * proof_prior
    elif perf_idx is not None:
        proof = 0.70 * (perf_index_to_score(perf_idx) or proof_prior) + 0.30 * proof_prior
    else:
        proof = proof_prior
    proof = min(100.0, max(15.0, proof))
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
    commercial_metadata: dict[str, Any] = {}

    value_bundle = loader.resolve(value_key) or loader.resolve(f"gravity_athlete_{sport}_v1")
    beta_cfg = beta_ranker_config(value_key) if value_bundle else None
    rank_only = bool(beta_cfg and beta_cfg.get("suppress_dollar_calibration"))

    if value_bundle:
        pred = _predict_from_bundle(value_bundle, raw)
        if pred:
            log_val = pred["primary"]
            if not rank_only:
                gravity, dollar_p50, commercial_metadata = _commercial_market_score(
                    log_val, raw, sport
                )
            else:
                # Beta rank-only bundles predict log1p(NIL) for ordering — not absolute G.
                # Use feature-based composite for the displayed gravity score.
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

    cohort_latents = raw.get("cohort_latent_scores") or raw.get("_cohort_latent_scores")
    g_latent = gravity
    if (
        cohort_latents
        and isinstance(cohort_latents, (list, tuple))
        and len(cohort_latents) > 0
        and (fallback_used or rank_only)
    ):
        gravity, cohort_pctile = calibrate_display_score(g_latent, cohort_latents)
        dollar_conf_extra = {
            "gravity_score_latent": round(g_latent, 4),
            "gravity_cohort_percentile": cohort_pctile,
            "calibration_version": "1.0.0",
        }
    else:
        cohort_pctile = None
        dollar_conf_extra = {}
        if not fallback_used and not rank_only:
            dollar_conf_extra = {
                "gravity_score_latent": round(float(g_latent), 4),
                "calibration_version": "commercial_ml_passthrough",
            }

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
            **commercial_metadata,
            **dollar_conf_extra,
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
