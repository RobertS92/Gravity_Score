"""User preferences for onboarding personalization (single-row user_accounts)."""

from __future__ import annotations

import uuid
from typing import Any, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from gravity_api.auth_deps import require_user_id
from gravity_api.database import get_db
from gravity_api.services.onboarding_defaults import (
    VALID_DASHBOARD_TABS,
    assert_org_type,
    normalize_sport_preferences,
)

router = APIRouter()


def _prefs_row(r: asyncpg.Record, include_goal: bool = True) -> dict[str, Any]:
    sp = r["sport_preferences"]
    if sp is None:
        sp_list: List[str] = ["CFB"]
    elif isinstance(sp, list):
        sp_list = [str(x) for x in sp]
    else:
        sp_list = list(sp)
    out: dict[str, Any] = {
        "org_type": r["org_type"],
        "sport_preferences": sp_list,
        "org_name": r["org_name"],
        "team_or_athlete_seed": r["team_or_athlete_seed"],
        "default_dashboard_tab": r["default_dashboard_tab"],
        "athletes_default_sort": r["athletes_default_sort"],
        "onboarding_completed_at": r["onboarding_completed_at"].isoformat() if r["onboarding_completed_at"] else None,
        "display_name": r.get("display_name"),
    }
    if include_goal:
        out["onboarding_goal"] = r.get("onboarding_goal")
    return out


@router.get("/preferences")
async def get_preferences(
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    row = await db.fetchrow(
        """SELECT org_type, sport_preferences, org_name, team_or_athlete_seed,
                  default_dashboard_tab, athletes_default_sort, onboarding_completed_at,
                  display_name, onboarding_goal
           FROM user_accounts WHERE id = $1""",
        user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return _prefs_row(row)


class PreferencesPatchBody(BaseModel):
    sport_preferences: Optional[List[str]] = None
    org_name: Optional[str] = None
    team_or_athlete_seed: Optional[str] = None
    default_dashboard_tab: Optional[str] = None
    onboarding_goal: Optional[str] = Field(None, max_length=150)


@router.patch("/preferences")
async def patch_preferences(
    body: PreferencesPatchBody,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    dump = body.model_dump(exclude_unset=True)
    if not dump:
        row = await db.fetchrow(
            """SELECT org_type, sport_preferences, org_name, team_or_athlete_seed,
                      default_dashboard_tab, athletes_default_sort, onboarding_completed_at,
                      display_name, onboarding_goal
               FROM user_accounts WHERE id = $1""",
            user_id,
        )
        return _prefs_row(row) if row else {}

    norm_sports: Optional[List[str]] = None
    try:
        if "sport_preferences" in dump and dump["sport_preferences"] is not None:
            norm_sports = normalize_sport_preferences(dump["sport_preferences"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if "default_dashboard_tab" in dump and dump["default_dashboard_tab"] is not None:
        if dump["default_dashboard_tab"] not in VALID_DASHBOARD_TABS:
            raise HTTPException(status_code=400, detail="Invalid default_dashboard_tab")

    sets: List[str] = []
    vals: List[Any] = []
    n = 1
    if norm_sports is not None:
        sets.append(f"sport_preferences = ${n}::text[]")
        vals.append(norm_sports)
        n += 1
    if "org_name" in dump:
        sets.append(f"org_name = ${n}")
        vals.append(dump["org_name"])
        n += 1
    if "team_or_athlete_seed" in dump:
        sets.append(f"team_or_athlete_seed = ${n}")
        vals.append(dump["team_or_athlete_seed"])
        n += 1
    if "default_dashboard_tab" in dump:
        sets.append(f"default_dashboard_tab = ${n}")
        vals.append(dump["default_dashboard_tab"])
        n += 1
    if "onboarding_goal" in dump:
        sets.append(f"onboarding_goal = ${n}")
        vals.append(dump["onboarding_goal"])
        n += 1
    vals.append(user_id)
    await db.execute(
        f"UPDATE user_accounts SET {', '.join(sets)} WHERE id = ${n}",
        *vals,
    )
    row = await db.fetchrow(
        """SELECT org_type, sport_preferences, org_name, team_or_athlete_seed,
                  default_dashboard_tab, athletes_default_sort, onboarding_completed_at,
                  display_name, onboarding_goal
           FROM user_accounts WHERE id = $1""",
        user_id,
    )
    return _prefs_row(row) if row else {}
