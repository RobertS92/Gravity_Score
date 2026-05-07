"""Roster lifecycle synchronization + score refresh helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg

from gravity_api.services.athlete_score_sync import sync_athlete_score_from_ml


@dataclass
class RosterLifecycleInput:
    athlete_id: str
    lifecycle_status: str = "active_on_roster"
    is_active: bool = True
    school: Optional[str] = None
    conference: Optional[str] = None
    sport: Optional[str] = None
    status_reason: Optional[str] = None


def _norm_text(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    t = str(v).strip()
    return t if t else None


async def _sync_scores_for_athletes(
    conn: asyncpg.Connection,
    athlete_ids: list[str],
) -> dict[str, Any]:
    ok = 0
    failed = 0
    failures: list[dict[str, str]] = []
    for athlete_id in athlete_ids:
        try:
            await sync_athlete_score_from_ml(conn, athlete_id)
            ok += 1
        except Exception as exc:  # pragma: no cover - network/ML failures are environment-dependent
            failed += 1
            failures.append({"athlete_id": athlete_id, "error": str(exc)})
    return {"ok": ok, "failed": failed, "failures": failures}


async def apply_roster_lifecycle_sync(
    conn: asyncpg.Connection,
    athletes: list[RosterLifecycleInput],
    *,
    sport_scope: Optional[str],
    verified_at: Optional[datetime],
    mode: str = "replace_scope",
    trigger_rescore: bool = True,
) -> dict[str, Any]:
    if mode not in {"replace_scope", "patch"}:
        raise ValueError("mode must be one of: replace_scope, patch")
    if mode == "replace_scope" and not sport_scope:
        raise ValueError("sport_scope is required when mode=replace_scope")

    ts = verified_at or datetime.now(timezone.utc)

    deduped: dict[str, RosterLifecycleInput] = {}
    for row in athletes:
        deduped[row.athlete_id] = row
    payload = list(deduped.values())
    athlete_ids = list(deduped.keys())

    existing_rows = await conn.fetch(
        """SELECT id, school, conference, sport, is_active
           FROM athletes
           WHERE id = ANY($1::uuid[])""",
        athlete_ids or [],
    )
    existing = {str(r["id"]): r for r in existing_rows}
    missing_ids = [aid for aid in athlete_ids if aid not in existing]

    changed_ids: list[str] = []
    reactivated_count = 0
    updates = 0
    deactivated_scope_count = 0
    status_counts: dict[str, int] = {
        "active_on_roster": 0,
        "transferred": 0,
        "left_for_draft": 0,
        "graduated": 0,
        "out_other": 0,
    }

    async with conn.transaction():
        for row in payload:
            prev = existing.get(row.athlete_id)
            if not prev:
                continue
            next_status = _norm_text(row.lifecycle_status) or "active_on_roster"
            if next_status not in status_counts:
                next_status = "out_other"
            status_counts[next_status] = status_counts.get(next_status, 0) + 1
            next_school = _norm_text(row.school)
            next_conference = _norm_text(row.conference)
            next_sport = _norm_text(row.sport)
            # Status is canonical. Allowing input is_active, but lifecycle outcomes win.
            if next_status in {"left_for_draft", "graduated", "out_other"}:
                next_active = False
            elif next_status in {"active_on_roster", "transferred"}:
                next_active = True
            else:
                next_active = bool(row.is_active)
            next_reason = _norm_text(row.status_reason)

            prev_active = prev["is_active"]
            changed = False
            if next_school is not None and next_school != prev["school"]:
                changed = True
            if next_conference is not None and next_conference != prev["conference"]:
                changed = True
            if next_sport is not None and next_sport != prev["sport"]:
                changed = True
            if prev_active is False and next_active:
                reactivated_count += 1
                changed = True
            if bool(prev_active is not False) != next_active:
                changed = True

            if not changed:
                await conn.execute(
                    """UPDATE athletes
                       SET roster_verified_at = $2,
                           roster_status = $3,
                           roster_status_reason = COALESCE($4, roster_status_reason),
                           roster_status_changed_at = CASE
                               WHEN roster_status IS DISTINCT FROM $3 THEN $2
                               ELSE roster_status_changed_at
                           END
                       WHERE id = $1::uuid""",
                    row.athlete_id,
                    ts,
                    next_status,
                    next_reason,
                )
                continue

            await conn.execute(
                """UPDATE athletes
                   SET school = COALESCE($2, school),
                       conference = COALESCE($3, conference),
                       sport = COALESCE($4, sport),
                       is_active = $5,
                       roster_verified_at = $6,
                       roster_status = $7,
                       roster_status_reason = $8,
                       roster_status_changed_at = $6,
                       updated_at = NOW()
                   WHERE id = $1::uuid""",
                row.athlete_id,
                next_school,
                next_conference,
                next_sport,
                next_active,
                ts,
                next_status,
                next_reason,
            )
            changed_ids.append(row.athlete_id)
            updates += 1

        if mode == "replace_scope" and sport_scope:
            result = await conn.execute(
                """UPDATE athletes
                   SET is_active = FALSE,
                       roster_verified_at = $3,
                       roster_status = 'out_other',
                       roster_status_reason = COALESCE(roster_status_reason, 'absent_from_authoritative_roster'),
                       roster_status_changed_at = $3,
                       updated_at = NOW()
                   WHERE sport = $1
                     AND id <> ALL($2::uuid[])
                     AND is_active IS DISTINCT FROM FALSE""",
                sport_scope,
                athlete_ids or [],
                ts,
            )
            deactivated_scope_count = int(result.split(" ")[-1]) if result else 0

    # Trigger fresh scoring only for active athletes with changed lifecycle/school context.
    rescore_candidates = [
        aid for aid in changed_ids if bool(deduped[aid].is_active)
    ]
    rescore = {"ok": 0, "failed": 0, "failures": []}
    if trigger_rescore and rescore_candidates:
        rescore = await _sync_scores_for_athletes(conn, rescore_candidates)

    return {
        "processed": len(payload),
        "matched": len(existing_rows),
        "missing_ids": missing_ids,
        "updated": updates,
        "reactivated": reactivated_count,
        "deactivated_out_of_scope": deactivated_scope_count,
        "status_counts": status_counts,
        "rescore": rescore,
        "verified_at": ts.isoformat(),
        "mode": mode,
        "sport_scope": sport_scope,
    }


async def backfill_active_athlete_scores(
    conn: asyncpg.Connection,
    *,
    limit: int = 250,
    sport: Optional[str] = None,
) -> dict[str, Any]:
    params: list[Any] = [limit]
    sport_clause = ""
    if sport:
        sport_clause = "AND a.sport = $2"
        params.append(sport)
    rows = await conn.fetch(
        f"""SELECT a.id
            FROM athletes a
            LEFT JOIN LATERAL (
                SELECT athlete_id
                FROM athlete_gravity_scores s
                WHERE s.athlete_id = a.id
                ORDER BY s.calculated_at DESC
                LIMIT 1
            ) latest ON true
            WHERE latest.athlete_id IS NULL
              AND (a.is_active IS TRUE)
              {sport_clause}
            ORDER BY a.updated_at DESC
            LIMIT $1""",
        *params,
    )
    athlete_ids = [str(r["id"]) for r in rows]
    res = await _sync_scores_for_athletes(conn, athlete_ids)
    return {
        "queued": len(athlete_ids),
        "scored_ok": res["ok"],
        "scored_failed": res["failed"],
        "failures": res["failures"],
    }
