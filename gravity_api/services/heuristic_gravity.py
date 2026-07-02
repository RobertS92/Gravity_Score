"""Tier-2 deterministic feature ranker (heuristic_gravity_v1)."""

from __future__ import annotations

import math
from typing import Any

from gravity_api.feature_engineering.types import AthleteFeatureSnapshot
from gravity_api.services.athlete_score_sync import brand_gravity_score
from gravity_api.services.nil_valuation import elite_signal_strength, nil_from_row
from gravity_composite.composite import compute_gravity_raw

SPORT_WEIGHTS: dict[str, dict[str, float]] = {
    "default": {"brand": 0.30, "proof": 0.35, "velocity": 0.15, "proximity": 0.10, "risk": 0.10},
    "cfb": {"brand": 0.30, "proof": 0.35, "velocity": 0.15, "proximity": 0.10, "risk": 0.10},
    "ncaab_mens": {"brand": 0.32, "proof": 0.33, "velocity": 0.15, "proximity": 0.10, "risk": 0.10},
    "ncaab_womens": {"brand": 0.32, "proof": 0.33, "velocity": 0.15, "proximity": 0.10, "risk": 0.10},
}


def _f(raw: dict[str, Any], key: str, default: float = 0.0) -> float:
    val = raw.get(key)
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _block_index(snapshot: AthleteFeatureSnapshot | None, block: str) -> float | None:
    if snapshot is None:
        return None
    comp = getattr(snapshot, block, None)
    if comp is None:
        return None
    if comp.composite_index is not None:
        return float(comp.composite_index)
    if comp.composite_pctile is not None:
        return float(comp.composite_pctile)
    return None


def _brand_score(raw: dict[str, Any], snapshot: AthleteFeatureSnapshot | None) -> float:
    idx = _block_index(snapshot, "brand")
    if idx is not None:
        return min(100.0, max(5.0, idx))
    reach = _f(raw, "instagram_followers") + _f(raw, "tiktok_followers") + _f(raw, "twitter_followers")
    trends = _f(raw, "google_trends_score", 50.0)
    wiki = _f(raw, "wikipedia_page_views_30d")
    return min(100.0, max(10.0, 15.0 + math.log1p(reach) * 5.0 + trends * 0.15 + math.log1p(wiki) * 2.0))


def _proof_score(raw: dict[str, Any], snapshot: AthleteFeatureSnapshot | None, sport: str) -> float:
    idx = _block_index(snapshot, "proof")
    if idx is not None:
        return min(100.0, max(5.0, idx))
    proof = _f(raw, "proof_composite_pctile") or _f(raw, "proof_performance_index_pctile")
    if proof > 0:
        return min(100.0, max(10.0, proof))
    stars = _f(raw, "recruiting_stars")
    gp = _f(raw, "games_played_season") or _f(raw, "gp")
    awards = _f(raw, "all_american_count") + _f(raw, "national_awards_count")
    news = _f(raw, "news_count_30d")
    dqs = _f(raw, "data_quality_score", 0.55)
    base = 20.0 + stars * 8.0 + min(gp, 15) * 1.5 + awards * 5.0 + news * 1.2 + dqs * 15.0
    if sport == "cfb" and gp <= 0:
        base *= 0.85
    return min(100.0, max(10.0, base))


def _velocity_score(raw: dict[str, Any], snapshot: AthleteFeatureSnapshot | None) -> float:
    idx = _block_index(snapshot, "velocity")
    if idx is not None:
        return min(100.0, max(5.0, idx))
    growth = _f(raw, "instagram_followers_growth_30d") or _f(raw, "social_growth_delta")
    news = _f(raw, "news_count_30d")
    trends = _f(raw, "google_trends_momentum_30d") or (_f(raw, "google_trends_score", 50) - 50)
    return min(100.0, max(8.0, 25.0 + growth * 0.02 + news * 2.0 + trends * 0.4))


def _proximity_score(raw: dict[str, Any], snapshot: AthleteFeatureSnapshot | None) -> float:
    idx = _block_index(snapshot, "proximity")
    if idx is not None:
        return min(100.0, max(5.0, idx))
    conf = _f(raw, "conference_tier_score") or _f(raw, "program_context_score")
    if conf > 0:
        return min(100.0, max(15.0, conf))
    trends = _f(raw, "google_trends_score", 50.0)
    return min(100.0, max(20.0, 30.0 + trends * 0.35))


