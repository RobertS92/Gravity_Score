"""JWT login (email → user_accounts) and /me."""

import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

import asyncpg

from gravity_api.config import get_settings
from gravity_api.database import get_db

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)


@router.post("/login")
async def login(body: LoginRequest, db: asyncpg.Connection = Depends(get_db)):
    settings = get_settings()
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=503,
            detail="JWT_SECRET (or GRAVITY_JWT_SECRET) is not configured",
        )
    row = await db.fetchrow(
        """SELECT id, email, role FROM user_accounts WHERE lower(email) = lower($1)""",
        body.email.strip(),
    )
    if not row:
        raise HTTPException(
            status_code=404,
            detail="No user_accounts row for this email — insert one in Postgres first",
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
        """SELECT id, email, role, organization FROM user_accounts WHERE id = $1""",
        uid,
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": str(row["id"]),
        "email": row["email"],
        "role": row["role"],
        "organization": row["organization"],
    }


@router.get("/health")
async def auth_health():
    return {"auth": "ok"}
