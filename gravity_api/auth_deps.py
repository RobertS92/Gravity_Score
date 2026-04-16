"""Resolve user id from JWT Bearer or optional query param (legacy terminal)."""

from __future__ import annotations

import uuid
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from gravity_api.config import get_settings

_bearer = HTTPBearer(auto_error=False)


def decode_sub(token: str) -> Optional[uuid.UUID]:
    settings = get_settings()
    secret = settings.jwt_secret
    if not secret:
        return None
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[settings.jwt_algorithm],
        )
        sub = payload.get("sub")
        if not sub:
            return None
        return uuid.UUID(str(sub))
    except (jwt.PyJWTError, ValueError):
        return None


async def optional_user_id(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    user_id: Optional[str] = Query(None),
) -> Optional[uuid.UUID]:
    """Prefer JWT `sub`; fall back to `user_id` when allowed."""
    settings = get_settings()
    if creds and creds.scheme.lower() == "bearer" and creds.credentials:
        uid = decode_sub(creds.credentials)
        if uid:
            return uid
    if user_id:
        if settings.jwt_secret and not settings.allow_query_user_id:
            return None
        try:
            return uuid.UUID(user_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="user_id must be UUID") from e
    return None


async def require_user_id(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> uuid.UUID:
    if creds and creds.scheme.lower() == "bearer" and creds.credentials:
        uid = decode_sub(creds.credentials)
        if uid:
            return uid
    raise HTTPException(status_code=401, detail="Missing or invalid bearer token")
