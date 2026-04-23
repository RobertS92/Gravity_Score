"""Org + sport access for CapIQ and school data routes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import List

import asyncpg
from fastapi import HTTPException

from gravity_api.services.cap_sport import CAP_SPORTS, assert_cap_sport


@dataclass
class SchoolAuthContext:
    user_id: uuid.UUID
    org_id: uuid.UUID
    is_org_admin: bool
    coach_sports: List[str]


async def load_school_auth(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    db: asyncpg.Connection,
) -> SchoolAuthContext:
    acct = await db.fetchrow("SELECT role FROM user_accounts WHERE id = $1", user_id)
    if acct and acct["role"] == "admin":
        return SchoolAuthContext(
            user_id=user_id,
            org_id=org_id,
            is_org_admin=True,
            coach_sports=list(CAP_SPORTS),
        )
    rows = await db.fetch(
        """SELECT role, sport FROM organization_members
           WHERE user_id = $1 AND org_id = $2""",
        user_id,
        org_id,
    )
    if not rows:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    is_admin = any(r["role"] == "school_admin" for r in rows)
    coach_sports = [r["sport"] for r in rows if r["role"] == "school_coach" and r["sport"]]
    return SchoolAuthContext(
        user_id=user_id,
        org_id=org_id,
        is_org_admin=is_admin,
        coach_sports=coach_sports,
    )


def ensure_sport_allowed(ctx: SchoolAuthContext, sport: str) -> None:
    cap = assert_cap_sport(sport)
    if ctx.is_org_admin:
        return
    if cap in ctx.coach_sports:
        return
    raise HTTPException(status_code=403, detail="Sport not permitted for this account")


def ensure_org_admin(ctx: SchoolAuthContext) -> None:
    if not ctx.is_org_admin:
        raise HTTPException(status_code=403, detail="School admin role required")

