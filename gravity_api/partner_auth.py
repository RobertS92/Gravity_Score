"""Partner API authentication and rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Optional

import asyncpg
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from gravity_api.config import get_settings
from gravity_api.database import get_db
from gravity_api.partner_types import PartnerContext
from gravity_api.services.partner_api import resolve_partner_context

_bearer = HTTPBearer(auto_error=False)

_rate_windows: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(key_id: str, limit_per_minute: int) -> None:
    now = time.monotonic()
    window = _rate_windows[key_id]
    cutoff = now - 60.0
    while window and window[0] < cutoff:
        window.pop(0)
    if len(window) >= limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail="Partner API rate limit exceeded",
            headers={"Retry-After": "60"},
        )
    window.append(now)


def _origin_allowed(origin: str | None, allowed: Optional[tuple[str, ...]]) -> bool:
    if not allowed:
        return True
    if not origin:
        return True
    return origin in allowed


def require_scope(partner: PartnerContext, scope: str) -> None:
    if scope not in partner.scopes:
        raise HTTPException(status_code=403, detail=f"Missing scope: {scope}")


async def require_partner(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: asyncpg.Connection = Depends(get_db),
) -> PartnerContext:
    settings = get_settings()
    bootstrap = (settings.partner_api_key or "").strip()
    if not bootstrap:
        try:
            has_table = await db.fetchval("SELECT to_regclass('public.partner_api_keys')")
        except asyncpg.PostgresError:
            has_table = None
        if not has_table:
            raise HTTPException(
                status_code=503,
                detail="Partner API not configured (set GRAVITY_PARTNER_API_KEY or apply migration 033)",
            )

    if not creds or creds.scheme.lower() != "bearer" or not creds.credentials:
        raise HTTPException(status_code=401, detail="Missing Bearer API key")

    raw_key = creds.credentials.strip()
    ctx = await resolve_partner_context(db, raw_key)
    if not ctx:
        raise HTTPException(status_code=403, detail="Invalid API key")

    origin = request.headers.get("origin")
    if not _origin_allowed(origin, ctx.allowed_origins):
        raise HTTPException(status_code=403, detail="Origin not allowed for this API key")

    rate_key = str(ctx.partner_id or ctx.partner_name)
    _check_rate_limit(rate_key, ctx.rate_limit_per_minute)

    if ctx.partner_id is not None:
        await db.execute(
            "UPDATE partner_api_keys SET last_used_at = NOW() WHERE id = $1",
            ctx.partner_id,
        )

    return ctx
