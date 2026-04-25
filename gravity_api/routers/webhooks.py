"""Stripe webhooks — signature-verified.

Implements the standard Stripe webhook contract:
- Validates `Stripe-Signature` against `STRIPE_WEBHOOK_SECRET` (HMAC-SHA256
  with a 5-minute tolerance window) without requiring the `stripe` SDK.
- Persists every accepted event into `stripe_webhook_events` for idempotency
  + audit. The handler is intentionally narrow: we record the event and
  trust downstream workers (or follow-up endpoints) to drive business logic
  off the same table.

Returning 4xx/5xx tells Stripe to retry. We only return 200 after the
event is durably stored or recognized as a duplicate.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from gravity_api.config import get_settings
from gravity_api.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

# Stripe's recommended replay-protection window.
_TOLERANCE_SECONDS = 5 * 60


def _verify_stripe_signature(
    payload: bytes,
    sig_header: str,
    secret: str,
    *,
    tolerance: int = _TOLERANCE_SECONDS,
) -> int:
    """Verify the Stripe-Signature header. Returns the timestamp on success.

    The header format is: `t=<unix>,v1=<hex>,v1=<hex>...`. We accept the
    request if at least one v1 hex matches HMAC-SHA256(secret, "{t}.{payload}")
    AND the signed timestamp is within `tolerance` of now.
    """
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    timestamp: int | None = None
    signatures: list[str] = []
    for piece in sig_header.split(","):
        piece = piece.strip()
        if not piece or "=" not in piece:
            continue
        key, _, value = piece.partition("=")
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                pass
        elif key == "v1":
            signatures.append(value)

    if timestamp is None or not signatures:
        raise HTTPException(status_code=400, detail="Malformed Stripe-Signature header")

    if abs(int(time.time()) - timestamp) > tolerance:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, sig) for sig in signatures):
        raise HTTPException(status_code=400, detail="Stripe signature mismatch")

    return timestamp


async def _ensure_events_table(db: asyncpg.Connection) -> None:
    """Idempotent schema bootstrap so the webhook works even if a migration
    hasn't been applied yet. Real schema is owned by migrations later."""
    await db.execute(
        """CREATE TABLE IF NOT EXISTS stripe_webhook_events (
            id              TEXT PRIMARY KEY,
            type            TEXT NOT NULL,
            api_version     TEXT,
            livemode        BOOLEAN,
            received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            payload         JSONB NOT NULL,
            handled_at      TIMESTAMPTZ
        )"""
    )


async def _record_event(db: asyncpg.Connection, event: dict[str, Any]) -> bool:
    """Insert the event; return True if newly inserted, False if duplicate."""
    event_id = event.get("id")
    if not event_id:
        raise HTTPException(status_code=400, detail="Stripe event missing id")
    result = await db.execute(
        """INSERT INTO stripe_webhook_events
                (id, type, api_version, livemode, payload)
           VALUES ($1, $2, $3, $4, $5::jsonb)
           ON CONFLICT (id) DO NOTHING""",
        event_id,
        event.get("type") or "unknown",
        event.get("api_version"),
        bool(event.get("livemode")),
        json.dumps(event),
    )
    # asyncpg returns "INSERT 0 1" for inserted, "INSERT 0 0" for skipped.
    return result.endswith(" 1")


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
):
    settings = get_settings()
    secret = settings.stripe_webhook_secret
    if not secret:
        # Without a secret we cannot verify authenticity. Reject loudly so
        # this is caught in deployment instead of silently accepting traffic.
        logger.error("STRIPE_WEBHOOK_SECRET not configured; rejecting webhook")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook not configured",
        )

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    _verify_stripe_signature(payload, sig_header, secret)

    try:
        event = json.loads(payload)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from e

    await _ensure_events_table(db)
    inserted = await _record_event(db, event)

    event_type = event.get("type") or "unknown"
    logger.info(
        "stripe webhook accepted: id=%s type=%s livemode=%s new=%s",
        event.get("id"),
        event_type,
        bool(event.get("livemode")),
        inserted,
    )

    # 200 with a small body — Stripe stops retrying on any 2xx.
    return {"received": True, "id": event.get("id"), "type": event_type, "duplicate": not inserted}
