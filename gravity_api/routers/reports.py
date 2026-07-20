"""Deal valuation reports, CSC JSON, brand match."""

import json
import logging
import os
import uuid
from typing import Any, Dict, List, Literal, Optional

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from gravity_api.auth_deps import optional_user_id, require_user_id
from gravity_api.config import get_settings
from gravity_api.database import get_db
from gravity_api.services.brand_match import BrandMatchBriefData, run_brand_match
from gravity_api.services.csc_report_builder import build_csc_report_json
from gravity_api.services.csc_report_validator import blocking_errors, validate_report
from gravity_api.services.team_conferences import ConferenceNotMappedError

logger = logging.getLogger(__name__)


def _admin_override_active(
    admin_key: str | None,
) -> bool:
    """Whether the caller presented the internal admin key for fallback override."""
    settings = get_settings()
    expected = (settings.internal_api_key or "").strip()
    if not expected:
        return False
    return bool(admin_key and admin_key.strip() == expected)


def _block_fallback_reports() -> bool:
    """Hard-block CSC reports when the ML scorer is on fallback.

    Off by default — the fallback model still produces commercially useful
    estimates and every report carries an unmistakable banner. Operators
    can enable hard blocking by setting CSC_BLOCK_FALLBACK to a truthy
    value when they need stricter governance.
    """
    raw = (os.environ.get("CSC_BLOCK_FALLBACK") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


router = APIRouter()


@router.get("")
@router.get("/", include_in_schema=False)
async def list_reports(
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    """List the most recent deal valuation reports for the authenticated user."""
    rows = await db.fetch(
        """SELECT id, report_uuid, athlete_id, status, created_at
           FROM deal_valuation_reports
           WHERE user_id = $1
           ORDER BY created_at DESC
           LIMIT 50""",
        user_id,
    )
    return {"reports": [dict(r) for r in rows]}


class CreateReportBody(BaseModel):
    athlete_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


@router.post("")
@router.post("/", include_in_schema=False)
async def create_report(
    body: CreateReportBody,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
    allow_fallback: bool = Query(False),
    x_gravity_admin_key: str | None = Header(default=None, alias="X-Gravity-Admin-Key"),
):
    """Create a deal valuation report row tied to the authenticated user.

    Builds the CSC JSON synchronously (same data the terminal uses for
    its preview) and persists it with status=ready. Caller receives the
    report id + uuid so they can fetch or share it later.
    """
    try:
        athlete_uuid = uuid.UUID(body.athlete_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid athlete_id") from e

    exists = await db.fetchval(
        "SELECT 1 FROM athletes WHERE id = $1", athlete_uuid
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Athlete not found")

    try:
        report_json = await build_csc_report_json(
            db,
            str(athlete_uuid),
            body.parameters,
            user_id=str(user_id),
        )
    except ConferenceNotMappedError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Athlete's team is missing conference mapping; cannot generate report ({e.team_id})",
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    metadata = report_json.get("metadata") if isinstance(report_json, dict) else None
    if isinstance(metadata, dict) and metadata.get("model_status") == "fallback":
        if _block_fallback_reports() and not (
            allow_fallback and _admin_override_active(x_gravity_admin_key)
        ):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Fallback scorer active; refusing to persist binding report. "
                    "Contact admin to override."
                ),
            )
        logger.warning(
            "Persisting CSC report with fallback banner: athlete=%s model_version=%s",
            athlete_uuid,
            metadata.get("model_version"),
        )

    report_uuid = str(uuid.uuid4())
    row = await db.fetchrow(
        """INSERT INTO deal_valuation_reports
                (user_id, athlete_id, report_uuid, status, parameters, report_json)
           VALUES ($1, $2, $3, 'ready', $4::jsonb, $5::jsonb)
           RETURNING id, report_uuid, athlete_id, status, created_at""",
        user_id,
        athlete_uuid,
        report_uuid,
        json.dumps(body.parameters or {}),
        json.dumps(report_json),
    )
    return {
        "id": str(row["id"]),
        "report_uuid": str(row["report_uuid"]),
        "athlete_id": str(row["athlete_id"]),
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "report": report_json,
    }


class BrandProfileIn(BaseModel):
    """Brand-side scores used to score athletes against the brand brief.

    All values are 0–100. Defaults are conservative midpoints; brands
    that have a Gravity-curated brand profile should pass their actual
    values here instead of relying on defaults.
    """

    reach_score: float = Field(72.0, ge=0.0, le=100.0)
    value_score: float = Field(68.0, ge=0.0, le=100.0)
    fit_score: float = Field(70.0, ge=0.0, le=100.0)
    authenticity_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    stability_score: Optional[float] = Field(None, ge=0.0, le=100.0)


class BrandMatchBriefIn(BaseModel):
    budget: float
    category: str = ""
    geography: List[str] = Field(default_factory=list)
    audience: List[str] = Field(default_factory=list)
    risk_tolerance: float = 0.5
    max_transfer_risk: bool = False
    authenticity_weight: float = 0.6
    # Optional brand profile — when omitted, we derive sensible values
    # from the brief's risk_tolerance / authenticity_weight so the API
    # is still useful for callers that don't have a curated profile yet.
    brand_profile: Optional[BrandProfileIn] = None
    min_social_reach: Optional[float] = None
    prioritize_engagement: bool = False
    excluded_categories: List[str] = Field(default_factory=list)
    deal_density_preference: str = "any"
    sports: List[str] = Field(default_factory=list)


class CscValueOut(BaseModel):
    total_benchmark: float | None = None
    range_low: float | None = None
    range_high: float | None = None
    annual_nil_benchmark: float | None = None
    activation_deal_low: float | None = None
    activation_deal_mid: float | None = None
    activation_deal_high: float | None = None
    season_partnership_low: float | None = None
    season_partnership_high: float | None = None
    deal_confidence: str | None = None
    deal_uncertainty: str | None = None
    deal_pricing_method: str | None = None
    deal_pricing_basis: str | None = None
    tier_tag: str | None = None
    confidence_tag: str | None = None


class CscKeyDriverOut(BaseModel):
    label: str
    signal: Literal["High", "Moderate", "Low"]
    explanation: str


class CscComparableOut(BaseModel):
    athlete_id: str
    name: str
    school: str | None = None
    position: str | None = None
    gravity_score: float | None = None
    brand_score: float | None = None
    nil_valuation_consensus: float | None = None
    nil_delta_vs_subject: float | None = None
    confidence: float | None = None
    verified_deal_count: int | None = None
    deal_structure: str | None = None
    verified_source: str | None = None


class CscExplanationOut(BaseModel):
    executive_summary: str
    key_value_drivers: List[CscKeyDriverOut]
    driver_takeaway: str


class CscValidationOut(BaseModel):
    market_context: str
    comparable_tier: str
    example_comparables: List[CscComparableOut]
    takeaway: str
    comparable_state: Literal["sufficient", "sparse", "none"]
    positional_reference_athletes: List[CscComparableOut]


class CscConfidenceRiskOut(BaseModel):
    confidence_level: Literal["High", "Moderate", "Low"]
    confidence_note: str
    risk_level: Literal["High", "Moderate", "Low"]
    risk_note: str


class CscMethodologyBlock(BaseModel):
    title: str = "Methodology"
    summary: str
    components: List[str] = Field(default_factory=list)
    tier_methodology_version: str | None = None


class CscCohortBlock(BaseModel):
    title: str = "Cohort"
    sport: str
    position_group: str
    conference: str | None = None
    conference_tier: str | None = None
    size: int = 0
    window_days: int = 0
    season_state: str | None = None
    fallback_step: int = 0


class CscComparablesBlock(BaseModel):
    title: str = "Comparables"
    state: Literal["sufficient", "sparse", "none"]
    computed_at: str | None = None


class CscProvenanceBlock(BaseModel):
    title: str = "Provenance"
    report_id: str
    rollout_phase: str
    tier_version: str
    exposure_formula_version: str
    model_version: str | None = None
    model_status: Literal["production", "fallback"] | None = None


class CscShapRow(BaseModel):
    feature: str
    contribution: float


class CscShapTable(BaseModel):
    title: str = "SHAP Attribution"
    rows: List[CscShapRow] = Field(default_factory=list)
    narrative: str | None = None


class CscDetailBlocks(BaseModel):
    methodology: CscMethodologyBlock
    cohort: CscCohortBlock
    comparables: CscComparablesBlock
    provenance: CscProvenanceBlock
    shap_attribution: CscShapTable


class CscDetailOut(BaseModel):
    shap_attribution: str
    methodology: str
    inputs: str
    blocks: CscDetailBlocks | None = None


class CscReportOut(BaseModel):
    value: CscValueOut
    explanation: CscExplanationOut
    validation: CscValidationOut
    confidence_risk: CscConfidenceRiskOut
    detail: CscDetailOut

    class CscMetadataOut(BaseModel):
        tier_version: Literal["tier_v1", "tier_v2"]
        tier_v1: str
        tier_v2: str
        cohort_window_days_used: int
        season_state: str
        cohort_size: int
        cohort_fallback_step: Literal[0, 1, 2, 3, 4]
        comparable_state: Literal["sufficient", "sparse", "none"]
        comparable_sets_computed_at: str | None = None
        exposure_formula_version: str
        exposure_formula_weights: Dict[str, float]
        rollout_phase: str
        low_cohort_data: bool
        athlete_benchmark_percentile_in_cohort: float | None = None
        conference: str | None = None
        conference_tier: Literal["power_5", "group_of_5", "fcs", "mid_major", "other"] | None = None
        conference_mapping_status: Literal[
            "mapped", "stored_fallback", "school_fallback", "unmapped"
        ] | None = None
        # CSC v3 fields (populated incrementally during rollout).
        model_status: Literal["production", "fallback", "unknown"] | None = None
        model_version: str | None = None
        cohort_fit: Literal["good", "edge", "poor"] | None = None
        range_quality: Literal["normal", "wide", "estimate", "unavailable"] | None = None
        report_id: str | None = None
        report_version: Literal["v2", "v3"] | None = None
        report_rollout_phase: str | None = None

    metadata: CscMetadataOut


@router.post("/brand-match")
async def brand_match(
    body: BrandMatchBriefIn,
    db: asyncpg.Connection = Depends(get_db),
):
    scored = await run_brand_match(
        db,
        BrandMatchBriefData(
            budget=body.budget,
            category=body.category,
            geography=body.geography,
            audience=body.audience,
            risk_tolerance=body.risk_tolerance,
            max_transfer_risk=body.max_transfer_risk,
            authenticity_weight=body.authenticity_weight,
            min_social_reach=body.min_social_reach,
            prioritize_engagement=body.prioritize_engagement,
            excluded_categories=body.excluded_categories,
            deal_density_preference=body.deal_density_preference,
            sports=body.sports,
        ),
    )
    return scored


@router.post("/csc", response_model=CscReportOut)
async def post_csc_report(
    body: Dict[str, Any],
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID | None = Depends(optional_user_id),
    allow_fallback: bool = Query(
        False,
        description=(
            "Admin override: when true and the caller presents the internal admin key, "
            "the report will be returned even if the scorer is on a fallback model."
        ),
    ),
    x_gravity_admin_key: str | None = Header(default=None, alias="X-Gravity-Admin-Key"),
):
    athlete_id = body.get("athlete_id")
    if not athlete_id:
        raise HTTPException(status_code=400, detail="athlete_id required")
    try:
        uuid.UUID(str(athlete_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="athlete_id must be a UUID") from exc
    params = {k: v for k, v in body.items() if k != "athlete_id"}
    try:
        report = await build_csc_report_json(
            db,
            str(athlete_id),
            params,
            user_id=str(user_id) if user_id else None,
        )
    except ConferenceNotMappedError as e:
        raise HTTPException(
            status_code=422,
            detail=(
                "Athlete's team is missing conference mapping; cannot generate report "
                f"({e.team_id})"
            ),
        ) from e
    except ValueError:
        raise HTTPException(status_code=404, detail="Athlete not found") from None

    # Per-report fallback enforcement. A fallback model means the report
    # cannot be used for binding deal decisions; the report already carries
    # `metadata.model_status = "fallback"` and the UI/PDF render an
    # unmistakable banner. Hard-blocking the endpoint is opt-in via
    # `CSC_BLOCK_FALLBACK=1` (and is still gated by the admin override
    # path) so the default behavior is "ship with banner".
    metadata = report.get("metadata") if isinstance(report, dict) else None
    if isinstance(metadata, dict) and metadata.get("model_status") == "fallback":
        if _block_fallback_reports() and not (
            allow_fallback and _admin_override_active(x_gravity_admin_key)
        ):
            logger.warning(
                "CSC report blocked (CSC_BLOCK_FALLBACK=1): athlete=%s model_version=%s",
                athlete_id,
                metadata.get("model_version"),
            )
            raise HTTPException(
                status_code=503,
                detail=(
                    "Fallback scorer active; refusing to issue binding report. "
                    "Contact admin to override."
                ),
            )
        logger.warning(
            "CSC report served with fallback banner: athlete=%s model_version=%s",
            athlete_id,
            metadata.get("model_version"),
        )

    # Final acceptance-criteria sweep. Cosmetic/copy violations are logged
    # as warnings for ops review; only structural violations in
    # `BLOCKING_ERROR_CODES` (placeholder conference, uncapped percentile,
    # fallback model with high confidence, tier-version mismatch) take the
    # report offline. Everything else still ships so a single drift in
    # prose never 500s the endpoint.
    validation_errors = validate_report(report)
    if validation_errors:
        logger.warning(
            "CSC report validator findings: athlete=%s errors=%s",
            athlete_id,
            [(e.code, e.message) for e in validation_errors],
        )
        critical = blocking_errors(validation_errors)
        if critical:
            logger.error(
                "CSC report blocked on validator: athlete=%s blocking_errors=%s",
                athlete_id,
                [(e.code, e.message) for e in critical],
            )
            raise HTTPException(
                status_code=500,
                detail=(
                    "Report failed internal validation; please retry or contact support."
                ),
            )
    return report
