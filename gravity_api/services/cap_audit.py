"""Append-only audit for CapIQ mutations."""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

import asyncpg


async def write_cap_audit_log(
    conn: asyncpg.Connection,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    table_name: str,
    record_id: uuid.UUID,
    action: str,
    old_values: Optional[dict[str, Any]] = None,
    new_values: Optional[dict[str, Any]] = None,
) -> None:
    await conn.execute(
        """INSERT INTO cap_audit_log (org_id, user_id, table_name, record_id, action, old_values, new_values)
           VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb)""",
        org_id,
        user_id,
        table_name,
        record_id,
        action,
        json.dumps(old_values) if old_values is not None else None,
        json.dumps(new_values) if new_values is not None else None,
    )
