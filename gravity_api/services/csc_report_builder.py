"""JSON CSC report builder for the terminal."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

import asyncpg

from gravity_api.services.position_group_match import derive_position_group, position_aliases_for_group


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


def _format_nil_value(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    if abs(value) < 1_000_000:
        return f"${value / 1_000:.1f}K"
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
    return max(0.0, min(1.0, raw))


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


def _signal_level(score: Optional[float], *, invert: bool = False) -> str:
    if score is None:
        return "Moderate"
    value = 100.0 - score if invert else score
    if value >= 70:
        return "High"
    if value >= 40:
        return "Moderate"
    return "Low"


def _signal_rank(score: Optional[float], *, invert: bool = False) -> float:
    if score is None:
        return 50.0
    return (100.0 - score) if invert else score


def _cap_confidence(level: str, *, max_level: str | None = None, min_level: str | None = None) -> str:
    order = {"Low": 0, "Moderate": 1, "High": 2}
    idx = order.get(level, 1)
    if max_level is not None:
        idx = min(idx, order[max_level])
    if min_level is not None:
        idx = max(idx, order[min_level])
    for k, v in order.items():
        if v == idx:
            return k
    return "Moderate"


def _quantile(values: Sequence[float], q: float) -> Optional[float]:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    seq = sorted(values)
    idx = (len(seq) - 1) * q
    lo = int(idx)
    hi = min(lo + 1, len(seq) - 1)
    frac = idx - lo
    return seq[lo] * (1 - frac) + seq[hi] * frac


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

    return (
        f"Latest score revision ({latest_version}, {latest_scored_on}) does not expose SHAP detail. "
        "Use Gravity Score components (Brand, Proof, Proximity, Velocity, Risk) for deterministic attribution."
    )


def _tier_v1_absolute(benchmark: Optional[float]) -> str:
    if benchmark is None:
        return "Developing"
    if benchmark >= 150_000:
        return "Top-tier"
    if benchmark >= 50_000:
        return "Mid-tier"
    return "Developing"


async def _load_active_exposure_formula(db: asyncpg.Connection) -> dict[str, Any]:
    try:
        rows = await db.fetch(
            """SELECT version, proximity_weight, velocity_weight, is_active
               FROM exposure_formulas
               WHERE is_active = TRUE"""
        )
    except Exception:
        rows = []
    if len(rows) != 1:
        return {
            "version": "exposure_formula_v1",
            "proximity_weight": 0.6,
            "velocity_weight": 0.4,
        }
    row = rows[0]
    return {
        "version": str(row["version"]),
        "proximity_weight": float(row["proximity_weight"]),
        "velocity_weight": float(row["velocity_weight"]),
    }


async def _load_tier_rollout_state(
    db: asyncpg.Connection, user_id: str | None
) -> tuple[str, str]:
    phase = "phase1"
    try:
        row = await db.fetchrow(
            "SELECT current_phase FROM csc_tier_rollout LIMIT 1"
        )
        if row and row.get("current_phase"):
            phase = str(row["current_phase"])
    except Exception:
        phase = "phase1"
    if user_id:
        try:
            override = await db.fetchrow(
                """SELECT force_tier_version
                   FROM csc_tier_account_overrides
                   WHERE user_id = $1""",
                user_id,
            )
            if override and override.get("force_tier_version") in {"tier_v1", "tier_v2"}:
                return phase, str(override["force_tier_version"])
        except Exception:
            pass
    return phase, ("tier_v1" if phase in {"phase1", "phase2"} else "tier_v2")


async def _load_season_state(
    db: asyncpg.Connection, sport: str, as_of: date
) -> tuple[str, int]:
    try:
        row = await db.fetchrow(
            """SELECT state, cohort_window_days
               FROM season_states
               WHERE UPPER(sport) = UPPER($1)
                 AND start_date <= $2
                 AND end_date >= $2
               ORDER BY effective_year DESC
               LIMIT 1""",
            sport,
            as_of,
        )
    except Exception:
        row = None
    if not row:
        return "unknown", 21
    return str(row["state"]), int(row["cohort_window_days"])


def _position_group_value(athlete_row: Dict[str, Any], params: Dict[str, Any]) -> str:
    explicit = params.get("position_group")
    if explicit:
        return str(explicit).strip().upper()
    raw = _text_or_fallback(
        athlete_row.get("position_group") or derive_position_group(athlete_row.get("position")),
        "UNK",
    )
    return raw.strip().upper()


async def _fetch_cohort_rows(
    db: asyncpg.Connection,
    *,
    sport: str,
    position_group: str,
    conference: str | None,
    window_days: int,
    as_of: datetime,
) -> list[dict[str, Any]]:
    aliases = position_aliases_for_group(position_group)
    since = as_of - timedelta(days=window_days)
    conf_pred = ""
    args: list[Any] = [sport, position_group, aliases, since]
    if conference:
        conf_pred = "AND UPPER(TRIM(COALESCE(a.conference, ''))) = UPPER(TRIM($5))"
        args.append(conference)
    rows = await db.fetch(
        f"""WITH latest AS (
               SELECT DISTINCT ON (a.id)
                 a.id,
                 a.name,
                 a.position,
                 a.position_group,
                 a.conference,
                 s.gravity_score,
                 s.velocity_score,
                 s.dollar_p50_usd,
                 s.calculated_at
               FROM athletes a
               JOIN athlete_gravity_scores s ON s.athlete_id = a.id
               WHERE UPPER(TRIM(COALESCE(a.sport, ''))) = UPPER(TRIM($1))
                 AND (
                   UPPER(TRIM(COALESCE(a.position_group, ''))) = $2
                   OR UPPER(TRIM(COALESCE(a.position, ''))) = ANY($3::text[])
                   OR string_to_array(UPPER(TRIM(COALESCE(a.position, ''))), '/') && $3::text[]
                 )
                 {conf_pred}
                 AND s.calculated_at >= $4
                 AND s.gravity_score IS NOT NULL
               ORDER BY a.id, s.calculated_at DESC
             )
             SELECT * FROM latest""",
        *args,
    )
    return [dict(r) for r in rows]


def _cohort_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    benchmarks = [_first_number(r.get("dollar_p50_usd")) for r in rows]
    benchmarks = [b for b in benchmarks if b is not None]
    velocities = [_first_number(r.get("velocity_score")) for r in rows]
    velocities = [v for v in velocities if v is not None]
    return {
        "size": len(rows),
        "p10": _quantile(benchmarks, 0.10),
        "p50": _quantile(benchmarks, 0.50),
        "p90": _quantile(benchmarks, 0.90),
        "velocity_p75": _quantile(velocities, 0.75),
        "benchmark_values": benchmarks,
    }


def _percentile_rank(values: list[float], subject_value: Optional[float]) -> Optional[float]:
    if not values or subject_value is None:
        return None
    less_or_equal = sum(1 for v in values if v <= subject_value)
    return (less_or_equal / len(values)) * 100.0


def _build_market_context_text(
    *,
    conference: str,
    position_group: str,
    cohort_size: int,
    p10: Optional[float],
    p50: Optional[float],
    p90: Optional[float],
    window_days: int,
    fallback_step: int,
) -> str:
    label = f"{conference} {position_group}s (n={cohort_size})"
    if fallback_step >= 3:
        return (
            f"Market Context ({label})\n"
            f"Range: {_format_nil_value(p10)} – {_format_nil_value(p90)}\n"
            f"Based on athletes scored in the last {window_days} days (absolute methodology)."
        )
    return (
        f"Market Context ({label})\n"
        f"Range: {_format_nil_value(p10)} – {_format_nil_value(p90)}\n"
        f"Median: {_format_nil_value(p50)}\n"
        f"Based on athletes scored in the last {window_days} days"
    )


async def build_csc_report_json(
    db: asyncpg.Connection,
    athlete_id: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    user_id: str | None = None,
) -> Dict[str, Any]:
    params = params or {}
    athlete = await db.fetchrow("SELECT * FROM athletes WHERE id = $1", athlete_id)
    if not athlete:
        raise ValueError("athlete not found")
    athlete_d = dict(athlete)

    name = _text_or_fallback(athlete_d.get("name"), "Selected athlete")
    sport_f = _text_or_fallback(params.get("sport") or athlete_d.get("sport"), "CFB").upper()
    conference_f = _text_or_fallback(athlete_d.get("conference"), "Conference")
    pos_group = _position_group_value(athlete_d, params)
    n_comp = int(params.get("comparables_count") or 12)
    conf_min = float(params.get("confidence_min") or 0.75)
    report_dt = datetime.now(tz=UTC)

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
    latest_dict = dict(latest) if latest else {}
    latest_with_shap_dict = dict(latest_with_shap) if latest_with_shap else None

    gravity_score = _first_number(latest_dict.get("gravity_score"))
    brand_score = _first_number(latest_dict.get("brand_score"))
    proof_score = _first_number(latest_dict.get("proof_score"))
    proximity_score = _first_number(latest_dict.get("proximity_score"))
    velocity_score = _first_number(latest_dict.get("velocity_score"))
    risk_score = _first_number(latest_dict.get("risk_score"))
    model_confidence = _normalize_confidence(latest_dict.get("confidence"))
    athlete_model_p10 = _first_number(latest_dict.get("dollar_p10_usd"))
    athlete_model_p50 = _first_number(latest_dict.get("dollar_p50_usd"))
    athlete_model_p90 = _first_number(latest_dict.get("dollar_p90_usd"))
    athlete_raw_nil = _first_number(athlete_d.get("nil_valuation_raw"))

    exposure_formula = await _load_active_exposure_formula(db)
    exposure_score = _first_number(
        (exposure_formula["proximity_weight"] * (proximity_score or 0.0))
        + (exposure_formula["velocity_weight"] * (velocity_score or 0.0))
    )

    season_state, cohort_window_days = await _load_season_state(db, sport_f, report_dt.date())

    # Cohort fallback chain.
    cohort_fallback_step = 0
    cohort_rows = await _fetch_cohort_rows(
        db,
        sport=sport_f,
        position_group=pos_group,
        conference=conference_f,
        window_days=cohort_window_days,
        as_of=report_dt,
    )
    if len(cohort_rows) < 5:
        cohort_fallback_step = 1
        cohort_rows = await _fetch_cohort_rows(
            db,
            sport=sport_f,
            position_group=pos_group,
            conference=None,
            window_days=cohort_window_days,
            as_of=report_dt,
        )
    if len(cohort_rows) < 5:
        cohort_fallback_step = 2
        cohort_rows = await _fetch_cohort_rows(
            db,
            sport=sport_f,
            position_group=pos_group,
            conference=None,
            window_days=90,
            as_of=report_dt,
        )
    if len(cohort_rows) < 5:
        cohort_fallback_step = 3
    cohort_stats = _cohort_stats(cohort_rows)

    benchmark = _first_number(athlete_model_p50, athlete_raw_nil, cohort_stats["p50"])
    lo = _first_number(athlete_model_p10, cohort_stats["p10"])
    hi = _first_number(athlete_model_p90, cohort_stats["p90"])
    if lo is None or hi is None:
        if benchmark is not None:
            band = max(benchmark * 0.2, 25_000.0)
            lo = max(0.0, benchmark - band)
            hi = benchmark + band

    percentile_rank = (
        None
        if cohort_fallback_step >= 3
        else _percentile_rank(cohort_stats["benchmark_values"], benchmark)
    )
    scoring_history_days = None
    history_start = await db.fetchval(
        """SELECT MIN(calculated_at)
           FROM athlete_gravity_scores
           WHERE athlete_id = $1""",
        athlete_id,
    )
    if history_start:
        scoring_history_days = max(0, int((report_dt - history_start).days))

    tier_v1 = _tier_v1_absolute(benchmark)
    tier_v2 = tier_v1
    if cohort_fallback_step >= 3:
        tier_v2 = f"{tier_v1}*"
    else:
        if (
            scoring_history_days is not None
            and scoring_history_days < 60
            and velocity_score is not None
            and cohort_stats["velocity_p75"] is not None
            and velocity_score >= cohort_stats["velocity_p75"]
        ):
            tier_v2 = "Emerging"
        elif percentile_rank is not None and percentile_rank >= 75:
            tier_v2 = "Top-tier"
        elif percentile_rank is not None and percentile_rank >= 40:
            tier_v2 = "Mid-tier"
        else:
            tier_v2 = "Developing"

    rollout_phase, selected_tier_version = await _load_tier_rollout_state(db, user_id)
    tier_selected = tier_v2 if selected_tier_version == "tier_v2" else tier_v1
    if cohort_fallback_step >= 3 and not tier_selected.endswith("*"):
        tier_selected = f"{tier_selected}*"

    # Deterministic comparables.
    comp_rows = await db.fetch(
        """SELECT a.id, a.name, a.school, a.position, s.gravity_score, s.brand_score,
                  s.dollar_p50_usd, cs.similarity_score, d.deal_type, d.verified, d.deal_value,
                  dv.verified_deal_count, cs.created_at
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
           WHERE cs.subject_athlete_id = $1
             AND cs.similarity_score >= $2
           ORDER BY cs.similarity_score DESC, cs.comparable_athlete_id ASC
           LIMIT $3""",
        athlete_id,
        conf_min,
        n_comp,
    )
    comparable_sets_computed_at = None
    comparables_analysis: List[Dict[str, Any]] = []
    for c in comp_rows:
        d = dict(c)
        comp_nil = _first_number(d.get("deal_value"), d.get("dollar_p50_usd"))
        comparables_analysis.append(
            {
                "athlete_id": str(d["id"]),
                "name": d["name"],
                "school": d["school"],
                "position": d["position"],
                "gravity_score": _first_number(d.get("gravity_score")),
                "brand_score": _first_number(d.get("brand_score")),
                "nil_valuation_consensus": comp_nil,
                "nil_delta_vs_subject": (
                    float(d["gravity_score"]) - float(gravity_score)
                    if d.get("gravity_score") is not None and gravity_score is not None
                    else None
                ),
                "confidence": _normalize_confidence(d.get("similarity_score")),
                "verified_deal_count": int(d.get("verified_deal_count") or 0),
                "deal_structure": _normalize_deal_structure(d.get("deal_type")),
                "verified_source": _normalize_verified_source(d.get("verified"), comp_nil),
            }
        )
        created_at = d.get("created_at")
        if created_at and (
            comparable_sets_computed_at is None or created_at > comparable_sets_computed_at
        ):
            comparable_sets_computed_at = created_at

    comparable_state = "sufficient"
    positional_reference_rows: List[Dict[str, Any]] = []
    if len(comparables_analysis) == 0:
        comparable_state = "none"
        refs = await db.fetch(
            """SELECT a.id, a.name, a.school, a.position, s.gravity_score, s.brand_score, s.dollar_p50_usd
               FROM athletes a
               LEFT JOIN LATERAL (
                 SELECT gravity_score, brand_score, dollar_p50_usd
                 FROM athlete_gravity_scores
                 WHERE athlete_id = a.id
                 ORDER BY calculated_at DESC
                 LIMIT 1
               ) s ON true
               WHERE a.id <> $1
                 AND UPPER(TRIM(COALESCE(a.sport, ''))) = UPPER(TRIM($2))
                 AND (
                   UPPER(TRIM(COALESCE(a.position_group, ''))) = $3
                   OR UPPER(TRIM(COALESCE(a.position, ''))) = ANY($4::text[])
                   OR string_to_array(UPPER(TRIM(COALESCE(a.position, ''))), '/') && $4::text[]
                 )
                 AND s.gravity_score IS NOT NULL
               ORDER BY ABS(s.gravity_score - $5) ASC, a.id ASC
               LIMIT 3""",
            athlete_id,
            sport_f,
            pos_group,
            position_aliases_for_group(pos_group),
            gravity_score or 0.0,
        )
        for r in refs:
            rd = dict(r)
            positional_reference_rows.append(
                {
                    "athlete_id": str(rd["id"]),
                    "name": rd["name"],
                    "school": rd["school"],
                    "position": rd["position"],
                    "gravity_score": _first_number(rd.get("gravity_score")),
                    "brand_score": _first_number(rd.get("brand_score")),
                    "nil_valuation_consensus": _first_number(rd.get("dollar_p50_usd")),
                    "nil_delta_vs_subject": None,
                    "confidence": None,
                    "verified_deal_count": 0,
                    "deal_structure": "Positional Reference",
                    "verified_source": "Model Estimate",
                }
            )
    elif len(comparables_analysis) < 3:
        comparable_state = "sparse"

    confidence_level = _signal_level((model_confidence or 0.5) * 100.0)
    if comparable_state == "none":
        confidence_level = _cap_confidence(confidence_level, max_level="Low")
    if cohort_fallback_step >= 3:
        confidence_level = _cap_confidence(confidence_level, max_level="Moderate")
    risk_level = _signal_level(risk_score, invert=True)

    drivers = [
        ("Brand Strength", brand_score, False),
        ("Market Proof", proof_score, False),
        ("Exposure", exposure_score, False),
        ("Risk", risk_score, True),
    ]
    top_driver = sorted(
        drivers,
        key=lambda item: _signal_rank(item[1], invert=item[2]),
        reverse=True,
    )[0][0]
    primary_constraint = sorted(
        drivers,
        key=lambda item: _signal_rank(item[1], invert=item[2]),
    )[0][0]

    executive_parts = [
        (
            f"{name} carries a Total NIL Value Benchmark of {_format_nil_value(benchmark)} "
            f"with a recommended range of {_format_nil_value(lo)} to {_format_nil_value(hi)}."
        ),
        (
            f"In {conference_f} {pos_group}s, this profile sits around the "
            f"{'middle' if percentile_rank is None else f'{round(percentile_rank)}th percentile'} tier, "
            f"led by {top_driver.lower()}."
        ),
    ]
    if confidence_level != "High":
        executive_parts.append(
            f"Primary uncertainty is driven by {primary_constraint.lower()} and current comparable depth."
        )
    executive_summary = " ".join(executive_parts)

    key_value_drivers = [
        {
            "label": "Brand Strength",
            "signal": _signal_level(brand_score),
            "explanation": f"Brand score {_format_score(brand_score)} relative to peer benchmarks.",
        },
        {
            "label": "Market Proof",
            "signal": _signal_level(proof_score),
            "explanation": f"Proof score {_format_score(proof_score)} and verified deal activity in market.",
        },
        {
            "label": "Exposure",
            "signal": _signal_level(exposure_score),
            "explanation": (
                f"Exposure score {_format_score(exposure_score)} from "
                f"{exposure_formula['proximity_weight']:.1f}*proximity + "
                f"{exposure_formula['velocity_weight']:.1f}*velocity."
            ),
        },
        {
            "label": "Risk",
            "signal": _signal_level(risk_score, invert=True),
            "explanation": f"Risk score {_format_score(risk_score)} as the primary valuation constraint signal.",
        },
    ]

    market_context = _build_market_context_text(
        conference=conference_f,
        position_group=pos_group,
        cohort_size=cohort_stats["size"],
        p10=_first_number(cohort_stats["p10"], lo),
        p50=_first_number(cohort_stats["p50"], benchmark),
        p90=_first_number(cohort_stats["p90"], hi),
        window_days=(90 if cohort_fallback_step >= 2 else cohort_window_days),
        fallback_step=cohort_fallback_step,
    )
    if comparable_state == "none":
        validation_takeaway = (
            f"{name}'s benchmark is presented against positional cohort context; direct similarity comparables were unavailable."
        )
    elif comparable_state == "sparse":
        validation_takeaway = (
            f"{name}'s benchmark aligns with available comparables, but sparse matches reduce certainty in the band."
        )
    else:
        validation_takeaway = (
            f"{name}'s benchmark aligns with similar comparables and current cohort market context."
        )

    detail_methodology = (
        "BPXVR component model with cohort-based market context. "
        f"Season state={season_state}, cohort_window_days={90 if cohort_fallback_step >= 2 else cohort_window_days}. "
        f"Exposure formula={exposure_formula['version']} "
        f"({exposure_formula['proximity_weight']:.2f}/{exposure_formula['velocity_weight']:.2f}); "
        "tier methodology=tier_v2 with phased rollout."
    )

    return {
        "value": {
            "total_benchmark": benchmark,
            "range_low": lo,
            "range_high": hi,
            "tier_tag": tier_selected,
            "confidence_tag": f"{confidence_level} Confidence",
        },
        "explanation": {
            "executive_summary": executive_summary,
            "key_value_drivers": key_value_drivers,
            "driver_takeaway": (
                f"{top_driver} is the dominant value driver, while {primary_constraint.lower()} "
                "is the primary constraint on upside."
            ),
        },
        "validation": {
            "market_context": market_context,
            "comparable_tier": f"{tier_selected} {pos_group}s with similar signal profile.",
            "example_comparables": comparables_analysis[: n_comp],
            "takeaway": validation_takeaway,
            "comparable_state": comparable_state,
            "positional_reference_athletes": positional_reference_rows,
        },
        "confidence_risk": {
            "confidence_level": confidence_level,
            "confidence_note": (
                f"{confidence_level} confidence based on cohort quality and "
                f"{len(comparables_analysis)} similarity comparables."
            ),
            "risk_level": risk_level,
            "risk_note": f"{risk_level} risk from latest risk component score {_format_score(risk_score)}.",
        },
        "detail": {
            "shap_attribution": _build_shap_narrative(latest_dict, latest_with_shap_dict),
            "methodology": detail_methodology,
            "inputs": (
                f"Inputs: sport={sport_f}, position_group={pos_group}, conference={conference_f}, "
                f"comparables_count={n_comp}, confidence_threshold={int(conf_min * 100)}%, "
                f"report_date={report_dt.date().isoformat()}."
            ),
        },
        "metadata": {
            "tier_version": selected_tier_version,
            "tier_v1": tier_v1,
            "tier_v2": tier_v2,
            "cohort_window_days_used": (90 if cohort_fallback_step >= 2 else cohort_window_days),
            "season_state": season_state,
            "cohort_size": cohort_stats["size"],
            "cohort_fallback_step": cohort_fallback_step,
            "comparable_state": comparable_state,
            "comparable_sets_computed_at": (
                comparable_sets_computed_at.isoformat()
                if comparable_sets_computed_at
                else None
            ),
            "exposure_formula_version": exposure_formula["version"],
            "exposure_formula_weights": {
                "proximity_weight": exposure_formula["proximity_weight"],
                "velocity_weight": exposure_formula["velocity_weight"],
            },
            "rollout_phase": rollout_phase,
            "low_cohort_data": cohort_fallback_step >= 3,
            "athlete_benchmark_percentile_in_cohort": percentile_rank,
        },
    }
