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
        "Use Gravity Score Summary components (Brand, Proof, Proximity, Velocity, Risk) for deterministic attribution."
    )


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
    sport_f = params.get("sport") or athlete.get("sport")
    pos_f = params.get("position") or athlete.get("position")
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
    risk_score = _first_number(latest.get("risk_score") if latest else None)
    athlete_model_p10 = _first_number(latest.get("dollar_p10_usd") if latest else None)
    athlete_model_p50 = _first_number(latest.get("dollar_p50_usd") if latest else None)
    athlete_model_p90 = _first_number(latest.get("dollar_p90_usd") if latest else None)
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
    subject_nil_estimate = _first_number(athlete_model_p50, athlete_raw_nil)
    if vals:
        vals.sort()
        lo = vals[int(low_pct * (len(vals) - 1))]
        hi = vals[int(high_pct * (len(vals) - 1))]
        subject_nil_estimate = _first_number(subject_nil_estimate, lo, hi)
        nil_note = (
            f"Observed deal values for {name} span roughly "
            f"${lo:,.0f}–${hi:,.0f} based on {len(vals)} datapoints in-band."
        )
    else:
        lo = athlete_model_p10
        hi = athlete_model_p90
        if lo is not None and hi is not None:
            nil_note = (
                f"No direct deal values on file for {name}; using model-derived valuation "
                f"range of {_format_money(lo)}–{_format_money(hi)}."
            )
        elif subject_nil_estimate is not None:
            band = max(subject_nil_estimate * 0.2, 25_000.0)
            lo = max(0.0, subject_nil_estimate - band)
            hi = subject_nil_estimate + band
            nil_note = (
                f"No direct deal values on file for {name}; using a conservative fallback band "
                f"centered on {_format_money(subject_nil_estimate)}."
            )
        else:
            lo = None
            hi = None
            nil_note = (
                "No verified deal values or model valuation estimates are available; "
                "NIL range remains pending additional source data."
            )

    g_str = f"{g:.1f}" if g is not None else "n/a"
    table = (
        f"| Component | Score |\n|-----------|-------|\n"
        f"| Gravity | {g_str} |\n"
        f"| Brand | {_format_score(_first_number(latest.get('brand_score') if latest else None))} |\n"
        f"| Proof | {_format_score(_first_number(latest.get('proof_score') if latest else None))} |\n"
    )

    shap_narrative = _build_shap_narrative(latest_dict, latest_with_shap_dict)

    comparable_nil_values = [
        float(r["nil_valuation_consensus"])
        for r in comparables_analysis
        if r.get("nil_valuation_consensus") is not None
    ]
    comp_mid = None
    if comparable_nil_values:
        comparable_nil_values.sort()
        comp_mid = comparable_nil_values[len(comparable_nil_values) // 2]

    exec_chunks = [
        (
            f"{name} ({_text_or_fallback(sport_f, 'sport n/a')}, {_text_or_fallback(pos_f, 'position n/a')}) "
            f"carries a Gravity score of {g_str}"
            + (
                f" with Brand {brand_score:.1f}"
                if brand_score is not None
                else ""
            )
            + "."
        ),
        (
            f"{len(comparables_analysis)} high-confidence comparables (threshold {int(conf_min * 100)}%) "
            + (
                f"show a midpoint NIL estimate near {_format_money(comp_mid)}."
                if comp_mid is not None
                else "provide directional support even where direct NIL values are sparse."
            )
        ),
        (
            f"Current NIL position is {_format_money(subject_nil_estimate)} within an estimated band of "
            f"{_format_money(lo)}–{_format_money(hi)}"
            + (
                f", while latest risk is {risk_score:.1f}."
                if risk_score is not None
                else "."
            )
        ),
    ]
    executive_summary = " ".join(exec_chunks)

    return {
        "executive_summary": executive_summary,
        "gravity_score_table": table,
        "comparables_analysis": comparables_analysis,
        "nil_range_note": nil_note,
        "shap_narrative": shap_narrative,
        "risk_assessment": (
            f"Latest risk component: {risk_score:.1f}"
            if risk_score is not None
            else "Risk data unavailable."
        ),
        "methodology": (
            "Comparable-weighted NIL banding, Gravity score components, and deal observations "
            "from the Gravity database. Not legal or investment advice."
        ),
    }
