"""JSON CSC report builder for the terminal."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

import asyncpg

from gravity_api.services.csc_report_llm import (
    generate_confidence_rationale,
    generate_driver_explanation,
    generate_executive_summary,
    generate_risk_rationale,
    generate_value_interpretation,
)
from gravity_api.services.csc_report_rollout import (
    ReportRolloutState,
    load_report_rollout_state,
)
from gravity_api.services.model_health import classify_model_version
from gravity_api.services.position_group_match import derive_position_group, position_aliases_for_group
from gravity_api.services.team_conferences import (
    ConferenceNotMappedError,
    try_get_conference,
)


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


def compute_final_confidence(
    base: str,
    *,
    cohort_fallback_step: int,
    comparable_state: str,
    model_status: str,
    cohort_fit: str | None = None,
) -> str:
    """Apply the spec's forced override chain.

    Lowest result wins; the order below is the canonical execution order
    documented in the CSC v3 spec.
    """
    levels = ("Low", "Moderate", "High")
    if base not in levels:
        base = "Moderate"
    if model_status == "fallback":
        # Hard cap — a fallback scorer cannot back a binding deal.
        return "Low"
    final = base
    if cohort_fallback_step >= 2:
        final = _cap_confidence(final, max_level="Low")
    elif cohort_fallback_step >= 1:
        final = _cap_confidence(final, max_level="Moderate")
    if comparable_state == "none":
        final = _cap_confidence(final, max_level="Low")
    elif comparable_state == "sparse":
        final = _cap_confidence(final, max_level="Moderate")
    if cohort_fit == "poor":
        final = _cap_confidence(final, max_level="Moderate")
    return final


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


async def _fetch_outlier_cohort_rows(
    db: asyncpg.Connection,
    *,
    sport: str,
    position_group: str,
    conference_tier: str | None,
    window_days: int,
    as_of: datetime,
    benchmark_floor: float,
) -> list[dict[str, Any]]:
    """Outlier-aware cohort fetch.

    Returns athletes whose `dollar_p50_usd >= benchmark_floor` within
    `(sport, position_group, conference_tier)`. Used when the standard
    fallback cohort has poor fit because the subject athlete sits far
    outside the broader cohort distribution.
    """
    aliases = position_aliases_for_group(position_group)
    since = as_of - timedelta(days=window_days)
    tier_pred = ""
    args: list[Any] = [sport, position_group, aliases, since, float(benchmark_floor)]
    if conference_tier:
        tier_pred = """AND EXISTS (
                  SELECT 1 FROM team_conferences tc
                  WHERE UPPER(TRIM(tc.team_id)) = UPPER(TRIM(a.school))
                    AND tc.sport = LOWER($1)
                    AND tc.conference_tier = $6
                    AND tc.effective_from <= CURRENT_DATE
                    AND (tc.effective_to IS NULL OR tc.effective_to >= CURRENT_DATE)
                )"""
        args.append(conference_tier)
    rows = await db.fetch(
        f"""WITH latest AS (
               SELECT DISTINCT ON (a.id)
                 a.id,
                 a.name,
                 a.position,
                 a.position_group,
                 a.conference,
                 a.school,
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
                 AND s.calculated_at >= $4
                 AND s.gravity_score IS NOT NULL
                 AND s.dollar_p50_usd IS NOT NULL
                 AND s.dollar_p50_usd >= $5
                 {tier_pred}
               ORDER BY a.id, s.calculated_at DESC
             )
             SELECT * FROM latest""",
        *args,
    )
    return [dict(r) for r in rows]


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
        "p25": _quantile(benchmarks, 0.25),
        "p50": _quantile(benchmarks, 0.50),
        "p75": _quantile(benchmarks, 0.75),
        "p90": _quantile(benchmarks, 0.90),
        "velocity_p75": _quantile(velocities, 0.75),
        "benchmark_values": benchmarks,
    }


def _percentile_rank(values: list[float], subject_value: Optional[float]) -> Optional[float]:
    if not values or subject_value is None:
        return None
    less_or_equal = sum(1 for v in values if v <= subject_value)
    return (less_or_equal / len(values)) * 100.0


def classify_cohort_fit(
    athlete_benchmark: Optional[float],
    cohort_stats: dict[str, Any],
) -> str:
    """Spec-exact cohort-fit classification: good / edge / poor.

    `poor` is returned when the cohort is too small to be informative or
    when the athlete sits more than 2x above P90 (or below half of P10).
    `edge` flags athletes near the tails. Everything else is `good`.
    """
    if cohort_stats.get("size", 0) < 5:
        return "poor"
    if athlete_benchmark is None:
        return "good"
    p10 = cohort_stats.get("p10")
    p90 = cohort_stats.get("p90")
    if p10 is None or p90 is None:
        return "poor"
    if athlete_benchmark > p90 * 2 or athlete_benchmark < p10 * 0.5:
        return "poor"
    if athlete_benchmark > p90 or athlete_benchmark < p10:
        return "edge"
    return "good"


def _build_detail_blocks(
    *,
    latest_dict: dict[str, Any],
    latest_with_shap_dict: dict[str, Any] | None,
    sport: str,
    position_group: str,
    conference: str,
    conference_tier: str | None,
    season_state: str,
    cohort_window_days: int,
    cohort_fallback_step: int,
    cohort_size: int,
    exposure_formula: dict[str, Any],
    comparable_state: str,
    comparable_sets_computed_at: Any,
    rollout_phase: str,
    tier_version: str,
    report_id: str,
    model_version: Any,
    model_status: str,
) -> dict[str, Any]:
    """Assemble the nested Methodology/Cohort/Comparables/Provenance/SHAP blocks."""
    shap_rows: list[dict[str, Any]] = []
    shap_source: dict[str, Any] | None = None
    if isinstance(latest_with_shap_dict, dict):
        shap_source = latest_with_shap_dict
    elif isinstance(latest_dict.get("shap_values"), dict):
        shap_source = {"shap_values": latest_dict.get("shap_values")}
    if shap_source:
        shap_obj = shap_source.get("shap_values")
        if isinstance(shap_obj, dict):
            for feature, value in sorted(
                shap_obj.items(),
                key=lambda kv: abs(_first_number(kv[1]) or 0.0),
                reverse=True,
            )[:8]:
                num = _first_number(value)
                if num is None:
                    continue
                shap_rows.append(
                    {
                        "feature": str(feature),
                        "contribution": float(num),
                    }
                )
    return {
        "methodology": {
            "title": "Methodology",
            "summary": (
                "Component-based valuation model with cohort-relative market context."
            ),
            "components": [
                "Brand Strength — branded reach and audience alignment.",
                "Market Proof — verified deal density and pricing.",
                "Exposure — proximity to high-leverage moments + recent velocity.",
                "Risk — operational, eligibility, and stability factors.",
            ],
            "tier_methodology_version": tier_version,
        },
        "cohort": {
            "title": "Cohort",
            "sport": sport,
            "position_group": position_group,
            "conference": conference,
            "conference_tier": conference_tier,
            "size": cohort_size,
            "window_days": cohort_window_days,
            "season_state": season_state,
            "fallback_step": cohort_fallback_step,
        },
        "comparables": {
            "title": "Comparables",
            "state": comparable_state,
            "computed_at": (
                comparable_sets_computed_at.isoformat()
                if comparable_sets_computed_at
                else None
            ),
        },
        "provenance": {
            "title": "Provenance",
            "report_id": report_id,
            "rollout_phase": rollout_phase,
            "tier_version": tier_version,
            "exposure_formula_version": exposure_formula["version"],
            "model_version": str(model_version) if model_version is not None else None,
            "model_status": model_status,
        },
        "shap_attribution": {
            "title": "SHAP Attribution",
            "rows": shap_rows,
            "narrative": _build_shap_narrative(latest_dict, latest_with_shap_dict),
        },
    }


def _athlete_initials(name: str | None) -> str:
    """Up-to-3-letter initials from athlete name, uppercased.

    Falls back to "ATH" when the name has no parseable initials so report
    IDs are always emittable even for partially-populated rows.
    """
    if not name:
        return "ATH"
    parts = [p for p in str(name).strip().split() if p]
    letters = "".join(p[0].upper() for p in parts if p[0].isalpha())[:3]
    return letters or "ATH"


async def _allocate_report_id(
    db: asyncpg.Connection,
    *,
    report_date: date,
    initials: str,
) -> str:
    """Allocate the next deterministic report id for (date, initials).

    Returns YYYY-MM-DD-INITIALS-NNN. Atomically increments
    `csc_report_sequence.next_seq`; falls back to a timestamp-based ID if
    the sequence table is missing (e.g. fresh dev DB without migration).
    """
    try:
        row = await db.fetchrow(
            """INSERT INTO csc_report_sequence (report_date, athlete_initials, next_seq)
               VALUES ($1, $2, 1)
               ON CONFLICT (report_date, athlete_initials)
               DO UPDATE SET next_seq = csc_report_sequence.next_seq + 1
               RETURNING next_seq""",
            report_date,
            initials,
        )
        if row and row.get("next_seq") is not None:
            return f"{report_date.isoformat()}-{initials}-{int(row['next_seq']):03d}"
    except Exception:
        # Sequence table not present (or read-only DB during preview).
        # Falls through to deterministic timestamp suffix below.
        pass
    return f"{report_date.isoformat()}-{initials}-001"


def validate_range(
    benchmark: Optional[float],
    p10: Optional[float],
    p90: Optional[float],
    *,
    p25: Optional[float] = None,
    p75: Optional[float] = None,
) -> tuple[Optional[float], Optional[float], str]:
    """Sanity-check the displayed range; fall back to P25/P75 when too wide.

    The spec defines `range_quality = "wide"` when (p90 - p10) > benchmark.
    When wide, we collapse to the interquartile band (P25/P75) if available
    so the report doesn't surface a band wider than the central estimate.
    """
    if benchmark is None or p10 is None or p90 is None:
        return p10, p90, "normal"
    spread = max(0.0, p90 - p10)
    if benchmark <= 0:
        return p10, p90, "normal"
    if spread <= benchmark:
        return p10, p90, "normal"
    if p25 is not None and p75 is not None:
        return p25, p75, "wide"
    # No interquartile fallback available: tighten symmetrically around
    # the benchmark to a +/- 30% band so the report still ships a band
    # that fits the spec's "narrower than benchmark" expectation.
    band = benchmark * 0.30
    return max(0.0, benchmark - band), benchmark + band, "wide"


def cap_displayed_percentile(
    raw_percentile: Optional[float],
    *,
    cohort_size: int,
) -> tuple[Optional[float], Optional[str]]:
    """Cap displayed percentile at 99 per spec.

    Returns `(displayed_value, override_text)`. `override_text` is set
    when the raw rank was 100 — in that case the report should render
    "Highest of N" rather than a numeric percentile.
    """
    if raw_percentile is None:
        return None, None
    if raw_percentile >= 100:
        return 99.0, f"Highest of {cohort_size} cohort athletes"
    if raw_percentile <= 1:
        return 1.0, None
    return raw_percentile, None


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
    cohort_fit: str = "good",
) -> str:
    label = f"{conference} {position_group}s (n={cohort_size})"
    if cohort_fit == "poor":
        # The athlete's benchmark is outside the cohort distribution; the
        # spec mandates that percentile and median be suppressed in favor
        # of an explicit "exceeds peer cohort distribution" framing.
        return (
            f"Peer Reference ({label})\n"
            "Athlete's valuation exceeds the peer cohort distribution. "
            "Standard percentile statistics are not applicable; refer to the "
            "Comparable Athletes section for peer reference.\n"
            f"Based on athletes scored in the last {window_days} days"
        )
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
    """Assemble a CSC v3 report.

    Pipeline phases (in execution order):
      1. INPUT VALIDATION   — required identifiers, parameter normalization.
      2. DATA HYDRATION     — athlete row, latest score, conference, cohort, exposure formula, comparables.
      3. DERIVED FIELDS     — benchmark, range, percentile, cohort_fit, tier, exposure score, drivers.
      4. LLM GENERATION     — executive summary, driver explanations, validation takeaway, confidence/risk notes.
      5. RENDER             — assemble Pydantic-shaped payload (value / explanation / validation / confidence_risk / detail).
      6. PERSIST            — allocate report_id (persisted only at router layer).
      7. RETURN             — stamp metadata + return.
    """
    # ---------------- PHASE 1: INPUT VALIDATION ----------------
    params = params or {}
    athlete = await db.fetchrow("SELECT * FROM athletes WHERE id = $1", athlete_id)
    if not athlete:
        raise ValueError("athlete not found")
    athlete_d = dict(athlete)

    report_dt = datetime.now(tz=UTC)
    name = _text_or_fallback(athlete_d.get("name"), "Selected athlete")
    sport_f = _text_or_fallback(params.get("sport") or athlete_d.get("sport"), "CFB").upper()
    # Conference and conference tier come from `team_conferences` (sourced via
    # the athlete's school). A missing mapping raises ConferenceNotMappedError
    # so the router can return HTTP 422 — never silently degrade to placeholder.
    school_text = _text_or_fallback(athlete_d.get("school"), "")
    conference_lookup = (
        await try_get_conference(db, school_text, sport_f, as_of=report_dt.date())
        if school_text
        else None
    )
    conference_mapping_status = "mapped"
    if conference_lookup is None:
        # Fallback chain when team_conferences has no entry for this school:
        #   1. Use the athlete row's stored conference (e.g. "Big 12").
        #   2. Use the school name itself as a display label.
        #   3. Use "Independent" as a last resort.
        # In all cases we stamp metadata.conference_mapping_status so ops
        # can backfill team_conferences for this school. We never 422 a
        # report on missing mapping alone — the cohort fallback chain
        # already handles the broader cohort definition.
        stored_conf = (athlete_d.get("conference") or "").strip()
        if stored_conf and stored_conf.lower() != "conference":
            conference_f = stored_conf
            conference_mapping_status = "stored_fallback"
        elif school_text:
            conference_f = school_text
            conference_mapping_status = "school_fallback"
        else:
            conference_f = "Independent"
            conference_mapping_status = "unmapped"
        conference_tier: str | None = None
    else:
        conference_f = conference_lookup.conference
        conference_tier = conference_lookup.conference_tier
    pos_group = _position_group_value(athlete_d, params)
    n_comp = int(params.get("comparables_count") or 12)
    conf_min = float(params.get("confidence_min") or 0.75)

    # ---------------- PHASE 2: DATA HYDRATION ----------------
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

    # Model status: classify the version of the latest score row. A
    # `fallback` value flips the per-report 503 gate in the router and
    # forces a hard Low confidence cap downstream.
    latest_model_version = latest_dict.get("model_version")
    model_status_classification = classify_model_version(latest_model_version)
    # Treat 'unknown' as production so reports still render in environments
    # where the model_version column is sparse. Per-report enforcement only
    # blocks confirmed `fallback` rows.
    model_status: str = (
        "fallback" if model_status_classification == "fallback" else "production"
    )

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

    # ---------------- PHASE 3: DERIVED FIELDS ----------------
    benchmark = _first_number(athlete_model_p50, athlete_raw_nil, cohort_stats["p50"])
    raw_lo = _first_number(athlete_model_p10, cohort_stats["p10"])
    raw_hi = _first_number(athlete_model_p90, cohort_stats["p90"])
    if raw_lo is None or raw_hi is None:
        if benchmark is not None:
            band = max(benchmark * 0.2, 25_000.0)
            raw_lo = max(0.0, benchmark - band) if raw_lo is None else raw_lo
            raw_hi = benchmark + band if raw_hi is None else raw_hi

    # Range sanity: when the model-derived P10/P90 band is wider than the
    # benchmark itself, fall back to the interquartile band (P25/P75) so
    # the report doesn't surface an actionable-looking range that isn't.
    lo, hi, range_quality = validate_range(
        benchmark,
        raw_lo,
        raw_hi,
        p25=_first_number(cohort_stats.get("p25")),
        p75=_first_number(cohort_stats.get("p75")),
    )

    raw_percentile_rank = (
        None
        if cohort_fallback_step >= 3
        else _percentile_rank(cohort_stats["benchmark_values"], benchmark)
    )
    percentile_rank, percentile_override_text = cap_displayed_percentile(
        raw_percentile_rank, cohort_size=cohort_stats["size"]
    )
    # Cohort fit classifies how informative the cohort is for this athlete.
    # `poor` triggers percentile suppression and forces confidence ≤ Moderate.
    cohort_fit_label = classify_cohort_fit(benchmark, cohort_stats)
    if cohort_fit_label == "poor":
        # Step 4: outlier-aware retry — pull athletes >= 50% of cohort median
        # within the same (sport, position_group, conference_tier) to build a
        # peer-tier reference instead of the diluted full cohort.
        if (
            cohort_fallback_step < 4
            and conference_tier
            and benchmark is not None
            and cohort_stats.get("p50") is not None
        ):
            try:
                outlier_rows = await _fetch_outlier_cohort_rows(
                    db,
                    sport=sport_f,
                    position_group=pos_group,
                    conference_tier=conference_tier,
                    window_days=90,
                    as_of=report_dt,
                    benchmark_floor=float(cohort_stats["p50"]) * 0.5,
                )
            except asyncpg.PostgresError:
                # team_conferences referenced by the outlier query may not
                # exist in this env; skip the step instead of failing.
                outlier_rows = []
            if len(outlier_rows) >= 5:
                cohort_fallback_step = 4
                cohort_rows = outlier_rows
                cohort_stats = _cohort_stats(cohort_rows)
                raw_percentile_rank = _percentile_rank(
                    cohort_stats["benchmark_values"], benchmark
                )
                percentile_rank, percentile_override_text = cap_displayed_percentile(
                    raw_percentile_rank, cohort_size=cohort_stats["size"]
                )
                cohort_fit_label = classify_cohort_fit(benchmark, cohort_stats)
        if cohort_fit_label == "poor":
            percentile_rank = None
            percentile_override_text = None
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
    report_rollout = await load_report_rollout_state(db, user_id)
    # The displayed tier tag must equal the methodology stamped in
    # metadata.tier_version. tier_v1 is the absolute-dollar methodology and
    # never carries the "*" footnote; tier_v2 already includes "*" when
    # cohort fallback step >= 3 (set above).
    if selected_tier_version == "tier_v2":
        tier_selected = tier_v2
    else:
        tier_selected = tier_v1

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

    base_confidence = _signal_level((model_confidence or 0.5) * 100.0)
    confidence_level = compute_final_confidence(
        base_confidence,
        cohort_fallback_step=cohort_fallback_step,
        comparable_state=comparable_state,
        model_status=model_status,
        cohort_fit=cohort_fit_label,
    )
    if range_quality == "wide":
        # Wide range → force ≤ Moderate confidence per spec.
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

    # ---------------- PHASE 4: LLM GENERATION ----------------
    benchmark_text = _format_nil_value(benchmark)
    range_text = (
        f"{_format_nil_value(lo)} to {_format_nil_value(hi)}"
        if lo is not None and hi is not None
        else "an estimated reference band"
    )
    percentile_text = (
        "the middle tier"
        if percentile_rank is None
        else f"the {round(percentile_rank)}th percentile of the cohort"
    )

    # Deterministic fallback prose (cleaned to satisfy validator: no
    # decimals, no formula constants, no system internals).
    fallback_executive_parts = [
        (
            f"{name} carries a Total NIL Value Benchmark of {benchmark_text} "
            f"with a recommended range of {range_text}."
        ),
        (
            f"In {conference_f} {pos_group}s, this profile sits in {percentile_text}, "
            f"led by {top_driver.lower()}."
        ),
        f"The benchmark reflects current cohort positioning and verified market activity.",
    ]
    if confidence_level != "High":
        fallback_executive_parts.append(
            f"Primary uncertainty is driven by {primary_constraint.lower()} and current comparable depth."
        )
    fallback_executive_summary = " ".join(fallback_executive_parts)

    cohort_label = f"{conference_f} {pos_group}s"
    uncertainty_note = (
        "None"
        if confidence_level == "High"
        else f"Primary uncertainty: {primary_constraint.lower()}."
    )
    executive_result = await generate_executive_summary(
        athlete_name=name,
        benchmark_text=benchmark_text,
        range_text=range_text,
        cohort_label=cohort_label,
        tier_tag=tier_selected,
        confidence_tag=f"{confidence_level} Confidence",
        dominant_driver=top_driver,
        uncertainty_note=uncertainty_note,
        fallback=fallback_executive_summary,
    )
    executive_summary = executive_result.text

    # Deterministic per-driver fallback prose — qualitative, no decimals, no
    # formula constants per the prompt's forbidden-term list.
    def _driver_fallback(label: str, signal: str) -> str:
        verb = {"High": "leads", "Moderate": "holds steady against", "Low": "lags"}.get(
            signal, "tracks"
        )
        return f"{label} {verb} the {cohort_label} cohort."

    raw_driver_rows = [
        ("Brand Strength", _signal_level(brand_score)),
        ("Market Proof", _signal_level(proof_score)),
        ("Exposure", _signal_level(exposure_score)),
        ("Risk", _signal_level(risk_score, invert=True)),
    ]
    key_value_drivers: list[dict[str, Any]] = []
    for label, signal in raw_driver_rows:
        fallback = _driver_fallback(label, signal)
        driver_result = await generate_driver_explanation(
            athlete_name=name,
            driver_label=label,
            signal_level=signal,
            position_group=pos_group,
            cohort_label=cohort_label,
            fallback=fallback,
        )
        key_value_drivers.append(
            {
                "label": label,
                "signal": signal,
                "explanation": driver_result.text,
            }
        )

    market_context = _build_market_context_text(
        conference=conference_f,
        position_group=pos_group,
        cohort_size=cohort_stats["size"],
        p10=_first_number(cohort_stats["p10"], lo),
        p50=_first_number(cohort_stats["p50"], benchmark),
        p90=_first_number(cohort_stats["p90"], hi),
        window_days=(90 if cohort_fallback_step >= 2 else cohort_window_days),
        fallback_step=cohort_fallback_step,
        cohort_fit=cohort_fit_label,
    )
    if percentile_override_text:
        # Suffix the override text so consumers see "Highest of N" instead of
        # a numeric percentile when the athlete is at the top of the cohort.
        market_context = f"{market_context}\n{percentile_override_text}"
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

    # ---------------- PHASE 6: PERSIST (report id allocation) ----------------
    report_id = await _allocate_report_id(
        db,
        report_date=report_dt.date(),
        initials=_athlete_initials(name),
    )

    # Validation takeaway via LLM with deterministic fallback.
    comparables_summary = (
        f"{len(comparables_analysis)} comparable athletes"
        if comparable_state != "none"
        else "No direct comparables available; using positional reference athletes"
    )
    interpretation_result = await generate_value_interpretation(
        athlete_name=name,
        market_context=market_context.replace("\n", " "),
        comparables_summary=comparables_summary,
        benchmark_text=benchmark_text,
        percentile_text=percentile_text,
        fallback=validation_takeaway,
    )
    validation_takeaway = interpretation_result.text

    # Confidence + risk rationale via LLM with deterministic fallback.
    confidence_causes_parts: list[str] = []
    if model_status == "fallback":
        confidence_causes_parts.append("the scoring service is on a fallback model")
    if comparable_state == "none":
        confidence_causes_parts.append("no direct comparables were available")
    elif comparable_state == "sparse":
        confidence_causes_parts.append("comparable athlete depth is limited")
    if cohort_fallback_step >= 2:
        confidence_causes_parts.append("cohort data is sparse for this athlete")
    if cohort_fit_label == "poor":
        confidence_causes_parts.append("the athlete sits outside the typical peer cohort")
    if range_quality == "wide":
        confidence_causes_parts.append("the value range is wider than the benchmark")
    if not confidence_causes_parts:
        confidence_causes_parts.append("cohort quality and comparable depth are adequate")
    confidence_causes = "; ".join(confidence_causes_parts)
    fallback_confidence_note = (
        f"{confidence_level} confidence: {confidence_causes_parts[0]}."
    )
    confidence_result = await generate_confidence_rationale(
        athlete_name=name,
        confidence_level=confidence_level,
        causes=confidence_causes,
        fallback=fallback_confidence_note,
    )

    risk_factors = primary_constraint.lower() if confidence_level != "High" else "none material"
    fallback_risk_note = (
        f"{risk_level} risk: driven by {risk_factors}."
    )
    risk_result = await generate_risk_rationale(
        athlete_name=name,
        risk_level=risk_level,
        position_group=pos_group,
        risk_factors=risk_factors,
        fallback=fallback_risk_note,
    )

    detail_methodology = (
        "Component-based valuation model with cohort-relative market context. "
        f"Season state={season_state}, cohort window={90 if cohort_fallback_step >= 2 else cohort_window_days} days. "
        f"Exposure formula version={exposure_formula['version']}; "
        "tier methodology=tier_v2 with phased rollout."
    )

    # ---------------- PHASE 5+7: RENDER + RETURN ----------------
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
            "confidence_note": confidence_result.text,
            "risk_level": risk_level,
            "risk_note": risk_result.text,
        },
        "detail": {
            "shap_attribution": _build_shap_narrative(latest_dict, latest_with_shap_dict),
            "methodology": detail_methodology,
            "inputs": (
                f"Inputs: sport={sport_f}, position_group={pos_group}, conference={conference_f}, "
                f"comparables_count={n_comp}, confidence_threshold={int(conf_min * 100)}%, "
                f"report_date={report_dt.date().isoformat()}."
            ),
            "blocks": _build_detail_blocks(
                latest_dict=latest_dict,
                latest_with_shap_dict=latest_with_shap_dict,
                sport=sport_f,
                position_group=pos_group,
                conference=conference_f,
                conference_tier=conference_tier,
                season_state=season_state,
                cohort_window_days=(90 if cohort_fallback_step >= 2 else cohort_window_days),
                cohort_fallback_step=cohort_fallback_step,
                cohort_size=cohort_stats["size"],
                exposure_formula=exposure_formula,
                comparable_state=comparable_state,
                comparable_sets_computed_at=comparable_sets_computed_at,
                rollout_phase=rollout_phase,
                tier_version=selected_tier_version,
                report_id=report_id,
                model_version=latest_model_version,
                model_status=model_status,
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
            "conference": conference_f,
            "conference_tier": conference_tier,
            "conference_mapping_status": conference_mapping_status,
            "model_status": model_status,
            "model_version": (
                str(latest_model_version) if latest_model_version is not None else None
            ),
            "cohort_fit": cohort_fit_label,
            "range_quality": range_quality,
            "report_id": report_id,
            "report_version": report_rollout.version,
            "report_rollout_phase": report_rollout.phase,
        },
    }
