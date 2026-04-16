"""JSON CSC report for the terminal (no PDF)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import asyncpg


async def build_csc_report_json(
    db: asyncpg.Connection,
    athlete_id: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    params = params or {}
    athlete = await db.fetchrow("SELECT * FROM athletes WHERE id = $1", athlete_id)
    if not athlete:
        raise ValueError("athlete not found")

    name = athlete["name"]
    sport_f = params.get("sport") or athlete.get("sport")
    pos_f = params.get("position") or athlete.get("position")
    n_comp = int(params.get("comparables_count") or 12)
    conf_min = float(params.get("confidence_min") or 0.75)

    latest = await db.fetchrow(
        """SELECT * FROM athlete_gravity_scores
           WHERE athlete_id = $1 ORDER BY calculated_at DESC LIMIT 1""",
        athlete_id,
    )
    g = float(latest["gravity_score"]) if latest and latest["gravity_score"] is not None else None

    comp_rows = await db.fetch(
        """SELECT a.*, s.gravity_score, s.brand_score, s.proof_score,
                  s.proximity_score, s.velocity_score, s.risk_score,
                  cs.similarity_score, d.deal_type, d.verified, d.deal_value
           FROM comparable_sets cs
           JOIN athletes a ON a.id = cs.comparable_athlete_id
           LEFT JOIN LATERAL (
               SELECT * FROM athlete_gravity_scores
               WHERE athlete_id = a.id ORDER BY calculated_at DESC LIMIT 1
           ) s ON true
           LEFT JOIN LATERAL (
               SELECT deal_type, verified, deal_value FROM athlete_nil_deals
               WHERE athlete_id = a.id ORDER BY ingested_at DESC LIMIT 1
           ) d ON true
           WHERE cs.subject_athlete_id = $1 AND cs.similarity_score >= $2
           ORDER BY cs.similarity_score DESC
           LIMIT $3""",
        athlete_id,
        conf_min,
        n_comp,
    )

    comparables_analysis: List[Dict[str, Any]] = []
    for c in comp_rows:
        comparables_analysis.append(
            {
                "athlete_id": str(c["id"]),
                "name": c["name"],
                "school": c["school"],
                "position": c["position"],
                "gravity_score": float(c["gravity_score"]) if c["gravity_score"] is not None else None,
                "brand_score": float(c["brand_score"]) if c["brand_score"] is not None else None,
                "nil_valuation_consensus": float(c["deal_value"]) if c["deal_value"] is not None else None,
                "nil_delta_vs_subject": (
                    float(c["gravity_score"]) - float(g)
                    if c["gravity_score"] is not None and g is not None
                    else None
                ),
                "confidence": float(c["similarity_score"]) if c["similarity_score"] is not None else None,
                "verified_deal_count": 1 if c.get("verified") else 0,
                "deal_structure": c.get("deal_type"),
                "verified_source": "yes" if c.get("verified") else None,
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
    if vals:
        vals.sort()
        lo = vals[int(low_pct * (len(vals) - 1))]
        hi = vals[int(high_pct * (len(vals) - 1))]
        nil_note = (
            f"Observed deal values for {name} span roughly "
            f"${lo:,.0f}–${hi:,.0f} based on {len(vals)} datapoints in-band."
        )
    else:
        nil_note = "No verified or estimated NIL deals on file; range uses comparable gravity scores only."

    g_str = f"{g:.1f}" if g is not None else "n/a"
    table = (
        f"| Component | Score |\n|-----------|-------|\n"
        f"| Gravity | {g_str} |\n"
        f"| Brand | {latest['brand_score'] if latest else 'n/a'} |\n"
        f"| Proof | {latest['proof_score'] if latest else 'n/a'} |\n"
    )

    shap = latest.get("shap_values") if latest else None
    if isinstance(shap, dict) and shap:
        shap_narrative = "Key drivers: " + ", ".join(f"{k}={v}" for k, v in list(shap.items())[:5])
    else:
        shap_narrative = "SHAP breakdown not available for this score revision."

    return {
        "executive_summary": (
            f"{name} ({sport_f}, {pos_f or '—'}) carries a Gravity score of {g_str}. "
            f"{len(comparables_analysis)} high-confidence comparables support the CSC-style banding below."
        ),
        "gravity_score_table": table,
        "comparables_analysis": comparables_analysis,
        "nil_range_note": nil_note,
        "shap_narrative": shap_narrative,
        "risk_assessment": (
            f"Latest risk component: {float(latest['risk_score']):.1f}" if latest else "Risk data unavailable."
        ),
        "methodology": (
            "Comparable-weighted NIL banding, Gravity score components, and deal observations "
            "from the Gravity database. Not legal or investment advice."
        ),
    }
