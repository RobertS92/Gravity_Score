"""ESPN roster sync — upsert athletes, optional snapshots + transfer events."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timezone
from typing import Any, Awaitable, Callable

import asyncpg

from gravity_api.scrapers.clients.espn import EspnClient, normalize_sport
from gravity_api.scrapers.roster.roster_diff import SnapshotRow, compute_roster_changes
from gravity_api.scrapers.roster.school_index import (
    all_sports_in_index,
    default_team_ids_for_sport,
    schools_for_sport,
)

logger = logging.getLogger(__name__)

RescrapeFn = Callable[[asyncpg.Connection, str], Awaitable[None]]


def _default_season_year() -> str:
    v = (os.getenv("CURRENT_STATS_SEASON") or os.getenv("SCRAPE_SEASON") or "").strip()
    if v:
        return v.split("-")[0] if "-" in v else v
    return str(datetime.now(timezone.utc).year)


def _canonical_sport(sport: str) -> str:
    return normalize_sport(sport)


async def _table_exists(conn: asyncpg.Connection, table: str) -> bool:
    row = await conn.fetchval("SELECT to_regclass($1)", f"public.{table}")
    return row is not None


async def _find_athlete_by_espn(
    conn: asyncpg.Connection, espn_id: str
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """SELECT id, school, conference, sport, is_active, roster_status
           FROM athletes
           WHERE espn_id = $1
           LIMIT 1""",
        espn_id,
    )


async def sync_team_roster(
    conn: asyncpg.Connection,
    sport: str,
    espn_team_id: str,
    *,
    roster_season: str | None = None,
    snapshot_date: date | None = None,
    defer_snapshot: bool = False,
    snapshots_out: list[SnapshotRow] | None = None,
) -> dict[str, Any]:
    """Fetch one ESPN roster and upsert athletes (school = team display name)."""
    canonical = _canonical_sport(sport)
    season = roster_season or _default_season_year()
    snap_d = snapshot_date or date.today()
    now = datetime.now(timezone.utc)
    espn = EspnClient()

    payload = await espn.fetch_roster_payload(canonical, espn_team_id)
    if not payload:
        return {
            "sport": canonical,
            "espn_team_id": espn_team_id,
            "error": "empty_roster_payload",
        }

    team_block = payload.get("team") or {}
    team_name = team_block.get("displayName") or team_block.get("name") or ""
    conference = EspnClient.parse_team_conference({"team": team_block})
    if not conference:
        detail = await espn.fetch_team_detail(canonical, espn_team_id)
        conference = EspnClient.parse_team_conference(detail) if detail else None

    players = EspnClient.flatten_roster_players(payload)
    added = updated = transfers = 0
    errors: list[str] = []

    for item in players:
        try:
            ext_id = item.get("id")
            if ext_id is None:
                continue
            ext_id_s = str(ext_id)
            display = item.get("fullName") or item.get("displayName") or ""
            if not str(display).strip():
                continue

            pos = EspnClient.position_str(item)
            jersey_raw = EspnClient.jersey_str(item)
            exp = item.get("experience") or {}
            class_year = str(exp.get("displayValue") or "") or None
            height_in = item.get("height")
            weight_lb = item.get("weight")
            try:
                hi = int(float(height_in)) if height_in is not None else None
            except (TypeError, ValueError):
                hi = None
            try:
                wl = int(float(weight_lb)) if weight_lb is not None else None
            except (TypeError, ValueError):
                wl = None
            bp = item.get("birthPlace") or {}
            hometown = home_state = None
            if isinstance(bp, dict):
                city = bp.get("city")
                st = bp.get("state")
                if city or st:
                    hometown = ", ".join(p for p in (city, st) if p)
                if st:
                    home_state = str(st)

            existing = await _find_athlete_by_espn(conn, ext_id_s)
            jersey_int = None
            if jersey_raw:
                jm = re.search(r"(\d+)", str(jersey_raw))
                if jm:
                    jersey_int = int(jm.group(1))

            if existing:
                aid = str(existing["id"])
                old_school = existing.get("school")
                transfer_detected = bool(
                    old_school
                    and team_name
                    and str(old_school).strip() != str(team_name).strip()
                )
                if transfer_detected:
                    transfers += 1
                await conn.execute(
                    """UPDATE athletes SET
                         name = $2,
                         school = $3,
                         conference = COALESCE($4, conference),
                         position = COALESCE($5, position),
                         sport = $6,
                         espn_id = $7,
                         roster_verified_at = $8,
                         is_active = TRUE,
                         roster_status = CASE WHEN $9 THEN 'transferred' ELSE COALESCE(roster_status, 'active_on_roster') END,
                         roster_status_changed_at = CASE WHEN $9 THEN $8 ELSE roster_status_changed_at END,
                         class_year = COALESCE($10, class_year),
                         height_inches = COALESCE($11, height_inches),
                         weight_lbs = COALESCE($12, weight_lbs),
                         hometown = COALESCE($13, hometown),
                         home_state = COALESCE($14, home_state),
                         jersey_number = COALESCE($15::text, jersey_number),
                         updated_at = NOW()
                       WHERE id = $1::uuid""",
                    aid,
                    str(display).strip(),
                    team_name,
                    conference,
                    pos or None,
                    canonical,
                    ext_id_s,
                    now,
                    transfer_detected,
                    class_year,
                    hi,
                    wl,
                    hometown,
                    home_state,
                    str(jersey_int) if jersey_int is not None else None,
                )
                updated += 1
            else:
                row = await conn.fetchrow(
                    """INSERT INTO athletes (
                         name, school, conference, position, sport, espn_id,
                         roster_verified_at, is_active, roster_status,
                         class_year, height_inches, weight_lbs, hometown, home_state,
                         jersey_number
                       ) VALUES (
                         $1, $2, $3, $4, $5, $6,
                         $7, TRUE, 'active_on_roster',
                         $8, $9, $10, $11, $12, $13
                       )
                       ON CONFLICT (name, school, sport) DO UPDATE SET
                         espn_id = EXCLUDED.espn_id,
                         conference = EXCLUDED.conference,
                         position = EXCLUDED.position,
                         roster_verified_at = EXCLUDED.roster_verified_at,
                         is_active = TRUE,
                         updated_at = NOW()
                       RETURNING id""",
                    str(display).strip(),
                    team_name,
                    conference or "Unknown",
                    pos or None,
                    canonical,
                    ext_id_s,
                    now,
                    class_year,
                    hi,
                    wl,
                    hometown,
                    home_state,
                    str(jersey_int) if jersey_int is not None else None,
                )
                if not row:
                    errors.append(f"upsert failed for espn id {ext_id_s}")
                    continue
                aid = str(row["id"])
                added += 1

            snap_row = SnapshotRow(
                athlete_id=aid,
                espn_athlete_id=ext_id_s,
                espn_team_id=espn_team_id,
                team=team_name,
                conference=str(conference or ""),
                sport=canonical,
                position=pos or None,
                class_year=class_year,
                jersey_number=jersey_raw,
            )
            if defer_snapshot and snapshots_out is not None:
                snapshots_out.append(snap_row)
            elif await _table_exists(conn, "roster_snapshots"):
                await conn.execute(
                    """INSERT INTO roster_snapshots (
                         athlete_id, espn_athlete_id, team, conference, espn_team_id,
                         sport, snapshot_date, position, class_year, jersey_number
                       ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                       ON CONFLICT DO NOTHING""",
                    aid,
                    ext_id_s,
                    team_name,
                    str(conference or ""),
                    espn_team_id,
                    canonical,
                    snap_d,
                    pos or None,
                    class_year,
                    jersey_raw,
                )
        except Exception as exc:
            errors.append(f"player {item.get('id')}: {exc}")
            logger.exception("Roster row failed")

    return {
        "sport": canonical,
        "espn_team_id": espn_team_id,
        "team_name": team_name,
        "players_seen": len(players),
        "added": added,
        "updated": updated,
        "transfers_flagged": transfers,
        "roster_season": season,
        "errors": errors,
    }


async def _load_prev_snapshots(
    conn: asyncpg.Connection, sport: str, before: date
) -> tuple[date | None, list[SnapshotRow]]:
    if not await _table_exists(conn, "roster_snapshots"):
        return None, []
    prev_d = await conn.fetchval(
        """SELECT snapshot_date FROM roster_snapshots
           WHERE sport = $1 AND snapshot_date < $2
           ORDER BY snapshot_date DESC LIMIT 1""",
        sport,
        before,
    )
    if not prev_d:
        return None, []
    rows = await conn.fetch(
        """SELECT athlete_id, espn_athlete_id, espn_team_id, team, conference, sport,
                  position, class_year, jersey_number
           FROM roster_snapshots
           WHERE sport = $1 AND snapshot_date = $2""",
        sport,
        prev_d,
    )
    out = [
        SnapshotRow(
            athlete_id=str(r["athlete_id"]),
            espn_athlete_id=str(r["espn_athlete_id"]),
            espn_team_id=str(r["espn_team_id"]),
            team=str(r["team"] or ""),
            conference=str(r["conference"] or ""),
            sport=str(r["sport"] or sport),
            position=r.get("position"),
            class_year=r.get("class_year"),
            jersey_number=r.get("jersey_number"),
        )
        for r in rows
    ]
    return prev_d, out


async def _insert_roster_event(
    conn: asyncpg.Connection, ev: dict[str, Any], occurred_at: datetime
) -> None:
    if not await _table_exists(conn, "athlete_events"):
        return
    await conn.execute(
        """INSERT INTO athlete_events (
             athlete_id, event_type, title, description, event_source, event_data, occurred_at
           ) VALUES ($1::uuid, $2, $3, $4, $5, $6::jsonb, $7)""",
        ev["athlete_id"],
        ev["event_type"],
        ev["title"],
        ev.get("description"),
        ev.get("source", "ROSTER_DIFF"),
        json.dumps(ev.get("metadata") or {}),
        occurred_at,
    )


async def sync_sport_rosters(
    conn: asyncpg.Connection,
    sport: str,
    team_ids: list[str],
    *,
    roster_season: str | None = None,
    rescrape_transfers: RescrapeFn | None = None,
) -> dict[str, Any]:
    """Sync all teams for one sport, diff snapshots, optionally rescrape transfers."""
    canonical = _canonical_sport(sport)
    snap_d = date.today()
    current: list[SnapshotRow] = []
    results: list[dict[str, Any]] = []

    for tid in team_ids:
        tid = tid.strip()
        if not tid:
            continue
        try:
            results.append(
                await sync_team_roster(
                    conn,
                    canonical,
                    tid,
                    roster_season=roster_season,
                    snapshot_date=snap_d,
                    defer_snapshot=True,
                    snapshots_out=current,
                )
            )
        except Exception as exc:
            logger.exception("Roster sync failed for team %s", tid)
            results.append({"sport": canonical, "espn_team_id": tid, "error": str(exc)})

    prev_d, prev_rows = await _load_prev_snapshots(conn, canonical, snap_d)
    diff = compute_roster_changes(prev_rows, current, as_of=snap_d)
    occurred_at = datetime.now(timezone.utc)
    event_counts = {k: 0 for k in diff}

    for kind, lst in diff.items():
        for ev in lst:
            try:
                await _insert_roster_event(conn, ev, occurred_at)
                event_counts[kind] += 1
                if kind == "TRANSFER_COMPLETED":
                    meta = ev.get("metadata") or {}
                    await conn.execute(
                        """UPDATE athletes SET
                             school = COALESCE($2, school),
                             conference = COALESCE($3, conference),
                             roster_status = 'transferred',
                             roster_status_changed_at = $4,
                             is_active = TRUE,
                             updated_at = NOW()
                           WHERE id = $1::uuid""",
                        ev["athlete_id"],
                        meta.get("to_team"),
                        meta.get("to_conference"),
                        occurred_at,
                    )
                elif kind == "ROSTER_DEPARTURE":
                    await conn.execute(
                        """UPDATE athletes SET
                             is_active = FALSE,
                             roster_status = 'out_other',
                             roster_status_changed_at = $2,
                             updated_at = NOW()
                           WHERE id = $1::uuid""",
                        ev["athlete_id"],
                        occurred_at,
                    )
                elif kind == "ROSTER_ADDITION":
                    meta = ev.get("metadata") or {}
                    await conn.execute(
                        """UPDATE athletes SET
                             is_active = TRUE,
                             roster_status = 'active_on_roster',
                             roster_status_changed_at = $2,
                             school = COALESCE($3, school),
                             conference = COALESCE($4, conference),
                             updated_at = NOW()
                           WHERE id = $1::uuid""",
                        ev["athlete_id"],
                        occurred_at,
                        meta.get("team"),
                        meta.get("conference"),
                    )
            except Exception as exc:
                logger.warning("roster diff event failed: %s", exc)

    if await _table_exists(conn, "roster_snapshots"):
        for row in current:
            try:
                await conn.execute(
                    """INSERT INTO roster_snapshots (
                         athlete_id, espn_athlete_id, team, conference, espn_team_id,
                         sport, snapshot_date, position, class_year, jersey_number
                       ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                       ON CONFLICT DO NOTHING""",
                    row.athlete_id,
                    row.espn_athlete_id,
                    row.team,
                    row.conference,
                    row.espn_team_id,
                    row.sport,
                    snap_d,
                    row.position,
                    row.class_year,
                    row.jersey_number,
                )
            except Exception as exc:
                logger.debug("snapshot insert skipped: %s", exc)

    if rescrape_transfers:
        for ev in diff.get("TRANSFER_COMPLETED", []):
            try:
                await rescrape_transfers(conn, ev["athlete_id"])
            except Exception:
                logger.exception("post-transfer rescrape failed for %s", ev["athlete_id"])

    return {
        "sport": canonical,
        "snapshot_date": snap_d.isoformat(),
        "previous_snapshot_date": prev_d.isoformat() if prev_d else None,
        "team_results": results,
        "diff_event_counts": event_counts,
        "snapshots_written": len(current),
    }


async def sync_power5_sports(
    conn: asyncpg.Connection,
    sports: list[str] | None = None,
    *,
    roster_season: str | None = None,
    rescrape_transfers: RescrapeFn | None = None,
) -> list[dict[str, Any]]:
    want = sports or all_sports_in_index()
    out: list[dict[str, Any]] = []
    for sp in want:
        ids = default_team_ids_for_sport(sp)
        if not ids:
            schools = schools_for_sport(sp)
            ids = [str(s["espn_team_id"]) for s in schools]
        if not ids:
            logger.warning("No team ids for sport %s — set ROSTER_SYNC_DEFAULT_TEAM_IDS", sp)
            continue
        out.append(
            await sync_sport_rosters(
                conn,
                sp,
                ids,
                roster_season=roster_season,
                rescrape_transfers=rescrape_transfers,
            )
        )
    return out
