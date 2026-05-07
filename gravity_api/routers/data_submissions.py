"""School athlete data submissions and org-enhanced scoring."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from gravity_api.auth_deps import require_user_id
from gravity_api.config import get_settings
from gravity_api.database import get_db
from gravity_api.services.athlete_score_sync import athlete_to_raw_data, sync_athlete_score_from_ml
from gravity_api.services.data_verification import run_stub_verification
from gravity_api.services.org_auth import load_school_auth
from gravity_api.services.sport_query import cap_prefs_to_db_slugs
from gravity_api.services.scraper_prop_shop import COLLECTOR_MAP, STATE

router = APIRouter()


def _uuid(s: str, name: str = "id") -> uuid.UUID:
    try:
        return uuid.UUID(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid {name}") from e


class SubmitBody(BaseModel):
    org_id: str
    athlete_id: str
    fields: Dict[str, Any] = Field(default_factory=dict)
    source_notes: Optional[str] = None
    run_verification: bool = Field(
        default=False,
        description="If true, run stub auto-verification (otherwise stays pending).",
    )


class ImputeField(BaseModel):
    field_name: str = Field(..., min_length=1, max_length=120)
    field_value: Any
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    reason: Optional[str] = Field(default=None, max_length=500)


class ImputeBody(BaseModel):
    athlete_id: str
    org_id: Optional[str] = None
    scope: str = Field(default="org", pattern="^(org|global)$")
    fields: list[ImputeField] = Field(default_factory=list, min_length=1)
    trigger_rescore: bool = True


async def _require_admin(db: asyncpg.Connection, user_id: uuid.UUID) -> None:
    role = await db.fetchval("SELECT role FROM user_accounts WHERE id = $1", user_id)
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")


def _ensure_org_member_can_impute_athlete_sport(
    ctx,
    athlete_sport_slug: str,
) -> None:
    if ctx.is_org_admin:
        return
    allowed_slugs = cap_prefs_to_db_slugs(ctx.coach_sports)
    if athlete_sport_slug in allowed_slugs:
        return
    raise HTTPException(status_code=403, detail="Sport not permitted for this account")


@router.post("/submit")
async def submit_athlete_data(
    body: SubmitBody,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    oid = _uuid(body.org_id, "org_id")
    await load_school_auth(oid, user_id, db)
    aid = _uuid(body.athlete_id, "athlete_id")
    exists = await db.fetchval("SELECT 1 FROM athletes WHERE id = $1", aid)
    if not exists:
        raise HTTPException(status_code=404, detail="Athlete not found")
    status = "pending"
    vresults: Optional[Dict[str, Any]] = None
    if body.run_verification and body.fields:
        status, vresults = run_stub_verification(body.fields)
    row = await db.fetchrow(
        """INSERT INTO athlete_data_submissions (
             athlete_id, org_id, submitted_by, fields, source_notes, status, verification_results
           ) VALUES ($1,$2,$3,$4::jsonb,$5,$6,$7::jsonb)
           RETURNING id, status""",
        aid,
        oid,
        user_id,
        json.dumps(body.fields),
        body.source_notes,
        status,
        json.dumps(vresults) if vresults else None,
    )
    STATE.enqueue(
        "P2",
        {
            "type": "school_submission",
            "athlete_id": str(aid),
            "org_id": str(oid),
            "submission_id": str(row["id"]),
            "collectors": COLLECTOR_MAP["school_submission"],
        },
    )
    return {"id": str(row["id"]), "status": row["status"], "verification_results": vresults}


@router.post("/impute")
async def upsert_imputations(
    body: ImputeBody,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    aid = _uuid(body.athlete_id, "athlete_id")
    athlete = await db.fetchrow("SELECT id, sport FROM athletes WHERE id = $1", aid)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    scope = body.scope
    source_type: str
    org_uuid: Optional[uuid.UUID] = None
    if scope == "global":
        await _require_admin(db, user_id)
        source_type = "admin_manual"
    else:
        if not body.org_id:
            raise HTTPException(status_code=400, detail="org_id is required for org scope")
        org_uuid = _uuid(body.org_id, "org_id")
        ctx = await load_school_auth(org_uuid, user_id, db)
        _ensure_org_member_can_impute_athlete_sport(ctx, str(athlete["sport"]))
        source_type = "school_manual"

    applied_fields: list[str] = []
    for f in body.fields:
        fname = f.field_name.strip()
        if scope == "global":
            await db.execute(
                """INSERT INTO athlete_manual_imputations (
                     athlete_id, scope, org_id, field_name, field_value, confidence, source_type, reason, created_by
                   ) VALUES ($1, 'global', NULL, $2, $3::jsonb, $4, $5, $6, $7)
                   ON CONFLICT (athlete_id, field_name)
                   WHERE scope = 'global' AND org_id IS NULL
                   DO UPDATE SET
                     field_value = EXCLUDED.field_value,
                     confidence = EXCLUDED.confidence,
                     source_type = EXCLUDED.source_type,
                     reason = EXCLUDED.reason,
                     created_by = EXCLUDED.created_by,
                     updated_at = NOW()""",
                aid,
                fname,
                json.dumps(f.field_value),
                f.confidence,
                source_type,
                f.reason,
                user_id,
            )
        else:
            await db.execute(
                """INSERT INTO athlete_manual_imputations (
                     athlete_id, scope, org_id, field_name, field_value, confidence, source_type, reason, created_by
                   ) VALUES ($1, 'org', $2, $3, $4::jsonb, $5, $6, $7, $8)
                   ON CONFLICT (athlete_id, org_id, field_name)
                   WHERE scope = 'org' AND org_id IS NOT NULL
                   DO UPDATE SET
                     field_value = EXCLUDED.field_value,
                     confidence = EXCLUDED.confidence,
                     source_type = EXCLUDED.source_type,
                     reason = EXCLUDED.reason,
                     created_by = EXCLUDED.created_by,
                     updated_at = NOW()""",
                aid,
                org_uuid,
                fname,
                json.dumps(f.field_value),
                f.confidence,
                source_type,
                f.reason,
                user_id,
            )
        applied_fields.append(fname)

    score_payload: Optional[Dict[str, Any]] = None
    if body.trigger_rescore:
        score_payload = await sync_athlete_score_from_ml(db, str(aid))

    return {
        "athlete_id": str(aid),
        "scope": scope,
        "org_id": str(org_uuid) if org_uuid else None,
        "applied_fields": applied_fields,
        "rescored": body.trigger_rescore,
        "score": score_payload,
    }


@router.get("/submissions/{org_id}")
async def list_submissions(
    org_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    oid = _uuid(org_id, "org_id")
    await load_school_auth(oid, user_id, db)
    rows = await db.fetch(
        """SELECT id, athlete_id, status, created_at, verification_results
           FROM athlete_data_submissions WHERE org_id = $1 ORDER BY created_at DESC LIMIT 100""",
        oid,
    )
    return {
        "submissions": [
            {
                "id": str(r["id"]),
                "athlete_id": str(r["athlete_id"]),
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "verification_results": r["verification_results"],
            }
            for r in rows
        ]
    }


async def _latest_raw_for_athlete(conn: asyncpg.Connection, athlete_id: str) -> Dict[str, Any]:
    try:
        row = await conn.fetchrow(
            """SELECT raw_data FROM raw_athlete_data
               WHERE athlete_id = $1::uuid ORDER BY scraped_at DESC NULLS LAST LIMIT 1""",
            athlete_id,
        )
    except Exception:
        return {}
    if row and row["raw_data"]:
        rd = row["raw_data"]
        if isinstance(rd, str):
            return json.loads(rd)
        return dict(rd)
    return {}


@router.post("/org-score/{org_id}/{athlete_id}")
async def compute_org_enhanced_score(
    org_id: str,
    athlete_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    """Blend network raw with org overrides, POST to gravity-ml, persist athlete_org_gravity_scores."""
    oid = _uuid(org_id, "org_id")
    await load_school_auth(oid, user_id, db)
    aid = _uuid(athlete_id, "athlete_id")
    settings = get_settings()
    if not settings.ml_service_url or not settings.ml_api_key:
        raise HTTPException(status_code=503, detail="ML service not configured")
    athlete = await db.fetchrow("SELECT * FROM athletes WHERE id = $1", aid)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    snap = await db.fetchrow(
        """SELECT * FROM social_snapshots WHERE athlete_id = $1
           ORDER BY scraped_at DESC LIMIT 1""",
        aid,
    )
    raw = athlete_to_raw_data(athlete, snap)
    net_raw = await _latest_raw_for_athlete(db, str(aid))
    if net_raw:
        raw = {**net_raw, **raw}
    ovs = await db.fetch(
        """SELECT field_name, org_value, confidence FROM athlete_org_overrides
           WHERE org_id = $1 AND athlete_id = $2""",
        oid,
        aid,
    )
    blend: Dict[str, Any] = {"sources": []}
    for o in ovs:
        fn = o["field_name"]
        raw[fn] = o["org_value"]
        blend["sources"].append({"field": fn, "source": "org", "confidence": float(o["confidence"] or 0.6)})
    headers = {"Authorization": f"Bearer {settings.ml_api_key}"}
    base = settings.ml_service_url
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{base}/score/athlete",
            params={"include_shap": "true"},
            json={
                "athlete_id": str(aid),
                "sport": athlete["sport"],
                "raw_data": raw,
                "partial_scoring": False,
                "org_blend": True,
                "org_id": str(oid),
            },
            headers=headers,
        )
        r.raise_for_status()
        score_data = r.json()
    await db.execute(
        """INSERT INTO athlete_org_gravity_scores (
             athlete_id, org_id, gravity_score, brand_score, proof_score, proximity_score,
             velocity_score, risk_score, blend_config, computed_at
           ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb, NOW())
           ON CONFLICT (athlete_id, org_id) DO UPDATE SET
             gravity_score = EXCLUDED.gravity_score,
             brand_score = EXCLUDED.brand_score,
             proof_score = EXCLUDED.proof_score,
             proximity_score = EXCLUDED.proximity_score,
             velocity_score = EXCLUDED.velocity_score,
             risk_score = EXCLUDED.risk_score,
             blend_config = EXCLUDED.blend_config,
             computed_at = NOW()""",
        aid,
        oid,
        float(score_data["gravity_score"]),
        float(score_data.get("brand_score") or 0),
        float(score_data.get("proof_score") or 0),
        float(score_data.get("proximity_score") or 0),
        float(score_data.get("velocity_score") or 0),
        float(score_data.get("risk_score") or 0),
        json.dumps(blend),
    )
    return {
        "athlete_id": str(aid),
        "org_id": str(oid),
        "gravity_score": score_data["gravity_score"],
        "brand_score": score_data.get("brand_score"),
        "blend_config": blend,
    }