def _risk_score(raw: dict[str, Any], snapshot: AthleteFeatureSnapshot | None) -> float:
    idx = _block_index(snapshot, "risk")
    if idx is not None:
        return min(95.0, max(5.0, idx))
    dqs = _f(raw, "data_quality_score", 0.55)
    injured = _f(raw, "injury_status_score") or (80.0 if raw.get("injury_flag") else 0.0)
    return min(95.0, max(10.0, 55.0 - injured * 0.3 + (1.0 - dqs) * 25.0))


def _confidence_from_signals(raw: dict[str, Any], snapshot: AthleteFeatureSnapshot | None) -> float:
    score = 0.25
    if _f(raw, "instagram_followers") >= 100:
        score += 0.12
    if int(float(raw.get("instagram_followers_observed") or 0)) == 1:
        score += 0.08
    if _f(raw, "games_played_season") > 0 or _f(raw, "gp") > 0:
        score += 0.12
    if _f(raw, "recruiting_stars") >= 3:
        score += 0.08
    if int(float(raw.get("nil_valuation_observed") or 0)) == 1:
        score += 0.15
    if snapshot and snapshot.proof.composite_pctile is not None:
        score += 0.12
    if _f(raw, "proof_composite_pctile") > 0:
        score += 0.08
    return round(min(0.92, max(0.28, score)), 4)


def compute_heuristic_gravity_v1(
    raw: dict[str, Any],
    sport: str | None,
    *,
    snapshot: AthleteFeatureSnapshot | None = None,
) -> dict[str, Any]:
    """Weighted BPXVR-style fallback scorer; replaces flat composite ~77 clusters."""
    sport_key = (sport or "default").lower()
    weights = SPORT_WEIGHTS.get(sport_key, SPORT_WEIGHTS["default"])

    brand = _brand_score(raw, snapshot)
    proof = _proof_score(raw, snapshot, sport_key)
    velocity = _velocity_score(raw, snapshot)
    proximity = _proximity_score(raw, snapshot)
    risk = _risk_score(raw, snapshot)

    gravity = compute_gravity_raw(
        brand=brand,
        proof=proof,
        proximity=proximity,
        velocity=velocity,
        risk=risk,
        sport=sport,
    )

    confidence = _confidence_from_signals(raw, snapshot)
    nil_anchor = nil_from_row(raw) or _f(raw, "nil_valuation")
    elite = elite_signal_strength(raw)
    base_p50 = max(25_000.0, min(50_000_000.0, (gravity / 100.0) ** 2 * 8_000_000.0))
    if nil_anchor and nil_anchor > 0:
        weight = min(0.9, 0.45 + 0.45 * elite)
        p50 = base_p50 * (1.0 - weight) + nil_anchor * weight
        p50 = max(25_000.0, min(75_000_000.0, p50))
        dollar_quality = "moderate" if int(float(raw.get("nil_valuation_observed") or 0)) == 1 else "low"
    else:
        p50 = base_p50
        dollar_quality = "low"

    imputed: list[str] = []
    if not int(float(raw.get("instagram_followers_observed") or 0)):
        imputed.append("instagram_followers")
    if not int(float(raw.get("nil_valuation_observed") or 0)) and nil_anchor:
        imputed.append("nil_valuation")

    return {
        "gravity_score": round(gravity, 4),
        "brand_score": round(brand, 4),
        "proof_score": round(proof, 4),
        "proximity_score": round(proximity, 4),
        "velocity_score": round(velocity, 4),
        "risk_score": round(risk, 4),
        "confidence": confidence,
        "model_version": "heuristic_gravity_v1",
        "fallback_used": True,
        "fallback_kind": "heuristic_gravity_v1",
        "score_tier": 2,
        "dollar_p10_usd": round(p50 * 0.6, 2),
        "dollar_p50_usd": round(p50, 2),
        "dollar_p90_usd": round(p50 * 1.8, 2),
        "dollar_confidence": {
            "source": "heuristic_gravity_v1",
            "quality": dollar_quality,
            "nil_anchored": bool(nil_anchor and nil_anchor > 0),
        },
        "brand_gravity_score": brand_gravity_score(brand, velocity, proof),
        "imputed_fields_heuristic": imputed,
    }


__all__ = ["compute_heuristic_gravity_v1"]
