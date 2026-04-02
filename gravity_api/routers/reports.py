"""Deal valuation reports — PDF generation wired in Week 2."""

from typing import Any, Dict

import asyncpg
from fastapi import APIRouter, Depends

from gravity_api.database import get_db

router = APIRouter()


@router.get("/")
async def list_reports_placeholder(db: asyncpg.Connection = Depends(get_db)):
    rows = await db.fetch(
        """SELECT id, report_uuid, athlete_id, status, created_at
           FROM deal_valuation_reports
           ORDER BY created_at DESC
           LIMIT 50"""
    )
    return {"reports": [dict(r) for r in rows]}


@router.post("/")
async def create_report(req: Dict[str, Any], db: asyncpg.Connection = Depends(get_db)):
    """Placeholder create — extend with auth + Stripe."""
    return {"detail": "Implement report intake + underwriter in services/report_gen.py", "received": req}
