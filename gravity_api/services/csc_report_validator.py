"""Post-build validator for CSC reports.

`validate_report(payload)` returns a list of `ValidationError`s; the router
treats a non-empty list as a 500 (with full error list logged internally).

Each check pins one acceptance criterion from the spec so regressions are
detected as soon as the builder produces bad output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from gravity_api.services.csc_report_prompts import FORBIDDEN_PROSE_TERMS


@dataclass(frozen=True)
class ValidationError:
    code: str
    message: str


_PLACEHOLDER_CONFERENCE_PATTERN = re.compile(r"\bconference\b", re.IGNORECASE)
_DOLLAR_LEAKY_PATTERN = re.compile(r"\$0\.0\d")


def _to_str(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def _check_placeholder_conference(payload: dict, errors: list[ValidationError]) -> None:
    metadata = payload.get("metadata") or {}
    conf = (metadata.get("conference") or "").strip()
    if not conf:
        errors.append(
            ValidationError(
                code="conference_missing",
                message="metadata.conference is empty; report cannot ship without a valid mapping.",
            )
        )
        return
    if conf.lower() == "conference":
        errors.append(
            ValidationError(
                code="conference_placeholder",
                message="metadata.conference is the placeholder 'Conference' (no team_conferences mapping).",
            )
        )


def _check_dollar_formatting(payload: dict, errors: list[ValidationError]) -> None:
    value = payload.get("value") or {}
    benchmark = value.get("total_benchmark")
    if isinstance(benchmark, (int, float)) and 0 < benchmark < 1_000_000:
        # Verify no $0.0XM formatting leaked into validation/explanation prose.
        for section in ("validation", "explanation"):
            section_data = payload.get(section) or {}
            for key, val in section_data.items():
                text = _to_str(val)
                if _DOLLAR_LEAKY_PATTERN.search(text):
                    errors.append(
                        ValidationError(
                            code="dollar_format_leak",
                            message=f"{section}.{key} contains '$0.0X' formatting for a sub-$1M value.",
                        )
                    )


def _check_percentile_cap(payload: dict, errors: list[ValidationError]) -> None:
    metadata = payload.get("metadata") or {}
    raw = metadata.get("athlete_benchmark_percentile_in_cohort")
    if isinstance(raw, (int, float)) and raw > 99:
        errors.append(
            ValidationError(
                code="percentile_uncapped",
                message=f"metadata.athlete_benchmark_percentile_in_cohort={raw} exceeds 99 cap.",
            )
        )


def _check_confidence_override_compliance(
    payload: dict, errors: list[ValidationError]
) -> None:
    metadata = payload.get("metadata") or {}
    conf = (payload.get("confidence_risk") or {}).get("confidence_level")
    if metadata.get("model_status") == "fallback" and conf != "Low":
        errors.append(
            ValidationError(
                code="fallback_high_confidence",
                message=f"model_status=fallback but confidence_level={conf} (must be Low).",
            )
        )
    if metadata.get("comparable_state") == "none" and conf not in ("Low",):
        errors.append(
            ValidationError(
                code="no_comparables_confidence_too_high",
                message=f"comparable_state=none but confidence_level={conf} (must be Low).",
            )
        )
    if (
        isinstance(metadata.get("cohort_fallback_step"), int)
        and metadata["cohort_fallback_step"] >= 2
        and conf not in ("Low",)
    ):
        errors.append(
            ValidationError(
                code="cohort_step_two_confidence_too_high",
                message=(
                    f"cohort_fallback_step={metadata['cohort_fallback_step']} but "
                    f"confidence_level={conf} (must be Low)."
                ),
            )
        )


def _check_fallback_banner_field(payload: dict, errors: list[ValidationError]) -> None:
    metadata = payload.get("metadata") or {}
    if metadata.get("model_status") == "fallback" and not metadata.get("model_version"):
        errors.append(
            ValidationError(
                code="fallback_banner_missing_version",
                message="model_status=fallback but metadata.model_version is missing.",
            )
        )


def _check_forbidden_terms_in_prose(
    payload: dict, errors: list[ValidationError]
) -> None:
    surfaces: list[tuple[str, str]] = []
    explanation = payload.get("explanation") or {}
    surfaces.append(("explanation.executive_summary", _to_str(explanation.get("executive_summary"))))
    surfaces.append(("explanation.driver_takeaway", _to_str(explanation.get("driver_takeaway"))))
    for idx, row in enumerate(explanation.get("key_value_drivers") or []):
        surfaces.append(
            (
                f"explanation.key_value_drivers[{idx}].explanation",
                _to_str((row or {}).get("explanation")),
            )
        )
    validation = payload.get("validation") or {}
    surfaces.append(("validation.takeaway", _to_str(validation.get("takeaway"))))
    cr = payload.get("confidence_risk") or {}
    surfaces.append(("confidence_risk.confidence_note", _to_str(cr.get("confidence_note"))))
    surfaces.append(("confidence_risk.risk_note", _to_str(cr.get("risk_note"))))
    for surface_name, text in surfaces:
        lowered = text.lower()
        for term in FORBIDDEN_PROSE_TERMS:
            if term.lower() in lowered:
                errors.append(
                    ValidationError(
                        code="forbidden_term_in_prose",
                        message=f"{surface_name} contains forbidden term '{term}'.",
                    )
                )


def _check_report_id_present(payload: dict, errors: list[ValidationError]) -> None:
    metadata = payload.get("metadata") or {}
    if not metadata.get("report_id"):
        errors.append(
            ValidationError(
                code="report_id_missing",
                message="metadata.report_id is missing; every report must carry a deterministic id.",
            )
        )


def _check_tier_methodology_consistency(
    payload: dict, errors: list[ValidationError]
) -> None:
    metadata = payload.get("metadata") or {}
    value = payload.get("value") or {}
    tier_tag = _to_str(value.get("tier_tag"))
    tier_version = metadata.get("tier_version")
    # tier_v1 (absolute) tag must NOT end with "*"; tier_v2 may.
    if tier_version == "tier_v1" and tier_tag.endswith("*"):
        errors.append(
            ValidationError(
                code="tier_version_mismatch",
                message="metadata.tier_version=tier_v1 but value.tier_tag carries '*' suffix.",
            )
        )


def validate_report(payload: dict) -> list[ValidationError]:
    """Return a list of structured validation errors for the given report."""
    errors: list[ValidationError] = []
    if not isinstance(payload, dict):
        return [ValidationError(code="invalid_payload", message="report payload is not a mapping")]
    _check_placeholder_conference(payload, errors)
    _check_dollar_formatting(payload, errors)
    _check_percentile_cap(payload, errors)
    _check_confidence_override_compliance(payload, errors)
    _check_fallback_banner_field(payload, errors)
    _check_forbidden_terms_in_prose(payload, errors)
    _check_report_id_present(payload, errors)
    _check_tier_methodology_consistency(payload, errors)
    return errors
