"""
Brand scoring endpoints — latest Gravity scores for sponsor companies.
Mounted at /v1/brands in main.py.
"""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from gravity_api.database import get_db

router = APIRouter()


@router.get("/")
async def list_brands(
    limit: int = 50,
    offset: int = 0,
    db: asyncpg.Connection = Depends(get_db),
):
    """List brands with their latest gravity score."""
    rows = await db.fetch(
        """
        SELECT DISTINCT ON (b.id)
               b.id, b.display_name, b.category,
               bgs.gravity_score, bgs.reach_score, bgs.authenticity_score,
               bgs.value_score, bgs.fit_score, bgs.stability_score,
               bgs.model_version, bgs.scored_at
        FROM   brands b
        LEFT JOIN brand_gravity_scores bgs ON bgs.brand_id = b.id
        ORDER  BY b.id, bgs.scored_at DESC NULLS LAST
        LIMIT  $1 OFFSET $2
        """,
        limit,
        offset,
    )
    return {"brands": [dict(r) for r in rows], "limit": limit, "offset": offset}


@router.get("/{brand_id}/score")
async def get_brand_score(
    brand_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Latest Gravity score for a sponsor brand.
    Returns five component scores: reach, authenticity, value, fit, stability.
    """
    row = await db.fetchrow(
        """
        SELECT bgs.*, b.display_name, b.category
        FROM   brand_gravity_scores bgs
        JOIN   brands b ON b.id = bgs.brand_id
        WHERE  bgs.brand_id = $1
        ORDER  BY bgs.scored_at DESC
        LIMIT  1
        """,
        brand_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No gravity score found for this brand")
    return dict(row)


@router.get("/{brand_id}/score/history")
async def get_brand_score_history(
    brand_id: str,
    limit: int = 30,
    db: asyncpg.Connection = Depends(get_db),
):
    """Historical Gravity scores for a brand (most recent first)."""
    rows = await db.fetch(
        """
        SELECT id, gravity_score, reach_score, authenticity_score,
               value_score, fit_score, stability_score,
               model_version, scored_at
        FROM   brand_gravity_scores
        WHERE  brand_id = $1
        ORDER  BY scored_at DESC
        LIMIT  $2
        """,
        brand_id,
        limit,
    )
    return {"brand_id": brand_id, "history": [dict(r) for r in rows]}


@router.get("/{brand_id}/athletes")
async def get_brand_athletes(
    brand_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    """Athletes with active NIL deals for this brand."""
    rows = await db.fetch(
        """
        SELECT a.id, a.full_name, a.sport, a.school,
               gs.gravity_score, nd.deal_value_usd, nd.status
        FROM   nil_deals nd
        JOIN   athletes a ON a.id = nd.athlete_id
        LEFT JOIN gravity_scores gs ON gs.athlete_id = a.id
        WHERE  nd.brand_id = $1
        ORDER  BY gs.gravity_score DESC NULLS LAST
        """,
        brand_id,
    )
    return {"brand_id": brand_id, "athletes": [dict(r) for r in rows]}
