"""JWT login (email → user_accounts), register, onboarding, and /me."""

import uuid

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

import asyncpg

from gravity_api.auth_deps import require_user_id
from gravity_api.config import get_settings
from gravity_api.database import get_db
from gravity_api.services.onboarding_defaults import (
    assert_org_type,
    default_athletes_sort_for_org_type,
    default_dashboard_tab_for_org_type,
    normalize_sport_preferences,
)

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str | None = Field(None, description="Required when account has a password set")


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=8, max_length=256)
    display_name: str = Field(..., min_length=1, max_length=200)


class OnboardingCompleteBody(BaseModel):
    org_type: str
    sport_preferences: list[str] = Field(..., min_length=1)
    org_name: str | None = Field(None, max_length=500)
    team_or_athlete_seed: str | None = Field(None, max_length=500)
    onboarding_goal: str | None = Field(None, max_length=150)


@router.post("/register")
async def register(body: RegisterRequest, db: asyncpg.Connection = Depends(get_db)):
    settings = get_settings()
    if not settings.jwt_secret:
        raise HTTPException(status_code=503, detail="JWT secret not configured")
    email = body.email.strip().lower()
    exists = await db.fetchval(
        "SELECT 1 FROM user_accounts WHERE lower(email) = lower($1)",
        email,
    )
    if exists:
        raise HTTPException(status_code=409, detail="Email already registered")
    pw_hash = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
    row = await db.fetchrow(
        """INSERT INTO user_accounts (email, role, organization, password_hash, display_name)
           VALUES ($1, 'agent', '', $2, $3)
           RETURNING id, email, role""",
        email,
        pw_hash,
        body.display_name.strip(),
    )
    token = jwt.encode(
        {
            "sub": str(row["id"]),
            "email": row["email"],
            "role": row["role"],
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": str(row["id"]),
        "email": row["email"],
    }


@router.post("/login")
async def login(body: LoginRequest, db: asyncpg.Connection = Depends(get_db)):
    settings = get_settings()
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=503,
            detail="JWT_SECRET (or GRAVITY_JWT_SECRET) is not configured",
        )
    row = await db.fetchrow(
        """SELECT id, email, role, password_hash FROM user_accounts WHERE lower(email) = lower($1)""",
        body.email.strip(),
    )
    if not row:
        raise HTTPException(
            status_code=404,
            detail="No user_accounts row for this email — insert one in Postgres first",
        )
    ph = row["password_hash"]
    if ph:
        if not body.password:
            raise HTTPException(status_code=401, detail="Password required")
        if not bcrypt.checkpw(
            body.password.encode("utf-8"),
            ph.encode("utf-8") if isinstance(ph, str) else ph,
        ):
            raise HTTPException(status_code=401, detail="Invalid password")
    token = jwt.encode(
        {
            "sub": str(row["id"]),
            "email": row["email"],
            "role": row["role"],
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": str(row["id"]),
        "email": row["email"],
    }


@router.post("/onboarding")
async def complete_onboarding(
    body: OnboardingCompleteBody,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    done = await db.fetchval(
        "SELECT onboarding_completed_at FROM user_accounts WHERE id = $1",
        user_id,
    )
    if done:
        raise HTTPException(status_code=409, detail="Onboarding already completed")
    try:
        ot = assert_org_type(body.org_type)
        sports = normalize_sport_preferences(body.sport_preferences)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    tab = default_dashboard_tab_for_org_type(ot)
    sort_hint = default_athletes_sort_for_org_type(ot)
    await db.execute(
        """UPDATE user_accounts SET
             org_type = $2,
             sport_preferences = $3::text[],
             org_name = $4,
             team_or_athlete_seed = $5,
             onboarding_goal = $6,
             default_dashboard_tab = $7,
             athletes_default_sort = $8,
             onboarding_completed_at = NOW()
           WHERE id = $1 AND onboarding_completed_at IS NULL""",
        user_id,
        ot,
        sports,
        body.org_name,
        body.team_or_athlete_seed,
        body.onboarding_goal,
        tab,
        sort_hint,
    )
    row = await db.fetchrow(
        """SELECT id, email, role, org_type, sport_preferences, org_name, team_or_athlete_seed,
                  default_dashboard_tab, athletes_default_sort, onboarding_completed_at, display_name,
                  onboarding_goal
           FROM user_accounts WHERE id = $1""",
        user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    sp = row["sport_preferences"] or ["CFB"]
    return {
        "user_id": str(row["id"]),
        "email": row["email"],
        "role": row["role"],
        "org_type": row["org_type"],
        "sport_preferences": list(sp) if not isinstance(sp, list) else sp,
        "org_name": row["org_name"],
        "team_or_athlete_seed": row["team_or_athlete_seed"],
        "default_dashboard_tab": row["default_dashboard_tab"],
        "athletes_default_sort": row["athletes_default_sort"],
        "onboarding_completed_at": row["onboarding_completed_at"].isoformat()
        if row["onboarding_completed_at"]
        else None,
        "display_name": row["display_name"],
        "onboarding_goal": row["onboarding_goal"],
    }


@router.get("/me")
async def me(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: asyncpg.Connection = Depends(get_db),
):
    settings = get_settings()
    if not creds or creds.scheme.lower() != "bearer" or not creds.credentials:
        raise HTTPException(status_code=401, detail="Bearer token required")
    if not settings.jwt_secret:
        raise HTTPException(status_code=503, detail="JWT secret not configured")
    try:
        payload = jwt.decode(
            creds.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token") from e
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing sub")
    try:
        uid = uuid.UUID(str(sub))
    except ValueError as e:
        raise HTTPException(status_code=401, detail="Invalid sub") from e
    row = await db.fetchrow(
        """SELECT u.id, u.email, u.role, u.organization, u.organization_id,
                  u.org_type, u.onboarding_completed_at, u.display_name,
                  o.slug AS organization_slug
           FROM user_accounts u
           LEFT JOIN organizations o ON o.id = u.organization_id
           WHERE u.id = $1""",
        uid,
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    coach_sports: list[str | None] = []
    if row["organization_id"]:
        coach_sports = [
            r["sport"]
            for r in await db.fetch(
                """SELECT sport FROM organization_members
                   WHERE user_id = $1 AND org_id = $2 AND role = 'school_coach' AND sport IS NOT NULL""",
                uid,
                row["organization_id"],
            )
        ]
    return {
        "user_id": str(row["id"]),
        "email": row["email"],
        "role": row["role"],
        "organization": row["organization"],
        "organization_id": str(row["organization_id"]) if row["organization_id"] else None,
        "organization_slug": row["organization_slug"],
        "coach_sports": [s for s in coach_sports if s],
        "org_type": row["org_type"],
        "display_name": row["display_name"],
        "onboarding_completed_at": row["onboarding_completed_at"].isoformat()
        if row["onboarding_completed_at"]
        else None,
    }


@router.get("/health")
async def auth_health():
    return {"auth": "ok"}
