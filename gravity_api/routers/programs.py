from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from gravity_api.database import get_db

router = APIRouter()


def _invert_risk(v: object) -> float | None:
    if v is None:
        return None
    try:
        return max(0.0, min(100.0, 100.0 - float(v)))
    except (TypeError, ValueError):
        return None


@router.get("")
@router.get("/", include_in_schema=False)
async def list_programs(
    sport: Optional[str] = None,
    db: asyncpg.Connection = Depends(get_db),
):
    if sport:
        rows = await db.fetch(
            "SELECT * FROM programs WHERE sport = $1 ORDER BY school", sport
        )
    else:
        rows = await db.fetch("SELECT * FROM programs ORDER BY conference, school")
    return {"programs": [dict(r) for r in rows]}


@router.get("/{team_id}/score")
async def get_program_score(
    team_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Latest Gravity score for a sport-specific program (team).
    Returns all five component scores: brand, proof, platform, velocity, risk.
    """
    row = await db.fetchrow(
        """
        SELECT tgs.*, t.school_name, t.conference, t.sport
        FROM   team_gravity_scores tgs
        JOIN   teams t ON t.id = tgs.team_id
        WHERE  tgs.team_id = $1
        ORDER  BY tgs.scored_at DESC
        LIMIT  1
        """,
        team_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No gravity score found for this program")
    out = dict(row)
    if "risk_score" in out:
        out["risk_score"] = _invert_risk(out.get("risk_score"))
    return out


@router.get("/{team_id}/score/history")
async def get_program_score_history(
    team_id: str,
    limit: int = 30,
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Historical gravity scores for a program (most recent first).
    """
    rows = await db.fetch(
        """
        SELECT id, gravity_score, brand_score, proof_score,
               platform_score, velocity_score, (100.0 - risk_score) AS risk_score,
               model_version, scored_at
        FROM   team_gravity_scores
        WHERE  team_id = $1
        ORDER  BY scored_at DESC
        LIMIT  $2
        """,
        team_id,
        limit,
    )
    return {"team_id": team_id, "history": [dict(r) for r in rows]}
