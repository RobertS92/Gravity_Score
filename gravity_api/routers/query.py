import json
import logging
import uuid
from typing import Any, Dict

import asyncpg
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from gravity_api.auth_deps import require_user_id
from gravity_api.database import get_db
from gravity_api.services.agents import GravityQueryAgent

logger = logging.getLogger(__name__)
router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    # `user_id` is accepted for backward compat but is IGNORED — the
    # authoritative identity comes from the JWT bearer token.
    user_id: str | None = None
    context: Dict[str, Any] = Field(default_factory=dict)


@router.post("/stream")
async def stream_query(
    req: QueryRequest,
    db: asyncpg.Connection = Depends(get_db),
    effective_user: uuid.UUID = Depends(require_user_id),  # noqa: B008
):
    """SSE stream of agent steps for the terminal UI. Auth required."""

    async def generate():
        agent = GravityQueryAgent(db=db)
        async for chunk in agent.run(req.query, req.context):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("")
@router.post("/", include_in_schema=False)
async def run_query(
    req: QueryRequest,
    db: asyncpg.Connection = Depends(get_db),
    effective_user: uuid.UUID = Depends(require_user_id),
):
    """Non-streaming agent run + query_history insert. Auth required."""
    agent = GravityQueryAgent(db=db)
    result = await agent.run_sync(req.query, req.context)

    try:
        await db.execute(
            """INSERT INTO query_history
                (user_id, query_text, query_type, result_summary, athlete_ids_returned)
               VALUES ($1, $2, $3, $4, $5::jsonb)""",
            effective_user,
            req.query,
            result.get("query_type"),
            result.get("summary"),
            json.dumps(result.get("athlete_ids", [])),
        )
    except Exception as e:
        logger.warning("query_history insert failed: %s", e)

    return result
