"""Deal valuation reports, CSC JSON, brand match."""

import json
import uuid
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from gravity_api.auth_deps import require_user_id
from gravity_api.database import get_db
from gravity_api.services.compatibility import compatibility_score
from gravity_api.services.csc_report_builder import build_csc_report_json

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
        report_json = await build_csc_report_json(db, str(athlete_uuid), body.parameters)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

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


@router.post("/brand-match")
async def brand_match(
    body: BrandMatchBriefIn,
    db: asyncpg.Connection = Depends(get_db),
):
    max_risk_cap = min(
        100.0,
        float(body.risk_tolerance) * 100.0 + (25.0 if body.max_transfer_risk else 0.0),
    )
    rows = await db.fetch(
        """
        SELECT a.id, a.name, a.school, a.position, a.conference, a.sport, a.home_state,
               s.gravity_score, s.brand_score, s.proof_score,
               s.proximity_score, s.velocity_score, s.risk_score
        FROM athletes a
        LEFT JOIN LATERAL (
            SELECT * FROM athlete_gravity_scores
            WHERE athlete_id = a.id
            ORDER BY calculated_at DESC LIMIT 1
        ) s ON true
        WHERE s.gravity_score IS NOT NULL
          AND (s.risk_score IS NULL OR s.risk_score <= $1)
        ORDER BY s.brand_score DESC NULLS LAST
        LIMIT 80
        """,
        max_risk_cap,
    )

    if body.brand_profile is not None:
        bp = body.brand_profile
        # Auth/stability default to brief-derived values when not given.
        auth = (
            bp.authenticity_score
            if bp.authenticity_score is not None
            else max(0.0, min(100.0, float(body.authenticity_weight) * 100.0))
        )
        stab = (
            bp.stability_score
            if bp.stability_score is not None
            else max(0.0, 100.0 - float(body.risk_tolerance) * 100.0)
        )
        brand_profile = {
            "reach_score": float(bp.reach_score),
            "value_score": float(bp.value_score),
            "fit_score": float(bp.fit_score),
            "authenticity_score": float(auth),
            "stability_score": float(stab),
        }
    else:
        brand_profile = {
            "reach_score": 72.0,
            "value_score": 68.0,
            "fit_score": 70.0,
            "authenticity_score": max(
                0.0, min(100.0, float(body.authenticity_weight) * 100.0)
            ),
            "stability_score": max(
                0.0, 100.0 - float(body.risk_tolerance) * 100.0
            ),
        }
    compat_brief: Dict[str, Any] = {
        "budget_usd_max": body.budget,
        "target_categories": [body.category] if body.category else None,
        "target_states": body.geography or None,
    }

    scored: List[Dict[str, Any]] = []
    for r in rows:
        rowd = dict(r)
        athlete_payload = {
            "brand_score": float(rowd["brand_score"] or 0),
            "proof_score": float(rowd["proof_score"] or 0),
            "proximity_score": float(rowd["proximity_score"] or 0),
            "velocity_score": float(rowd["velocity_score"] or 0),
            "risk_score": float(rowd["risk_score"] or 0),
            "primary_interest_category": body.category,
            "school_state": rowd.get("home_state"),
            "dollar_p50_usd": None,
        }
        comp = compatibility_score(athlete_payload, brand_profile, compat_brief)
        sub = comp.get("subscores") or {}
        rationale_parts = [
            f"core={comp.get('compatibility_core_0_1', 0):.2f}",
            f"brand_align={sub.get('alignment_brand', 0):.2f}",
            f"risk_align={sub.get('alignment_risk_stability', 0):.2f}",
        ]
        g = rowd.get("gravity_score")
        scored.append(
            {
                "athlete_id": str(rowd["id"]),
                "name": rowd["name"],
                "school": rowd.get("school"),
                "position": rowd.get("position"),
                "match_score": comp["compatibility_score"],
                "gravity_score": float(g) if g is not None else None,
                "brand_score": float(rowd["brand_score"]) if rowd.get("brand_score") is not None else None,
                "deal_range_low": None,
                "deal_range_high": None,
                "fit_rationale": "; ".join(rationale_parts),
            }
        )

    scored.sort(key=lambda x: -x["match_score"])
    return scored[:25]


@router.post("/csc")
async def post_csc_report(
    body: Dict[str, Any],
    db: asyncpg.Connection = Depends(get_db),
):
    athlete_id = body.get("athlete_id")
    if not athlete_id:
        raise HTTPException(status_code=400, detail="athlete_id required")
    params = {k: v for k, v in body.items() if k != "athlete_id"}
    try:
        report = await build_csc_report_json(db, str(athlete_id), params)
    except ValueError:
        raise HTTPException(status_code=404, detail="Athlete not found") from None
    return report
