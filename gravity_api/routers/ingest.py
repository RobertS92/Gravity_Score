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

import json
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
from gravity_api.services.feature_snapshots_v2 import materialize_feature_snapshot

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


class ObservationIn(BaseModel):
    entity_type: Literal["athlete", "team", "brand", "campaign"]
    entity_id: uuid.UUID
    feature_key: str = Field(..., min_length=1, max_length=128)
    numeric_value: Optional[float] = None
    text_value: Optional[str] = None
    json_value: Optional[dict[str, Any] | list[Any]] = None
    observed_at: datetime
    source_key: str = Field(..., min_length=1, max_length=128)
    source_record_id: Optional[str] = Field(default=None, max_length=300)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    verification_status: Literal[
        "verified", "corroborated", "single_source", "unverified", "rejected"
    ] = "unverified"
    freshness_seconds: Optional[int] = Field(default=None, ge=0)
    collection_run_id: Optional[str] = Field(default=None, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObservationBatchIn(BaseModel):
    observations: list[ObservationIn] = Field(..., min_length=1, max_length=500)


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


@router.post("/observations")
async def post_observations(
    body: ObservationBatchIn,
    db: asyncpg.Connection = Depends(get_db),
    _: uuid.UUID = Depends(require_ops),
):
    """Upsert field-level observations with source lineage and observed time."""
    inserted = 0
    rejected: list[dict[str, Any]] = []
    for index, item in enumerate(body.observations):
        if (
            item.numeric_value is None
            and item.text_value is None
            and item.json_value is None
        ):
            rejected.append({"index": index, "reason": "missing_value"})
            continue
        source = await db.fetchrow(
            """SELECT id, default_confidence FROM gravity_data_sources
               WHERE source_key = $1 AND active = TRUE""",
            item.source_key,
        )
        if not source:
            rejected.append({"index": index, "reason": "unknown_source"})
            continue
        confidence = (
            item.confidence
            if item.confidence is not None
            else float(source["default_confidence"])
        )
        await db.execute(
            """INSERT INTO gravity_observations (
                 entity_type, entity_id, feature_key, numeric_value, text_value,
                 json_value, observed_at, source_id, source_record_id, confidence,
                 verification_status, freshness_seconds, collection_run_id, metadata
               ) VALUES (
                 $1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11, $12, $13, $14::jsonb
               )
               ON CONFLICT (
                 entity_type, entity_id, feature_key, source_id, source_record_id
               ) WHERE source_record_id IS NOT NULL
               DO UPDATE SET
                 numeric_value = EXCLUDED.numeric_value,
                 text_value = EXCLUDED.text_value,
                 json_value = EXCLUDED.json_value,
                 observed_at = EXCLUDED.observed_at,
                 ingested_at = NOW(),
                 confidence = EXCLUDED.confidence,
                 verification_status = EXCLUDED.verification_status,
                 freshness_seconds = EXCLUDED.freshness_seconds,
                 collection_run_id = EXCLUDED.collection_run_id,
                 metadata = EXCLUDED.metadata""",
            item.entity_type,
            item.entity_id,
            item.feature_key,
            item.numeric_value,
            item.text_value,
            json.dumps(item.json_value) if item.json_value is not None else None,
            item.observed_at,
            source["id"],
            item.source_record_id,
            confidence,
            item.verification_status,
            item.freshness_seconds,
            item.collection_run_id,
            json.dumps(item.metadata),
        )
        inserted += 1
    return {"inserted": inserted, "rejected": rejected}


@router.post("/snapshots/{entity_type}/{entity_id}")
async def post_feature_snapshot(
    entity_type: Literal["athlete", "team", "brand"],
    entity_id: uuid.UUID,
    as_of: Optional[datetime] = None,
    db: asyncpg.Connection = Depends(get_db),
    _: uuid.UUID = Depends(require_ops),
):
    return await materialize_feature_snapshot(
        db,
        entity_type=entity_type,
        entity_id=str(entity_id),
        as_of=as_of,
    )


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
