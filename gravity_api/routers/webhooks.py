"""Stripe webhooks — verify signature in production."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/stripe")
async def stripe_webhook(request: Request):
    _ = await request.body()
    return {"received": True, "detail": "Verify Stripe-Signature via STRIPE_WEBHOOK_SECRET"}
