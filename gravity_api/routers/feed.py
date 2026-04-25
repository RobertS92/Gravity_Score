"""Unified live feed for the terminal.

GET /v1/feed
  ?categories=NIL_DEAL,SCORE_UPDATE,...   filter by category (default = all)
  &sources=watchlist,teams,general        which buckets to include
  &sports=CFB,NCAAB,NCAAW                 sport scope (default = all user's)
  &before=<iso8601>                       cursor — only items strictly older
  &limit=50                               1..100, default 50

The handler is auth-gated; the user_id from the JWT is the only identity
used to resolve watchlist + favorited teams.
"""

from __future__ import annotations

import uuid
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from gravity_api.auth_deps import require_user_id
from gravity_api.database import get_db
from gravity_api.services.feed import (
    ALLOWED_CATEGORIES,
    ALLOWED_SOURCES,
    _normalize_categories,
    _normalize_sources,
    build_feed,
)

router = APIRouter()


def _csv(raw: Optional[str]) -> Optional[list[str]]:
    if raw is None:
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts or None


@router.get("")
@router.get("/", include_in_schema=False)
async def get_feed(
    categories: Optional[str] = Query(
        None,
        description=f"CSV of categories. Allowed: {sorted(ALLOWED_CATEGORIES)}",
    ),
    sources: Optional[str] = Query(
        None,
        description=f"CSV of sources. Allowed: {sorted(ALLOWED_SOURCES)}. Default = watchlist,teams.",
    ),
    sports: Optional[str] = Query(
        None,
        description="CSV of UI sport codes (CFB, NCAAB, NCAAW). Default = all user's active sports.",
    ),
    before: Optional[str] = Query(
        None,
        description="ISO8601 cursor — return only items occurred strictly before this.",
    ),
    limit: int = Query(50, ge=1, le=100),
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    cat_list = _normalize_categories(_csv(categories))
    src_set = _normalize_sources(_csv(sources))
    sport_list_raw = _csv(sports)

    # Map UI sport codes to athlete-side slugs (cfb / mcbb).
    athlete_sport_slugs: Optional[list[str]] = None
    if sport_list_raw:
        from gravity_api.services.sport_query import cap_prefs_to_db_slugs

        athlete_sport_slugs = cap_prefs_to_db_slugs(sport_list_raw)

    if before:
        # Validate ISO; let FastAPI surface a 400 if malformed.
        try:
            from datetime import datetime

            datetime.fromisoformat(before.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(status_code=400, detail="`before` must be ISO8601") from e

    return await build_feed(
        db,
        user_id=user_id,
        sources=src_set,
        categories=cat_list,
        sports=athlete_sport_slugs,
        before_iso=before,
        limit=limit,
    )


@router.get("/categories", include_in_schema=True)
async def list_feed_categories():
    """Static enum used by the UI to render category toggles."""
    return {
        "categories": sorted(ALLOWED_CATEGORIES),
        "sources": sorted(ALLOWED_SOURCES),
    }
