"""Brand Match scoring engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import asyncpg

from gravity_api.services.deal_pricing import price_standard_activation
from gravity_api.services.risk_utils import invert_risk_score


CONFERENCE_REGION_MAP: dict[str, set[str]] = {
    "sec": {"southeast", "national"},
    "big ten": {"midwest", "northeast", "national"},
    "big 12": {"midwest", "west", "national"},
    "acc": {"southeast", "northeast", "national"},
    "pac-12": {"west", "national"},
    "aac": {"southeast", "midwest", "national"},
    "mountain west": {"west", "national"},
}

POSITION_CATEGORY_AFFINITY: dict[str, dict[str, float]] = {
    "qb": {"finance": 0.92, "auto": 0.88, "tech": 0.86, "apparel": 0.82, "gaming": 0.78},
    "rb": {"apparel": 0.9, "food/beverage": 0.86, "gaming": 0.82, "tech": 0.72},
    "wr": {"apparel": 0.91, "food/beverage": 0.84, "gaming": 0.8, "tech": 0.76},
    "te": {"apparel": 0.84, "food/beverage": 0.82, "auto": 0.76},
    "ol": {"food/beverage": 0.78, "auto": 0.74, "finance": 0.68},
    "dl": {"apparel": 0.82, "food/beverage": 0.79, "gaming": 0.7},
    "lb": {"apparel": 0.83, "food/beverage": 0.8, "gaming": 0.72},
    "db": {"apparel": 0.84, "tech": 0.74, "gaming": 0.76},
    "g": {"apparel": 0.9, "gaming": 0.85, "tech": 0.82, "fashion": 0.88},
    "pg": {"apparel": 0.9, "gaming": 0.86, "tech": 0.84, "fashion": 0.88},
    "sg": {"apparel": 0.89, "gaming": 0.84, "tech": 0.82, "fashion": 0.87},
    "sf": {"apparel": 0.89, "gaming": 0.82, "fashion": 0.87},
    "pf": {"apparel": 0.85, "food/beverage": 0.8, "gaming": 0.76},
    "c": {"apparel": 0.82, "food/beverage": 0.81, "auto": 0.74},
}

DEAL_DENSITY_RANGES = {
    "few": (0, 2),
    "moderate": (3, 6),
}

SPORT_MAP = {
    "CFB": "cfb",
    "NCAAB": "mcbb",
    "NCAAW": "wcbb",
    "NCAAWB": "wcbb",
}


@dataclass
class BrandMatchBriefData:
    budget: float
    category: str
    geography: List[str]
    audience: List[str]
    risk_tolerance: float
    max_transfer_risk: bool
    authenticity_weight: float
    min_social_reach: Optional[float]
    prioritize_engagement: bool
    excluded_categories: List[str]
    deal_density_preference: str
    sports: List[str]


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _norm_text_set(items: Iterable[str]) -> set[str]:
    return {str(x).strip().lower() for x in items if str(x).strip()}


def _conference_regions(conference: Optional[str]) -> set[str]:
    if not conference:
        return {"national"}
    key = conference.strip().lower()
    return CONFERENCE_REGION_MAP.get(key, {"national"})


def _category_affinity(position: Optional[str], category: str) -> float:
    if not position:
        return 0.55
    pos = position.strip().lower()
    cat = category.strip().lower()
    if pos in POSITION_CATEGORY_AFFINITY and cat in POSITION_CATEGORY_AFFINITY[pos]:
        return POSITION_CATEGORY_AFFINITY[pos][cat]
    return 0.62


def _deal_density_score(preference: str, verified_deals_count: int) -> float:
    pref = (preference or "any").lower()
    if pref == "few":
        return 100.0 if verified_deals_count <= 2 else (60.0 if verified_deals_count <= 6 else 35.0)
    if pref == "moderate":
        return 100.0 if 3 <= verified_deals_count <= 6 else 55.0
    return 72.0


def _recommended_structure(risk_score: float, engagement_rate: Optional[float], verified_deals_count: int) -> str:
    if risk_score <= 72:
        return "PERFORMANCE_WEIGHTED"
    if (engagement_rate is not None and engagement_rate >= 6.5) and verified_deals_count <= 3:
        return "HYBRID"
    if risk_score >= 86 and verified_deals_count >= 5:
        return "FIXED"
    return "HYBRID"


def _calc_weights(brief: BrandMatchBriefData) -> dict[str, float]:
    weights = {
        "brand": 0.30,
        "geo": 0.20,
        "category": 0.20,
        "engagement": 0.15,
        "risk": 0.15,
    }
    if brief.prioritize_engagement:
        weights["engagement"] = 0.30
        weights["brand"] = 0.20
    if brief.budget < 300_000:
        # affordability precision comes from geo market fit budget sensitivity
        weights["geo"] = max(0.10, weights["geo"] - 0.10)
        weights["category"] = min(0.30, weights["category"] + 0.05)
        weights["risk"] = min(0.25, weights["risk"] + 0.05)
    total = sum(weights.values()) or 1.0
    return {k: v / total for k, v in weights.items()}


async def _fetch_candidates(db: asyncpg.Connection, sports_db: list[str], max_risk_cap: float) -> list[dict[str, Any]]:
    sports_pred = ""
    params: list[Any] = [max_risk_cap]
    if sports_db:
        sports_pred = "AND a.sport = ANY($2::text[])"
        params.append(sports_db)

    sql = f"""
        SELECT
            a.id, a.name, a.school, a.position, a.conference, a.sport, a.eligibility_year,
            a.is_active, COALESCE(a.data_quality_score, 1.0) AS data_quality_score,
            s.gravity_score, s.brand_score, s.proof_score, s.proximity_score, s.velocity_score, s.risk_score,
            s.dollar_p50_usd, s.dollar_p10_usd, s.dollar_p90_usd, s.calculated_at AS score_date,
            ss.instagram_followers, ss.twitter_followers, ss.tiktok_followers, ss.instagram_engagement_rate,
            ss.scraped_at AS social_date,
            d.verified_deals_count, d.avg_verified_deal_value, d.deal_categories
        FROM athletes a
        LEFT JOIN LATERAL (
            SELECT gravity_score, brand_score, proof_score, proximity_score, velocity_score, risk_score,
                   dollar_p10_usd, dollar_p50_usd, dollar_p90_usd, calculated_at
            FROM athlete_gravity_scores
            WHERE athlete_id = a.id
            ORDER BY calculated_at DESC
            LIMIT 1
        ) s ON true
        LEFT JOIN LATERAL (
            SELECT instagram_followers, twitter_followers, tiktok_followers, instagram_engagement_rate, scraped_at
            FROM social_snapshots
            WHERE athlete_id = a.id
            ORDER BY scraped_at DESC
            LIMIT 1
        ) ss ON true
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) FILTER (WHERE verified IS TRUE) AS verified_deals_count,
                AVG(deal_value) FILTER (WHERE verified IS TRUE AND deal_value > 0) AS avg_verified_deal_value,
                ARRAY_REMOVE(ARRAY_AGG(DISTINCT LOWER(brand_category)) FILTER (WHERE brand_category IS NOT NULL), NULL) AS deal_categories
            FROM athlete_nil_deals
            WHERE athlete_id = a.id
        ) d ON true
        WHERE s.gravity_score IS NOT NULL
          AND (a.is_active IS DISTINCT FROM FALSE)
          AND (s.risk_score IS NULL OR s.risk_score <= $1)
          {sports_pred}
        ORDER BY s.brand_score DESC NULLS LAST
        LIMIT 3000
    """
    try:
        rows = await db.fetch(sql, *params)
        return [dict(r) for r in rows]
    except Exception:
        # fallback for environments without social_snapshots or data_quality_score
        sql_fallback = f"""
            SELECT
                a.id, a.name, a.school, a.position, a.conference, a.sport, a.eligibility_year,
                TRUE AS is_active, 1.0 AS data_quality_score,
                s.gravity_score, s.brand_score, s.proof_score, s.proximity_score, s.velocity_score, s.risk_score,
                s.dollar_p50_usd, s.dollar_p10_usd, s.dollar_p90_usd, s.calculated_at AS score_date,
                NULL::BIGINT AS instagram_followers, NULL::BIGINT AS twitter_followers, NULL::BIGINT AS tiktok_followers,
                NULL::NUMERIC AS instagram_engagement_rate, NULL::TIMESTAMPTZ AS social_date,
                d.verified_deals_count, d.avg_verified_deal_value, d.deal_categories
            FROM athletes a
            LEFT JOIN LATERAL (
                SELECT gravity_score, brand_score, proof_score, proximity_score, velocity_score, risk_score,
                       dollar_p10_usd, dollar_p50_usd, dollar_p90_usd, calculated_at
                FROM athlete_gravity_scores
                WHERE athlete_id = a.id
                ORDER BY calculated_at DESC
                LIMIT 1
            ) s ON true
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*) FILTER (WHERE verified IS TRUE) AS verified_deals_count,
                    AVG(deal_value) FILTER (WHERE verified IS TRUE AND deal_value > 0) AS avg_verified_deal_value,
                    ARRAY_REMOVE(ARRAY_AGG(DISTINCT LOWER(brand_category)) FILTER (WHERE brand_category IS NOT NULL), NULL) AS deal_categories
                FROM athlete_nil_deals
                WHERE athlete_id = a.id
            ) d ON true
            WHERE s.gravity_score IS NOT NULL
              AND (s.risk_score IS NULL OR s.risk_score <= $1)
              {sports_pred}
            ORDER BY s.brand_score DESC NULLS LAST
            LIMIT 3000
        """
        rows = await db.fetch(sql_fallback, *params)
        return [dict(r) for r in rows]


def _score_candidate(row: dict[str, Any], brief: BrandMatchBriefData, weights: dict[str, float]) -> Optional[dict[str, Any]]:
    dqs = _safe_float(row.get("data_quality_score"), 1.0)
    if dqs < 0.35:
        return None

    reach = (
        _safe_float(row.get("instagram_followers"))
        + _safe_float(row.get("twitter_followers"))
        + _safe_float(row.get("tiktok_followers"))
    )
    if brief.min_social_reach is not None and reach < float(brief.min_social_reach):
        return None

    brand_score = _clamp(_safe_float(row.get("brand_score")))
    raw_risk = _clamp(_safe_float(row.get("risk_score"), 30.0))
    risk_score = _clamp(invert_risk_score(raw_risk) or 0.0)
    p50 = _safe_float(row.get("dollar_p50_usd"))
    avg_verified_deal = _safe_float(row.get("avg_verified_deal_value"))
    pricing = price_standard_activation(
        annual_benchmark=p50 if p50 > 0 else None,
        model_p50=p50 if p50 > 0 else None,
        cohort_stats={"size": 0, "benchmark_values": []},
        comparables=(
            [{"deal_value": avg_verified_deal, "dollar_p50_usd": p50}]
            if avg_verified_deal > 0
            else []
        ),
        sport=str(row.get("sport") or "").upper(),
        position_group=str(row.get("position_group") or row.get("position") or "").upper(),
        brand_score=brand_score,
        proof_score=_safe_float(row.get("proof_score"), 50.0),
        exposure_score=_safe_float(row.get("proximity_score"), 50.0),
        velocity_score=_safe_float(row.get("velocity_score"), 50.0),
        risk_score=raw_risk,
        model_confidence=0.55,
        verified_deals_count=int(row.get("verified_deals_count") or 0),
        cohort_fit="edge",
    )
    activation_mid = pricing.activation_deal_mid or avg_verified_deal or p50
    budget_cap = brief.budget * 1.2
    if activation_mid > 0 and activation_mid > budget_cap:
        return None

    engagement_rate = row.get("instagram_engagement_rate")
    engagement_val = _safe_float(engagement_rate, 0.0)
    conference_regions = _conference_regions(row.get("conference"))
    geo_target = _norm_text_set(brief.geography)
    geo_overlap = len(conference_regions.intersection(geo_target)) / max(1, len(geo_target)) if geo_target else 1.0
    geo_score = _clamp(geo_overlap * 100.0)

    category_affinity = _category_affinity(row.get("position"), brief.category)
    category_score = _clamp(category_affinity * 100.0)

    if activation_mid > 0:
        affordability = _clamp((brief.budget / activation_mid) * 100.0)
    else:
        affordability = 65.0

    social_reach_score = _clamp((reach / 2_000_000.0) * 100.0)
    engagement_score = _clamp(engagement_val * 12.0)
    if brief.prioritize_engagement:
        social_score = _clamp(engagement_score * 0.7 + social_reach_score * 0.3)
    else:
        social_score = _clamp(engagement_score * 0.4 + social_reach_score * 0.6)

    risk_target = (1.0 - float(brief.risk_tolerance)) * 100.0
    risk_alignment = _clamp(100.0 - abs(risk_score - risk_target))
    if brief.budget < 300_000:
        geo_score = _clamp(geo_score * 0.7 + affordability * 0.3)

    verified_deals_count = int(row.get("verified_deals_count") or 0)
    density_score = _deal_density_score(brief.deal_density_preference, verified_deals_count)
    category_score = _clamp(category_score * 0.75 + density_score * 0.25)

    # Convert weighted components into point contributions that sum to match_score.
    contrib_brand = brand_score * weights["brand"]
    contrib_geo = geo_score * weights["geo"]
    contrib_category = category_score * weights["category"]
    contrib_engagement = social_score * weights["engagement"]
    contrib_risk = risk_alignment * weights["risk"]
    match_score = _clamp(contrib_brand + contrib_geo + contrib_category + contrib_engagement + contrib_risk)

    deal_categories = _norm_text_set(row.get("deal_categories") or [])
    excluded = _norm_text_set(brief.excluded_categories)
    flags = sorted(deal_categories.intersection(excluded))

    if match_score < 50:
        return None

    sport_val = str(row.get("sport") or "").upper()
    class_year = row.get("eligibility_year")
    class_year_str = f"Y{class_year}" if class_year is not None else None
    out = {
        "athlete_id": str(row["id"]),
        "name": row.get("name"),
        "school": row.get("school"),
        "position": row.get("position"),
        "conference": row.get("conference"),
        "sport": sport_val if sport_val else None,
        "class_year": class_year_str,
        "match_score": round(match_score, 1),
        "gravity_score": _safe_float(row.get("gravity_score"), 0.0),
        "brand_score": _safe_float(row.get("brand_score"), 0.0),
        "deal_range_low": pricing.activation_deal_low,
        "deal_range_high": pricing.activation_deal_high,
        "social_combined_reach": int(reach) if reach > 0 else None,
        "instagram_engagement_rate": engagement_val if engagement_val > 0 else None,
        "verified_deals_count": verified_deals_count,
        "fit_rationale": (
            f"Brand {brand_score:.1f}, geo overlap {geo_score:.1f}, category authenticity {category_score:.1f}, "
            f"engagement quality {social_score:.1f}, risk alignment {risk_alignment:.1f}."
        ),
        "match_breakdown": {
            "brand_alignment": round(contrib_brand, 1),
            "geography_overlap": round(contrib_geo, 1),
            "category_authenticity": round(contrib_category, 1),
            "engagement_quality": round(contrib_engagement, 1),
            "risk_alignment": round(contrib_risk, 1),
        },
        "recommended_structure": _recommended_structure(risk_score, engagement_rate, verified_deals_count),
        "exclusion_flags": flags,
    }
    return out


async def run_brand_match(db: asyncpg.Connection, brief: BrandMatchBriefData) -> list[dict[str, Any]]:
    sports_db = [SPORT_MAP.get(s.upper(), s.lower()) for s in brief.sports if s]
    max_risk_cap = min(
        100.0,
        float(brief.risk_tolerance) * 100.0 + (25.0 if brief.max_transfer_risk else 0.0),
    )
    rows = await _fetch_candidates(db, sports_db, max_risk_cap)
    weights = _calc_weights(brief)
    scored = []
    for row in rows:
        item = _score_candidate(row, brief, weights)
        if item is not None:
            scored.append(item)
    scored.sort(key=lambda x: float(x.get("match_score") or 0.0), reverse=True)
    return scored[:25]
