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
from gravity_api.services.athlete_score_sync import athlete_to_raw_data
from gravity_api.services.data_verification import run_stub_verification
from gravity_api.services.org_auth import load_school_auth
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
