import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from gravity_api.auth_deps import require_user_id
from gravity_api.database import get_db
from gravity_api.services.sport_query import cap_prefs_to_db_slugs

router = APIRouter()

# Match athlete_score_sync insert thresholds so the feed and the writer agree.
SCORE_MOVE_THRESHOLD = 3.0
NIL_P50_THRESHOLD = 250_000.0
RISK_FLAG_THRESHOLD = 65.0
ALERT_TYPES = ("SCORE_MOVE", "NIL_SIGNAL", "RISK_FLAG", "DEAL_DETECTED")


class MarkReadBody(BaseModel):
    alert_ids: list[str] = Field(default_factory=list)
    mark_all: bool = False


def _alert_type_from_reason(reason: str | None) -> str:
    raw = (reason or "").strip().upper()
    for kind in ALERT_TYPES:
        if raw.startswith(kind):
            return kind
    return "SCORE_MOVE"


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _item_from_event(row: Any) -> dict[str, Any]:
    r = dict(row)
    reason = r.get("trigger_reason") or "Score change"
    athlete_id = r.get("athlete_id")
    return {
        "id": str(r["id"]),
        "athlete_id": str(athlete_id) if athlete_id is not None else "",
        "athlete_name": r.get("athlete_name") or "Athlete",
        "school": r.get("school"),
        "sport": r.get("sport"),
        "previous_score": _num(r.get("previous_score")),
        "new_score": _num(r.get("new_score")),
        "delta": _num(r.get("delta")),
        "trigger_reason": reason,
        "alert_type": _alert_type_from_reason(str(reason)),
        "read": bool(r.get("read")),
        "created_at": _iso(r.get("created_at")),
        "source": "event",
    }


def _live_item(
    *,
    athlete_id: Any,
    athlete_name: str,
    school: str | None,
    sport: str | None,
    alert_type: str,
    reason: str,
    delta: float | None,
) -> dict[str, Any]:
    aid = str(athlete_id)
    return {
        "id": f"live:{alert_type}:{aid}",
        "athlete_id": aid,
        "athlete_name": athlete_name,
        "school": school,
        "sport": sport,
        "previous_score": None,
        "new_score": None,
        "delta": delta,
        "trigger_reason": f"{alert_type}: {reason}",
        "alert_type": alert_type,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "live",
    }


