"""Champion/challenger model registry operations."""

from __future__ import annotations

from typing import Any

import asyncpg


async def list_models(conn: asyncpg.Connection, model_key: str | None = None) -> list[dict[str, Any]]:
    if model_key:
        rows = await conn.fetch(
            """SELECT * FROM gravity_model_registry
               WHERE model_key = $1 ORDER BY created_at DESC""",
            model_key,
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM gravity_model_registry ORDER BY model_key, created_at DESC"
        )
    return [dict(row) for row in rows]


async def promote_model(
    conn: asyncpg.Connection,
    model_key: str,
    model_version: str,
) -> dict[str, Any]:
    async with conn.transaction():
        candidate = await conn.fetchrow(
            """SELECT * FROM gravity_model_registry
               WHERE model_key = $1 AND model_version = $2
               FOR UPDATE""",
            model_key,
            model_version,
        )
        if not candidate:
            raise ValueError("Model version not found")
        if candidate["stage"] not in {"candidate", "shadow", "champion"}:
            raise ValueError(f"Model in stage {candidate['stage']} cannot be promoted")
        await conn.execute(
            """UPDATE gravity_model_registry SET stage = 'retired'
               WHERE model_key = $1 AND stage = 'champion' AND model_version <> $2""",
            model_key,
            model_version,
        )
        promoted = await conn.fetchrow(
            """UPDATE gravity_model_registry SET stage = 'champion'
               WHERE model_key = $1 AND model_version = $2
               RETURNING *""",
            model_key,
            model_version,
        )
    return dict(promoted)


__all__ = ["list_models", "promote_model"]
