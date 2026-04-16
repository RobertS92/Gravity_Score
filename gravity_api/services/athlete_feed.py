"""Derive terminal feed events from scores and NIL deals."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, List

import asyncpg


def _iso(ts: Any) -> str:
    if ts is None:
        return datetime.utcnow().isoformat() + "Z"
    if isinstance(ts, datetime):
        return ts.isoformat()
    if isinstance(ts, date):
        return datetime.combine(ts, datetime.min.time()).isoformat() + "Z"
    return str(ts)


async def build_athlete_feed_events(
    db: asyncpg.Connection,
    athlete_id: str,
    athlete_name: str,
    *,
    deal_limit: int = 12,
    score_limit: int = 24,
) -> List[dict[str, Any]]:
    events: List[dict[str, Any]] = []

    deals = await db.fetch(
        """SELECT id, deal_value, brand_name, deal_type, deal_date, verified, ingested_at
           FROM athlete_nil_deals
           WHERE athlete_id = $1
           ORDER BY COALESCE(deal_date, ingested_at::date) DESC NULLS LAST, ingested_at DESC
           LIMIT $2""",
        athlete_id,
        deal_limit,
    )
    for d in deals:
        amt = d["deal_value"]
        body = (
            f"{'Verified ' if d.get('verified') else ''}NIL {d.get('deal_type') or 'deal'}"
            + (f" — ${float(amt):,.0f}" if amt is not None else "")
        )
        ts = _iso(d.get("deal_date") or d.get("ingested_at"))
        events.append(
            {
                "event_id": str(d["id"]),
                "athlete_id": athlete_id,
                "athlete_name": athlete_name,
                "event_type": "NIL_DEAL",
                "timestamp": ts,
                "body": body,
                "entity_name": d.get("brand_name"),
                "value": float(amt) if amt is not None else None,
            }
        )

    scores = await db.fetch(
        """SELECT gravity_score, brand_score, proof_score, proximity_score, velocity_score,
                  risk_score, calculated_at
           FROM athlete_gravity_scores
           WHERE athlete_id = $1
           ORDER BY calculated_at ASC
           LIMIT $2""",
        athlete_id,
        score_limit,
    )
    prev = None
    for row in scores:
        cur = dict(row)
        if prev is not None:
            g0 = float(prev["gravity_score"] or 0)
            g1 = float(cur["gravity_score"] or 0)
            if abs(g1 - g0) >= 0.5:
                ts = _iso(cur["calculated_at"])
                eid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"score-{athlete_id}-{ts}"))
                events.append(
                    {
                        "event_id": eid,
                        "athlete_id": athlete_id,
                        "athlete_name": athlete_name,
                        "event_type": "SCORE_UPDATE",
                        "timestamp": ts,
                        "body": f"Gravity score moved from {g0:.1f} to {g1:.1f}",
                        "entity_name": None,
                        "value": g1,
                    }
                )
            r0 = float(prev["risk_score"] or 0)
            r1 = float(cur["risk_score"] or 0)
            if abs(r1 - r0) >= 3.0:
                ts = _iso(cur["calculated_at"])
                eid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"risk-{athlete_id}-{ts}"))
                events.append(
                    {
                        "event_id": eid,
                        "athlete_id": athlete_id,
                        "athlete_name": athlete_name,
                        "event_type": "RISK",
                        "timestamp": ts,
                        "body": f"Risk component shifted from {r0:.1f} to {r1:.1f}",
                        "entity_name": None,
                        "value": r1,
                    }
                )
        prev = cur

    events.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
    return events