async def _derived_watchlist_alerts(
    db: asyncpg.Connection,
    uid: uuid.UUID,
    sports_db: Optional[List[str]],
    existing_keys: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    sport_clause = ""
    params: List[Any] = [uid]
    if sports_db:
        sport_clause = " AND a.sport = ANY($2::text[])"
        params.append(sports_db)
    rows = await db.fetch(
        f"""WITH wl AS (
                SELECT a.id AS athlete_id, a.name AS athlete_name, a.school, a.sport
                  FROM watchlists w
                  JOIN athletes a ON a.id = w.athlete_id
                 WHERE w.user_id = $1 {sport_clause}
            ),
            latest AS (
                SELECT DISTINCT ON (s.athlete_id)
                       s.athlete_id, s.gravity_score, s.dollar_p50_usd, s.risk_score, s.calculated_at
                  FROM athlete_gravity_scores s
                  JOIN wl ON wl.athlete_id = s.athlete_id
                 ORDER BY s.athlete_id, s.calculated_at DESC
            )
            SELECT wl.athlete_id, wl.athlete_name, wl.school, wl.sport,
                   latest.gravity_score, latest.dollar_p50_usd, latest.risk_score, latest.calculated_at,
                   (
                       SELECT s2.gravity_score
                         FROM athlete_gravity_scores s2
                        WHERE s2.athlete_id = wl.athlete_id
                          AND s2.calculated_at <= COALESCE(latest.calculated_at, NOW()) - INTERVAL '30 days'
                        ORDER BY s2.calculated_at DESC
                        LIMIT 1
                   ) AS past_gravity
              FROM wl
              LEFT JOIN latest ON latest.athlete_id = wl.athlete_id""",
        *params,
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        aid = str(row["athlete_id"])
        name = row["athlete_name"] or "Athlete"
        school = row["school"]
        sport = row["sport"]
        gravity = _num(row["gravity_score"])
        past = _num(row["past_gravity"])
        p50 = _num(row["dollar_p50_usd"])
        risk = _num(row["risk_score"])

        if gravity is not None and past is not None:
            delta = gravity - past
            if abs(delta) >= SCORE_MOVE_THRESHOLD and (aid, "SCORE_MOVE") not in existing_keys:
                out.append(
                    _live_item(
                        athlete_id=aid,
                        athlete_name=name,
                        school=school,
                        sport=sport,
                        alert_type="SCORE_MOVE",
                        reason=f"Gravity score moved {delta:+.1f} over ~30 days",
                        delta=round(delta, 1),
                    )
                )
                existing_keys.add((aid, "SCORE_MOVE"))
        if p50 is not None and p50 >= NIL_P50_THRESHOLD and (aid, "NIL_SIGNAL") not in existing_keys:
            out.append(
                _live_item(
                    athlete_id=aid,
                    athlete_name=name,
                    school=school,
                    sport=sport,
                    alert_type="NIL_SIGNAL",
                    reason=f"Model NIL P50 is ${p50:,.0f}",
                    delta=p50,
                )
            )
            existing_keys.add((aid, "NIL_SIGNAL"))
        if risk is not None and risk >= RISK_FLAG_THRESHOLD and (aid, "RISK_FLAG") not in existing_keys:
            out.append(
                _live_item(
                    athlete_id=aid,
                    athlete_name=name,
                    school=school,
                    sport=sport,
                    alert_type="RISK_FLAG",
                    reason=f"Risk composite is elevated ({risk:.0f})",
                    delta=risk,
                )
            )
            existing_keys.add((aid, "RISK_FLAG"))
    return out


async def _fetch_alerts(
    db: asyncpg.Connection,
    uid: uuid.UUID,
    sports_db: Optional[List[str]] = None,
) -> dict[str, Any]:
    sport_clause = ""
    params: List[Any] = [uid]
    if sports_db:
        sport_clause = " AND a.sport = ANY($2::text[])"
        params.append(sports_db)
    rows = await db.fetch(
        f"""SELECT sa.id, sa.user_id, sa.athlete_id, sa.previous_score, sa.new_score,
                   sa.delta, sa.trigger_reason, sa.read, sa.created_at,
                   a.name AS athlete_name, a.school, a.sport
              FROM score_alerts sa
              JOIN athletes a ON a.id = sa.athlete_id
              INNER JOIN watchlists w ON w.athlete_id = sa.athlete_id AND w.user_id = sa.user_id
             WHERE sa.user_id = $1 {sport_clause}
             ORDER BY sa.created_at DESC
             LIMIT 100""",
        *params,
    )
    items = [_item_from_event(r) for r in rows]
    existing_keys = {
        (str(it["athlete_id"]), str(it["alert_type"]))
        for it in items
    }
    items.extend(await _derived_watchlist_alerts(db, uid, sports_db, existing_keys))
    unread = sum(1 for it in items if not it["read"])
    return {"unread": unread, "items": items}


@router.get("")
@router.get("/", include_in_schema=False)
async def get_alerts(
    db: asyncpg.Connection = Depends(get_db),
    effective_user: uuid.UUID = Depends(require_user_id),
    sports: str | None = Query(
        None,
        description="Comma-separated CFB,NCAAB,NCAAW — filter alerts to athletes in those sports",
    ),
):
    sports_db = None
    if sports and sports.strip():
        sports_db = cap_prefs_to_db_slugs([s.strip() for s in sports.split(",") if s.strip()])
    return await _fetch_alerts(db, effective_user, sports_db=sports_db)


@router.post("/mark-read")
async def mark_alerts_read(
    body: MarkReadBody,
    db: asyncpg.Connection = Depends(get_db),
    effective_user: uuid.UUID = Depends(require_user_id),
):
    """Persist read state for score_alerts rows. Live (derived) ids are ignored."""
    if body.mark_all:
        await db.execute(
            "UPDATE score_alerts SET read = true WHERE user_id = $1 AND read IS NOT TRUE",
            effective_user,
        )
        return {"ok": True}
    ids: list[uuid.UUID] = []
    for raw in body.alert_ids:
        try:
            ids.append(uuid.UUID(raw))
        except ValueError:
            continue
    if ids:
        await db.execute(
            """UPDATE score_alerts
                  SET read = true
                WHERE user_id = $1 AND id = ANY($2::uuid[])""",
            effective_user,
            ids,
        )
    return {"ok": True}


@router.get("/{user_id}")
async def get_alerts_by_path(
    user_id: str,
    db: asyncpg.Connection = Depends(get_db),
    effective_user: uuid.UUID = Depends(require_user_id),
):
    """Path-style alias kept for legacy clients. Caller may only read their own alerts."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="user_id must be UUID") from e
    if uid != effective_user:
        raise HTTPException(status_code=403, detail="Cannot read alerts for another user")
    return await _fetch_alerts(db, uid, sports_db=None)
