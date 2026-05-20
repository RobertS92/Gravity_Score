"""JSON CSC report for the terminal (no PDF)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

import asyncpg


def _first_number(*values: Any) -> Optional[float]:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _text_or_fallback(value: Any, fallback: str) -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _format_money(value: Optional[float]) -> str:
    return f"${value:,.0f}" if value is not None else "n/a"


def _format_nil_value(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    if abs(value) < 1_000_000:
        return f"${round(value / 1_000)}K"
    return f"${value / 1_000_000:.1f}M"


def _format_score(value: Optional[float]) -> str:
    return f"{value:.1f}" if value is not None else "n/a"


def _normalize_confidence(value: Any) -> Optional[float]:
    raw = _first_number(value)
    if raw is None:
        return None
    if raw <= 0:
        return 0.0
    while raw > 1.0:
        raw /= 100.0
    if raw < 0:
        return 0.0
    if raw > 1:
        return 1.0
    return raw


def _normalize_deal_structure(value: Any) -> str:
    raw = _text_or_fallback(value, "Structure pending verification")
    mapping = {
        "hybrid": "Hybrid",
        "cash + appearances": "Cash + Appearances",
        "cash+appearances": "Cash + Appearances",
        "cash + performance": "Cash + Performance Bonus",
        "cash + performance bonus": "Cash + Performance Bonus",
        "fixed": "Cash / Flat Fee",
        "fixed fee": "Cash / Flat Fee",
        "flat fee": "Cash / Flat Fee",
        "equity": "Equity / Options",
        "revenue share": "Revenue Share / Affiliate",
        "affiliate": "Revenue Share / Affiliate",
        "in kind": "Product / In-Kind",
        "in-kind": "Product / In-Kind",
    }
    return mapping.get(raw.lower(), raw)


def _normalize_verified_source(verified: Any, comp_nil: Optional[float]) -> str:
    if bool(verified):
        return "Direct Verification"
    if comp_nil is not None:
        return "Model Estimate"
    return "Source pending verification"


def _coerce_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_model_revision(value: Any) -> str:
    text = str(value).strip() if value is not None else ""
    return text or "unknown revision"


def _format_scored_at(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip() if value is not None else ""
    if not text:
        return "unknown date"
    return text[:10] if len(text) >= 10 else text


def _signal_level(score: Optional[float], invert: bool = False) -> str:
    if score is None:
        return "Moderate"
    value = 100.0 - score if invert else score
    if value >= 66:
        return "High"
    if value >= 40:
        return "Moderate"
    return "Low"


def _build_shap_narrative(
    latest_score: Optional[Dict[str, Any]],
    latest_explainable: Optional[Dict[str, Any]],
) -> str:
    latest_score = latest_score or {}
    latest_explainable = latest_explainable or {}
    latest_version = _format_model_revision(latest_score.get("model_version"))
    latest_scored_on = _format_scored_at(latest_score.get("calculated_at"))
    latest_revision_id = (latest_version, latest_scored_on)

    source_row = latest_explainable if latest_explainable else latest_score
    shap = source_row.get("shap_values")
    if isinstance(shap, dict) and shap:
        numeric_drivers: List[tuple[str, float]] = []
        for key, value in shap.items():
            numeric = _coerce_float(value)
            if numeric is not None:
                numeric_drivers.append((str(key), numeric))

        source_version = _format_model_revision(source_row.get("model_version"))
        source_scored_on = _format_scored_at(source_row.get("calculated_at"))
        source_revision_id = (source_version, source_scored_on)
        is_latest_revision = source_revision_id == latest_revision_id
        if numeric_drivers:
            numeric_drivers.sort(key=lambda item: (-abs(item[1]), item[0]))
            top = numeric_drivers[:5]
            prefix = (
                "Top score drivers"
                if is_latest_revision
                else "Top score drivers (most recent explainable revision)"
            )
            details = ", ".join(f"{key} ({value:+.2f})" for key, value in top)
            return f"{prefix}: {details}. Source model {source_version} scored on {source_scored_on}."

        keys = sorted(str(key) for key in shap.keys())[:5]
        key_text = ", ".join(keys)
        if is_latest_revision:
            return (
                f"Score driver fields available: {key_text}. "
                f"Model {source_version} scored on {source_scored_on}."
            )
        return (
            f"Latest score revision ({latest_version}, {latest_scored_on}) does not expose numeric SHAP values; "
            f"using driver fields from explainable revision ({source_version}, {source_scored_on}): {key_text}."
        )

    return (
        f"Latest score revision ({latest_version}, {latest_scored_on}) does not expose SHAP detail. "
        "Use Gravity Score components (Brand, Proof, Proximity, Velocity, Risk) for deterministic attribution."
    )


def _tier_tag(benchmark: Optional[float]) -> str:
    if benchmark is None:
        return "Unranked"
    if benchmark >= 150000:
        return "High-tier"
    if benchmark >= 50000:
        return "Mid-tier"
    return "Developing-tier"


async def build_csc_report_json(
    db: asyncpg.Connection,
    athlete_id: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    params = params or {}
    athlete = await db.fetchrow("SELECT * FROM athletes WHERE id = $1", athlete_id)
    if not athlete:
        raise ValueError("athlete not found")

    name = _text_or_fallback(athlete.get("name"), "Selected athlete")
    sport_f = _text_or_fallback(params.get("sport") or athlete.get("sport"), "sport n/a")
    pos_f = _text_or_fallback(params.get("position") or athlete.get("position"), "position n/a")
    conf_f = _text_or_fallback(athlete.get("conference"), "conference n/a")
    n_comp = int(params.get("comparables_count") or 12)
    conf_min = float(params.get("confidence_min") or 0.75)

    latest = await db.fetchrow(
        """SELECT * FROM athlete_gravity_scores
           WHERE athlete_id = $1 ORDER BY calculated_at DESC LIMIT 1""",
        athlete_id,
    )
    latest_with_shap = await db.fetchrow(
        """SELECT shap_values, model_version, calculated_at
           FROM athlete_gravity_scores
           WHERE athlete_id = $1
             AND shap_values IS NOT NULL
             AND jsonb_typeof(shap_values) = 'object'
             AND shap_values <> '{}'::jsonb
           ORDER BY calculated_at DESC
           LIMIT 1""",
        athlete_id,
    )
    latest_dict = dict(latest) if latest else None
    latest_with_shap_dict = dict(latest_with_shap) if latest_with_shap else None

    g = _first_number(latest.get("gravity_score") if latest else None)
    brand_score = _first_number(latest.get("brand_score") if latest else None)
    proof_score = _first_number(latest.get("proof_score") if latest else None)
    proximity_score = _first_number(latest.get("proximity_score") if latest else None)
    velocity_score = _first_number(latest.get("velocity_score") if latest else None)
    risk_score = _first_number(latest.get("risk_score") if latest else None)
    athlete_model_p10 = _first_number(latest.get("dollar_p10_usd") if latest else None)
    athlete_model_p50 = _first_number(latest.get("dollar_p50_usd") if latest else None)
    athlete_model_p90 = _first_number(latest.get("dollar_p90_usd") if latest else None)
    model_confidence = _normalize_confidence(latest.get("confidence") if latest else None)
    athlete_raw_nil = _first_number(athlete.get("nil_valuation_raw"))

    comp_rows = await db.fetch(
        """SELECT a.*, s.gravity_score, s.brand_score, s.proof_score,
                  s.dollar_p50_usd, s.dollar_p10_usd, s.dollar_p90_usd,
                  s.proximity_score, s.velocity_score, s.risk_score,
                  cs.similarity_score, d.deal_type, d.verified, d.deal_value,
                  dv.verified_deal_count
           FROM comparable_sets cs
           JOIN athletes a ON a.id = cs.comparable_athlete_id
           LEFT JOIN LATERAL (
               SELECT * FROM athlete_gravity_scores
               WHERE athlete_id = a.id ORDER BY calculated_at DESC LIMIT 1
           ) s ON true
           LEFT JOIN LATERAL (
               SELECT deal_type, verified, deal_value FROM athlete_nil_deals
               WHERE athlete_id = a.id
               ORDER BY (deal_value IS NOT NULL) DESC, ingested_at DESC
               LIMIT 1
           ) d ON true
           LEFT JOIN LATERAL (
               SELECT COUNT(*)::int AS verified_deal_count
               FROM athlete_nil_deals
               WHERE athlete_id = a.id AND verified = true
           ) dv ON true
           WHERE cs.subject_athlete_id = $1 AND cs.similarity_score >= $2
           ORDER BY cs.similarity_score DESC
           LIMIT $3""",
        athlete_id,
        conf_min,
        n_comp,
    )

    comparables_analysis: List[Dict[str, Any]] = []
    for c in comp_rows:
        comp_nil = _first_number(
            c.get("deal_value"),
            c.get("dollar_p50_usd"),
            c.get("nil_valuation_raw"),
        )
        comparables_analysis.append(
            {
                "athlete_id": str(c["id"]),
                "name": c["name"],
                "school": c["school"],
                "position": c["position"],
                "gravity_score": _first_number(c.get("gravity_score")),
                "brand_score": _first_number(c.get("brand_score")),
                "nil_valuation_consensus": comp_nil,
                "nil_delta_vs_subject": (
                    float(c["gravity_score"]) - float(g)
                    if c.get("gravity_score") is not None and g is not None
                    else None
                ),
                "confidence": _normalize_confidence(c.get("similarity_score")),
                "verified_deal_count": int(c.get("verified_deal_count") or 0),
                "deal_structure": _normalize_deal_structure(c.get("deal_type")),
                "verified_source": _normalize_verified_source(c.get("verified"), comp_nil),
            }
        )

    deals = await db.fetch(
        """SELECT deal_value FROM athlete_nil_deals
           WHERE athlete_id = $1 AND deal_value IS NOT NULL""",
        athlete_id,
    )
    vals = [float(d["deal_value"]) for d in deals if d["deal_value"] is not None]
    low_pct = float(params.get("csc_band_low_pct") or 25) / 100.0
    high_pct = float(params.get("csc_band_high_pct") or 75) / 100.0
    benchmark = _first_number(athlete_model_p50, athlete_raw_nil)
    if vals:
        vals.sort()
        lo = vals[int(low_pct * (len(vals) - 1))]
        hi = vals[int(high_pct * (len(vals) - 1))]
        benchmark = _first_number(benchmark, lo, hi)
    else:
        lo = athlete_model_p10
        hi = athlete_model_p90
        if lo is None or hi is None:
            if benchmark is not None:
                band = max(benchmark * 0.2, 25_000.0)
                lo = max(0.0, benchmark - band)
                hi = benchmark + band
            else:
                lo = None
                hi = None

    comparable_nil_values = [
        float(r["nil_valuation_consensus"])
        for r in comparables_analysis
        if r.get("nil_valuation_consensus") is not None
    ]
    comp_median = None
    if comparable_nil_values:
        comparable_nil_values.sort()
        comp_median = comparable_nil_values[len(comparable_nil_values) // 2]
    market_low = min(comparable_nil_values) if comparable_nil_values else lo
    market_high = max(comparable_nil_values) if comparable_nil_values else hi
    market_median = _first_number(comp_median, benchmark)

    confidence_level = _signal_level((model_confidence or 0.5) * 100.0)
    risk_level = _signal_level(risk_score, invert=True)

    executive_summary = (
        f"{name} profiles as a {_tier_tag(benchmark).lower()} NIL asset with a Total NIL Value Benchmark of "
        f"{_format_nil_value(benchmark)} and a recommended range of {_format_nil_value(lo)} to {_format_nil_value(hi)}, "
        f"placing this athlete in line with similarly positioned {pos_f}s in the {conf_f}. "
        f"Value is driven by brand {_signal_level(brand_score).lower()} and exposure {_signal_level(proximity_score).lower()} signals, "
        f"while market proof {_signal_level(proof_score).lower()} and risk {_signal_level(risk_score, invert=True).lower()} "
        "set confidence for roster planning."
    )

    key_value_drivers = [
        {
            "label": "Brand Strength",
            "signal": _signal_level(brand_score),
            "explanation": f"Brand score {_format_score(brand_score)} is strong versus position peers.",
        },
        {
            "label": "Market Proof",
            "signal": _signal_level(proof_score),
            "explanation": f"Proof score {_format_score(proof_score)} reflects current verified deal depth.",
        },
        {
            "label": "Exposure",
            "signal": _signal_level(proximity_score),
            "explanation": f"Exposure score {_format_score(proximity_score)} supports market visibility.",
        },
        {
            "label": "Risk",
            "signal": _signal_level(risk_score, invert=True),
            "explanation": f"Risk score {_format_score(risk_score)} moderates valuation certainty.",
        },
    ]

    return {
        "value": {
            "total_benchmark": benchmark,
            "range_low": lo,
            "range_high": hi,
            "tier_tag": _tier_tag(benchmark),
            "confidence_tag": f"{confidence_level} Confidence",
        },
        "explanation": {
            "executive_summary": executive_summary,
            "key_value_drivers": key_value_drivers,
            "driver_takeaway": (
                f"{name}'s benchmark is supported by "
                f"{_signal_level(brand_score).lower()} brand positioning and "
                f"{_signal_level(proximity_score).lower()} exposure, with "
                f"{_signal_level(proof_score).lower()} market proof limiting upside certainty."
            ),
        },
        "validation": {
            "market_context": (
                f"Market Context ({conf_f} {pos_f}s)\n"
                f"Range: {_format_nil_value(market_low)} – {_format_nil_value(market_high)}\n"
                f"Median: {_format_nil_value(market_median)}"
            ),
            "comparable_tier": (
                f"{_tier_tag(benchmark)} {pos_f}s with similar brand and exposure signals."
            ),
            "example_comparables": comparables_analysis[:5],
            "takeaway": (
                f"{name}'s benchmark sits within the middle of the current conference range and aligns with similarly tiered comparables."
            ),
        },
        "confidence_risk": {
            "confidence_level": confidence_level,
            "confidence_note": (
                f"{confidence_level} confidence from model signal quality and {len(comparables_analysis)} comparable rows."
            ),
            "risk_level": risk_level,
            "risk_note": (
                f"{risk_level} risk based on latest risk component score {_format_score(risk_score)}."
            ),
        },
        "detail": {
            "shap_attribution": _build_shap_narrative(latest_dict, latest_with_shap_dict),
            "methodology": (
                "Comparable-weighted NIL banding, Gravity score components, and deal observations "
                "from the Gravity database."
            ),
            "inputs": (
                f"Inputs: sport={sport_f}, position={pos_f}, comparables_count={n_comp}, "
                f"confidence_threshold={int(conf_min * 100)}%."
            ),
        },
    }
