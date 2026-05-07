"""Server-side agent completion + streaming + conversation persistence."""

import json
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List

import asyncpg
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from gravity_api.auth_deps import require_user_id
from gravity_api.database import get_db
from gravity_api.services.agents import GravityQueryAgent

router = APIRouter()


class AgentCompleteRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=16_000)
    context: Dict[str, Any] = Field(default_factory=dict)
    history: List[Dict[str, Any]] = Field(default_factory=list)


@router.post("/complete")
async def agent_complete(
    body: AgentCompleteRequest,
    db: asyncpg.Connection = Depends(get_db),
    effective_user: uuid.UUID = Depends(require_user_id),  # noqa: ARG001
):
    """Auth required: prevents anonymous use of the Anthropic budget."""
    agent = GravityQueryAgent(db)
    result = await agent.run_sync(body.prompt, body.context or None)
    return {
        "text": result.get("response") or "",
        "query_type": result.get("query_type"),
        "athlete_ids": result.get("athlete_ids") or [],
    }


@router.post("/stream")
async def agent_stream(
    body: AgentCompleteRequest,
    db: asyncpg.Connection = Depends(get_db),
    effective_user: uuid.UUID = Depends(require_user_id),  # noqa: ARG001
):
    """SSE endpoint with token-style chunks + [DONE] terminator."""

    async def generate() -> AsyncGenerator[str, None]:
        agent = GravityQueryAgent(db)
        result = await agent.run_sync(body.prompt, body.context or None)
        text = str(result.get("response") or "")
        if not text:
            yield "data: [DONE]\n\n"
            return
        chunk = 24
        for i in range(0, len(text), chunk):
            token = text[i : i + chunk].replace("\n", " ")
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class ConversationMessageIn(BaseModel):
    id: str
    role: str
    content: str
    timestamp: int


class ConversationIn(BaseModel):
    id: str
    title: str
    messages: List[ConversationMessageIn]
    contextAthleteId: str | None = None
    contextAthleteName: str | None = None
    createdAt: int
    updatedAt: int


class ConversationUpsertBody(BaseModel):
    user_id: str
    conversation: ConversationIn


async def _ensure_conversations_table(db: asyncpg.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
            conversation_id TEXT NOT NULL,
            title TEXT NOT NULL,
            messages_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            context_athlete_id TEXT,
            context_athlete_name TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (user_id, conversation_id)
        );
        """
    )


@router.get("/conversations")
async def list_conversations(
    user_id: str,
    db: asyncpg.Connection = Depends(get_db),
    effective_user: uuid.UUID = Depends(require_user_id),
):
    await _ensure_conversations_table(db)
    if str(effective_user) != str(user_id):
        return []
    rows = await db.fetch(
        """
        SELECT conversation_id, title, messages_json, context_athlete_id, context_athlete_name,
               created_at, updated_at
        FROM agent_conversations
        WHERE user_id = $1
        ORDER BY updated_at DESC
        LIMIT 50
        """,
        effective_user,
    )
    out = []
    for r in rows:
        out.append(
            {
                "id": r["conversation_id"],
                "title": r["title"],
                "messages": r["messages_json"] or [],
                "contextAthleteId": r["context_athlete_id"],
                "contextAthleteName": r["context_athlete_name"],
                "createdAt": int(r["created_at"].timestamp() * 1000),
                "updatedAt": int(r["updated_at"].timestamp() * 1000),
            }
        )
    return out


@router.post("/conversations")
async def upsert_conversation(
    body: ConversationUpsertBody,
    db: asyncpg.Connection = Depends(get_db),
    effective_user: uuid.UUID = Depends(require_user_id),
):
    await _ensure_conversations_table(db)
    if str(effective_user) != str(body.user_id):
        return {"ok": False, "error": "forbidden"}
    conv = body.conversation
    created_at = datetime.fromtimestamp(conv.createdAt / 1000.0)
    updated_at = datetime.fromtimestamp(conv.updatedAt / 1000.0)
    await db.execute(
        """
        INSERT INTO agent_conversations
            (user_id, conversation_id, title, messages_json, context_athlete_id, context_athlete_name, created_at, updated_at)
        VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8)
        ON CONFLICT (user_id, conversation_id)
        DO UPDATE SET
            title = EXCLUDED.title,
            messages_json = EXCLUDED.messages_json,
            context_athlete_id = EXCLUDED.context_athlete_id,
            context_athlete_name = EXCLUDED.context_athlete_name,
            updated_at = EXCLUDED.updated_at
        """,
        effective_user,
        conv.id,
        conv.title,
        json.dumps([m.model_dump() for m in conv.messages]),
        conv.contextAthleteId,
        conv.contextAthleteName,
        created_at,
        updated_at,
    )
    return {"ok": True}
