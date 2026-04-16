"""Server-side agent completion (Anthropic key stays on API)."""

from typing import Any, Dict

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from gravity_api.database import get_db
from gravity_api.services.agents import GravityQueryAgent

router = APIRouter()


class AgentCompleteRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=16_000)
    context: Dict[str, Any] = Field(default_factory=dict)


@router.post("/complete")
async def agent_complete(
    body: AgentCompleteRequest,
    db: asyncpg.Connection = Depends(get_db),
):
    agent = GravityQueryAgent(db)
    result = await agent.run_sync(body.prompt, body.context or None)
    return {
        "text": result.get("response") or "",
        "query_type": result.get("query_type"),
        "athlete_ids": result.get("athlete_ids") or [],
    }
