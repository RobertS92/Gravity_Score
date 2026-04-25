"""Admin/scraper-only ingest endpoints.

External scrapers (and internal jobs) MUST write news through this router.
Direct INSERTs to ``athlete_events`` / ``team_events`` are forbidden going
forward — they bypass the trust pipeline.

Auth: same ``require_ops`` dependency as the scraper-jobs router — either
an admin JWT or the ``X-Internal-Key`` header matching
``GRAVITY_INTERNAL_API_KEY``.

Endpoints:
  POST /v1/ingest/athlete-event   — single event
  POST /v1/ingest/team-event      — single team event
  POST /v1/ingest/batch           — up to 50 mixed items at once
  GET  /v1/ingest/sources         — current allowlist (debugging)
  GET  /v1/ingest/rejections      — recent rejections (debugging)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from gravity_api.database import get_db
from gravity_api.routers.scraper_jobs import require_ops
from gravity_api.services.news_collector import (
    FEED_REGISTRY,
    collect_all,
    collect_feed,
    coverage_report,
)
from gravity_api.services.news_ingest import (
    IngestRejected,
    IngestResult,
    ingest_athlete_event,
    ingest_team_event,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class AthleteEventIn(BaseModel):
    athlete_id: uuid.UUID
    category: str = Field(..., max_length=32)
    title: str = Field(..., min_length=1, max_length=400)
    description: Optional[str] = None
    occurred_at: datetime
    published_at: Optional[datetime] = None
    source_url: str = Field(..., min_length=4, max_length=2000)
    article_text: Optional[str] = None
    extracted_claim: Optional[str] = None
    key_fact: Optional[str] = None
    is_official: bool = False
    require_llm: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    scraper_run_id: Optional[uuid.UUID] = None


class TeamEventIn(BaseModel):
    team_id: uuid.UUID
    category: str = Field(..., max_length=32)
    title: str = Field(..., min_length=1, max_length=400)
    body: Optional[str] = None
    occurred_at: datetime
    published_at: Optional[datetime] = None
    source_url: str = Field(..., min_length=4, max_length=2000)
    article_text: Optional[str] = None
    extracted_claim: Optional[str] = None
    key_fact: Optional[str] = None
    is_official: bool = False
    require_llm: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    scraper_run_id: Optional[uuid.UUID] = None


class BatchItem(BaseModel):
    kind: Literal["athlete_event", "team_event"]
    athlete: Optional[AthleteEventIn] = None
    team: Optional[TeamEventIn] = None


class BatchIn(BaseModel):
    items: list[BatchItem] = Field(..., max_length=50)


# ---------------------------------------------------------------------------
# Response shaping
# ---------------------------------------------------------------------------
def _result_payload(r: IngestResult) -> dict[str, Any]:
    return {
        "inserted": r.inserted,
        "event_id": str(r.event_id) if r.event_id else None,
        "verification": r.verification,
        "promoted_to_multi_source": r.promoted_to_multi_source,
        "rejected_reason": r.rejected_reason,
    }


# ---------------------------------------------------------------------------
# Single-item endpoints
# ---------------------------------------------------------------------------
@router.post("/athlete-event")
async def post_athlete_event(
    body: AthleteEventIn,
    db: asyncpg.Connection = Depends(get_db),
    _: uuid.UUID = Depends(require_ops),
):
    try:
        result = await ingest_athlete_event(
            db,
            athlete_id=body.athlete_id,
            category=body.category.upper(),
            title=body.title,
            description=body.description,
            occurred_at=body.occurred_at,
            published_at=body.published_at,
            source_url=body.source_url,
            article_text=body.article_text,
            extracted_claim=body.extracted_claim,
            key_fact=body.key_fact,
            is_official=body.is_official,
            require_llm=body.require_llm,
            metadata=body.metadata,
            scraper_run_id=body.scraper_run_id,
        )
    except IngestRejected as e:
        raise HTTPException(status_code=422, detail={"reason": e.reason, "detail": e.detail})
    return _result_payload(result)


@router.post("/team-event")
async def post_team_event(
    body: TeamEventIn,
    db: asyncpg.Connection = Depends(get_db),
    _: uuid.UUID = Depends(require_ops),
):
    try:
        result = await ingest_team_event(
            db,
            team_id=body.team_id,
            category=body.category.upper(),
            title=body.title,
            body=body.body,
            occurred_at=body.occurred_at,
            published_at=body.published_at,
            source_url=body.source_url,
            article_text=body.article_text,
            extracted_claim=body.extracted_claim,
            key_fact=body.key_fact,
            is_official=body.is_official,
            require_llm=body.require_llm,
            metadata=body.metadata,
            scraper_run_id=body.scraper_run_id,
        )
    except IngestRejected as e:
        raise HTTPException(status_code=422, detail={"reason": e.reason, "detail": e.detail})
    return _result_payload(result)


# ---------------------------------------------------------------------------
# Batch endpoint — never raises on per-item failure, returns per-item status.
# ---------------------------------------------------------------------------
@router.post("/batch")
async def post_batch(
    body: BatchIn,
    db: asyncpg.Connection = Depends(get_db),
    _: uuid.UUID = Depends(require_ops),
):
    out: list[dict[str, Any]] = []
    for item in body.items:
        try:
            if item.kind == "athlete_event":
                if not item.athlete:
                    out.append({"ok": False, "reason": "missing_athlete"})
                    continue
                a = item.athlete
                r = await ingest_athlete_event(
                    db,
                    athlete_id=a.athlete_id,
                    category=a.category.upper(),
                    title=a.title,
                    description=a.description,
                    occurred_at=a.occurred_at,
                    published_at=a.published_at,
                    source_url=a.source_url,
                    article_text=a.article_text,
                    extracted_claim=a.extracted_claim,
                    key_fact=a.key_fact,
                    is_official=a.is_official,
                    require_llm=a.require_llm,
                    metadata=a.metadata,
                    scraper_run_id=a.scraper_run_id,
                )
                out.append({"ok": True, **_result_payload(r)})
            elif item.kind == "team_event":
                if not item.team:
                    out.append({"ok": False, "reason": "missing_team"})
                    continue
                t = item.team
                r = await ingest_team_event(
                    db,
                    team_id=t.team_id,
                    category=t.category.upper(),
                    title=t.title,
                    body=t.body,
                    occurred_at=t.occurred_at,
                    published_at=t.published_at,
                    source_url=t.source_url,
                    article_text=t.article_text,
                    extracted_claim=t.extracted_claim,
                    key_fact=t.key_fact,
                    is_official=t.is_official,
                    require_llm=t.require_llm,
                    metadata=t.metadata,
                    scraper_run_id=t.scraper_run_id,
                )
                out.append({"ok": True, **_result_payload(r)})
            else:
                out.append({"ok": False, "reason": "unknown_kind"})
        except IngestRejected as e:
            out.append({"ok": False, "reason": e.reason, "detail": e.detail})
    return {"results": out}


# ---------------------------------------------------------------------------
# Inspection endpoints (admin-only)
# ---------------------------------------------------------------------------
@router.get("/sources")
async def list_sources(
    db: asyncpg.Connection = Depends(get_db),
    _: uuid.UUID = Depends(require_ops),
):
    rows = await db.fetch(
        "SELECT domain, display_name, tier, enabled FROM news_sources ORDER BY tier, domain"
    )
    return {"sources": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# News collection — pulls registered RSS feeds into the trust pipeline.
# ---------------------------------------------------------------------------
class CollectIn(BaseModel):
    """Optional restrictions for which feeds to run."""
    domains: Optional[list[str]] = None  # restrict to e.g. ['espn.com']
    use_llm: bool = True
    max_entries_per_feed: int = 50


@router.post("/collect")
async def collect_news(
    body: CollectIn = CollectIn(),
    db: asyncpg.Connection = Depends(get_db),
    _: uuid.UUID = Depends(require_ops),
):
    """Pull every registered RSS feed (optionally filtered) and route
    every entry through the trust pipeline."""
    feeds = FEED_REGISTRY
    if body.domains:
        wanted = set(d.lower() for d in body.domains)
        feeds = [f for f in FEED_REGISTRY if f.domain.lower() in wanted]
        if not feeds:
            raise HTTPException(
                status_code=400,
                detail=f"No registered feeds match domains={body.domains}",
            )
    stats = await collect_all(
        db,
        feeds=feeds,
        use_llm=body.use_llm,
        max_entries_per_feed=max(1, min(100, body.max_entries_per_feed)),
    )
    return {
        "feeds_processed": stats.feeds_processed,
        "entries_seen": stats.entries_seen,
        "inserted": stats.inserted,
        "duplicates": stats.duplicates,
        "rejected": stats.rejected,
        "unmatched": stats.unmatched,
        "by_category": stats.by_category,
        "by_source": stats.by_source,
        "errors": stats.errors[:20],
    }


@router.get("/feeds")
async def list_feeds(_: uuid.UUID = Depends(require_ops)):
    """Surface the configured feed registry so admins can audit which
    publishers feed which categories."""
    return {
        "feeds": [
            {
                "name": f.name,
                "domain": f.domain,
                "url": f.url,
                "default_category": f.default_category,
                "sport_hint": f.sport_hint,
                "description": f.description,
            }
            for f in FEED_REGISTRY
        ]
    }


@router.get("/coverage")
async def coverage(
    db: asyncpg.Connection = Depends(get_db),
    _: uuid.UUID = Depends(require_ops),
):
    """Per-category coverage: which categories have recent data and
    which are stale or have no feed configured."""
    return await coverage_report(db)


@router.get("/rejections")
async def list_rejections(
    limit: int = 100,
    db: asyncpg.Connection = Depends(get_db),
    _: uuid.UUID = Depends(require_ops),
):
    rows = await db.fetch(
        """SELECT id, athlete_id, team_id, attempted_category, attempted_title,
                  source_domain, source_url, reason, llm_response, created_at
             FROM extraction_rejections
            ORDER BY created_at DESC
            LIMIT $1""",
        max(1, min(500, limit)),
    )
    out = []
    for r in rows:
        d = dict(r)
        for k in ("id", "athlete_id", "team_id"):
            if d.get(k) is not None:
                d[k] = str(d[k])
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
        out.append(d)
    return {"rejections": out}
