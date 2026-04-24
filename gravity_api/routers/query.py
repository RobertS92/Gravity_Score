import json
import logging
import uuid
from typing import Any, Dict, Optional

import asyncpg
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from gravity_api.database import get_db
from gravity_api.services.agents import GravityQueryAgent

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_user_id(raw: str) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(raw)
    except (ValueError, TypeError):
        return None


class QueryRequest(BaseModel):
    query: str
    user_id: str
    context: Dict[str, Any] = Field(default_factory=dict)


@router.post("/stream")
async def stream_query(req: QueryRequest, db: asyncpg.Connection = Depends(get_db)):
    """SSE stream of agent steps for the terminal UI."""

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
async def run_query(req: QueryRequest, db: asyncpg.Connection = Depends(get_db)):
    """Non-streaming agent run + query_history insert."""
    agent = GravityQueryAgent(db=db)
    result = await agent.run_sync(req.query, req.context)

    uid = _parse_user_id(req.user_id)
    if uid:
        try:
            await db.execute(
                """INSERT INTO query_history
                    (user_id, query_text, query_type, result_summary, athlete_ids_returned)
                   VALUES ($1, $2, $3, $4, $5::jsonb)""",
                uid,
                req.query,
                result.get("query_type"),
                result.get("summary"),
                json.dumps(result.get("athlete_ids", [])),
            )
        except Exception as e:
            logger.warning("query_history insert failed: %s", e)
    else:
        logger.debug("Skipping query_history: user_id is not a UUID (%s)", req.user_id)

    return result
