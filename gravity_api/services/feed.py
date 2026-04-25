"""Unified live-feed query.

Composes a single time-ordered stream of items from:
  - athlete_events     (athlete-level signals — score moves, injuries, etc.)
  - athlete_nil_deals  (deals — synthesized into NIL_DEAL items)
  - team_events        (team-level news / recruiting / rankings)

For a given authenticated user the feed honors three optional source
buckets:
  - watchlist : items where athlete_id is on the user's watchlist
  - teams     : items where the athlete's (school, sport) — or the team
                event's team_id — is one of the user's favorited teams
  - general   : items in any of the user's active sports, regardless of
                watchlist/favorites (top items only)

Categories are filtered post-hoc using the normalized `category` column
on athlete_events / team_events.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import asyncpg


def _parse_before(iso: Optional[str]) -> Optional[datetime]:
    """asyncpg requires a datetime instance for timestamptz binds (won't accept
    str). Accept the API cursor as ISO-8601 and return a tz-aware datetime."""
    if not iso:
        return None
    s = iso.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _jsonb_to_obj(v: Any) -> Optional[dict[str, Any] | list[Any]]:
    """asyncpg returns JSONB columns as plain strings unless a codec is set.

    Accept either str or already-decoded dict/list and return a Python obj
    (or None on parse failure / empty)."""
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return v
    if isinstance(v, (bytes, bytearray)):
        v = v.decode("utf-8", errors="replace")
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except (ValueError, TypeError):
            return None
    return None

# Single source of truth for category names exposed over the wire.
# Order matters: this is the order chips render in the UI.
CATALOG_CATEGORIES = [
    "NIL_DEAL",       # NIL & brand endorsement deals
    "TRANSFER",       # transfer portal moves
    "INJURY",         # injuries / clearances
    "NEWS",           # general news / mentions
    "AWARD",          # awards / honors / all-conference
    "RECRUITING",     # commits / decommits / recruit ranking changes
    "PERFORMANCE",    # game stats / spikes
    "ANNOUNCEMENT",   # official program / league announcements
    "BUSINESS",       # collective deals, conference moves, revenue
    "INCIDENT",       # suspensions / controversies / legal
    "SCORE",          # gravity score updates
    "ROSTER",         # roster additions
    "SOCIAL",         # social media spikes
    "RANKING",        # team / poll rankings
    "RISK",           # risk-related events
    "OTHER",          # fallback
]

ALLOWED_CATEGORIES = set(CATALOG_CATEGORIES)

# Categories the "general" bucket shows by default when the caller has not
# pinned an explicit category filter.  We deliberately drop ROSTER, SOCIAL,
# SCORE, RANKING, RISK, OTHER because they are high-volume / low-signal —
# they would drown out NIL deals, big news, transfers, and incidents.
DEFAULT_GENERAL_CATEGORIES = [
    "NIL_DEAL",
    "TRANSFER",
    "INJURY",
    "NEWS",
    "AWARD",
    "RECRUITING",
    "PERFORMANCE",
    "ANNOUNCEMENT",
    "BUSINESS",
    "INCIDENT",
]

ALLOWED_SOURCES = {"watchlist", "teams", "general"}


def _normalize_categories(raw: Optional[Iterable[str]]) -> Optional[list[str]]:
    if not raw:
        return None
    out: list[str] = []
    for c in raw:
        u = str(c).strip().upper()
        if u in ALLOWED_CATEGORIES:
            out.append(u)
    return out or None


def _normalize_sources(raw: Optional[Iterable[str]]) -> set[str]:
    if not raw:
        return {"watchlist", "teams"}
    out = {str(s).strip().lower() for s in raw}
    out &= ALLOWED_SOURCES
    return out or {"watchlist", "teams"}


def _athlete_sport_to_team_sport(sport_code: str) -> list[str]:
    """Map an athletes.sport DB value to the equivalent teams.sport slugs.

    athletes use 'cfb' / 'mcbb' (men's college basketball) but teams have
    'cfb' / 'ncaab_mens' / 'ncaab_womens'. We return all team slugs that
    share a roster with the athlete sport.
    """
    s = (sport_code or "").lower()
    if s == "cfb":
        return ["cfb"]
    if s in ("mcbb", "ncaab", "ncaab_mens"):
        return ["ncaab_mens"]
    if s in ("wcbb", "ncaaw", "ncaab_womens"):
        return ["ncaab_womens"]
    return [s]


async def _favorited_team_athlete_ids(
    db: asyncpg.Connection, user_id: uuid.UUID
) -> list[uuid.UUID]:
    """All athlete ids on the rosters of the user's favorited teams."""
    rows = await db.fetch(
        """SELECT a.id
           FROM athletes a
           JOIN teams t ON t.school_name = a.school
           JOIN team_favorites tf ON tf.team_id = t.id AND tf.user_id = $1
           WHERE (
                  -- crude sport mapping; see _athlete_sport_to_team_sport
                  (LOWER(a.sport) = 'cfb'  AND t.sport = 'cfb') OR
                  (LOWER(a.sport) IN ('mcbb','ncaab','ncaab_mens')   AND t.sport = 'ncaab_mens') OR
                  (LOWER(a.sport) IN ('wcbb','ncaaw','ncaab_womens') AND t.sport = 'ncaab_womens')
                )""",
        user_id,
    )
    return [r["id"] for r in rows]


async def _watchlist_athlete_ids(
    db: asyncpg.Connection, user_id: uuid.UUID
) -> list[uuid.UUID]:
    rows = await db.fetch(
        "SELECT athlete_id FROM watchlists WHERE user_id = $1 AND athlete_id IS NOT NULL",
        user_id,
    )
    return [r["athlete_id"] for r in rows]


async def _favorited_team_ids(
    db: asyncpg.Connection, user_id: uuid.UUID
) -> list[uuid.UUID]:
    rows = await db.fetch(
        "SELECT team_id FROM team_favorites WHERE user_id = $1",
        user_id,
    )
    return [r["team_id"] for r in rows]


def _rec_get(r: asyncpg.Record, key: str) -> Any:
    """asyncpg.Record supports __getitem__ + keys() but no .get(); emulate it."""
    return r[key] if key in r.keys() else None


def _athlete_event_to_item(r: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": f"ae_{r['id']}",
        "kind": "athlete_event",
        "category": r["category"] or "OTHER",
        "title": r["title"],
        "body": _rec_get(r, "description"),
        "occurred_at": r["occurred_at"].isoformat() if r["occurred_at"] else None,
        "source": _rec_get(r, "source"),
        "source_url": None,
        "athlete_id": str(r["athlete_id"]) if _rec_get(r, "athlete_id") else None,
        "athlete_name": _rec_get(r, "athlete_name"),
        "team_id": str(r["team_id"]) if _rec_get(r, "team_id") else None,
        "team_name": _rec_get(r, "school"),
        "sport": _rec_get(r, "sport"),
        "metadata": _jsonb_to_obj(_rec_get(r, "metadata")),
    }


def _nil_deal_to_item(r: asyncpg.Record) -> dict[str, Any]:
    deal_value = r["deal_value"]
    body_parts = [r["brand_name"]] if r["brand_name"] else []
    if deal_value is not None:
        body_parts.append(f"${float(deal_value):,.0f}")
    if r["deal_type"]:
        body_parts.append(r["deal_type"])
    occurred = r["deal_date"] or (r["ingested_at"].date() if r["ingested_at"] else None)
    iso = (
        r["deal_date"].isoformat()
        if r["deal_date"]
        else (r["ingested_at"].isoformat() if r["ingested_at"] else None)
    )
    return {
        "id": f"nd_{r['id']}",
        "kind": "nil_deal",
        "category": "NIL_DEAL",
        "title": f"NIL deal: {r['athlete_name']}",
        "body": " · ".join([p for p in body_parts if p]) or None,
        "occurred_at": iso,
        "source": r["source"],
        "source_url": r["source_url"],
        "athlete_id": str(r["athlete_id"]) if r["athlete_id"] else None,
        "athlete_name": r["athlete_name"],
        "team_id": None,
        "team_name": _rec_get(r, "school"),
        "sport": _rec_get(r, "sport"),
        "metadata": {
            "deal_value": float(deal_value) if deal_value is not None else None,
            "brand_name": r["brand_name"],
            "deal_type": r["deal_type"],
            "verified": r["verified"],
            "deal_date": occurred.isoformat() if occurred else None,
        },
    }


def _team_event_to_item(r: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": f"te_{r['id']}",
        "kind": "team_event",
        "category": r["category"] or "OTHER",
        "title": r["title"],
        "body": _rec_get(r, "body"),
        "occurred_at": r["occurred_at"].isoformat() if r["occurred_at"] else None,
        "source": _rec_get(r, "source"),
        "source_url": _rec_get(r, "source_url"),
        "athlete_id": None,
        "athlete_name": None,
        "team_id": str(r["team_id"]) if r["team_id"] else None,
        "team_name": _rec_get(r, "school_name"),
        "sport": _rec_get(r, "sport"),
        "metadata": _jsonb_to_obj(_rec_get(r, "metadata")),
    }


async def build_feed(
    db: asyncpg.Connection,
    *,
    user_id: uuid.UUID,
    sources: set[str],
    categories: Optional[list[str]],
    sports: Optional[list[str]],
    before_iso: Optional[str],
    limit: int,
) -> dict[str, Any]:
    """Collect feed items honoring the requested sources / categories / sports.

    The strategy is union-then-sort:
      1. Build a set of athlete_ids relevant to the user (watchlist ∪ team rosters).
      2. Build a set of team_ids relevant to the user.
      3. For "general", broaden the filter to any athlete in `sports`.
      4. Run small bounded queries for each shape (athlete_events,
         athlete_nil_deals, team_events), merge, sort by occurred_at DESC,
         truncate to `limit`.

    `limit` caps the *final* response size; per-shape we fetch a multiple
    so we don't lose items to truncation in any single source.
    """
    per_source = max(20, limit * 3)
    watchlist_ids = await _watchlist_athlete_ids(db, user_id) if "watchlist" in sources else []
    team_athlete_ids = await _favorited_team_athlete_ids(db, user_id) if "teams" in sources else []
    team_ids = await _favorited_team_ids(db, user_id) if "teams" in sources else []

    relevant_athletes: list[uuid.UUID] = list({*watchlist_ids, *team_athlete_ids})

    # Honor explicit category filter when given. Otherwise apply the default
    # high-signal whitelist *only* to the GENERAL bucket — watchlist/teams
    # buckets keep showing everything because they are user-curated and the
    # absolute volume is low.
    explicit_cat_filter = categories  # None = caller did not pin a filter
    cat_filter = explicit_cat_filter
    general_cat_filter = (
        explicit_cat_filter
        if explicit_cat_filter is not None
        else DEFAULT_GENERAL_CATEGORIES
    )
    sport_filter = sports or None
    before_dt = _parse_before(before_iso)

    items: list[dict[str, Any]] = []

    # ---------- 1. athlete_events ---------------------------------------------
    # Bucket A: items for relevant athletes (watchlist ∪ team rosters).
    if relevant_athletes:
        params: list[Any] = [relevant_athletes]
        sql = """SELECT ev.id, ev.athlete_id, ev.event_type, ev.category,
                        ev.title, ev.description, ev.occurred_at, ev.metadata,
                        ev.event_source AS source,
                        a.name AS athlete_name, a.school, a.sport,
                        NULL::uuid AS team_id
                 FROM athlete_events ev
                 JOIN athletes a ON a.id = ev.athlete_id
                 WHERE ev.athlete_id = ANY($1::uuid[])"""
        if cat_filter:
            params.append(cat_filter)
            sql += f" AND ev.category = ANY(${len(params)}::text[])"
        if sport_filter:
            params.append([s.lower() for s in sport_filter])
            sql += f" AND LOWER(a.sport) = ANY(${len(params)}::text[])"
        if before_dt is not None:
            params.append(before_dt)
            sql += f" AND ev.occurred_at < ${len(params)}::timestamptz"
        sql += f" ORDER BY ev.occurred_at DESC LIMIT {per_source}"
        rows = await db.fetch(sql, *params)
        items.extend(_athlete_event_to_item(r) for r in rows)

    # Bucket B: "general" — any athlete event in the user's active sports.
    # We always apply the high-signal default whitelist here (caller can
    # override with an explicit categories filter — incl. ROSTER if they
    # really want that firehose).
    if "general" in sources:
        params = []
        sql = """SELECT ev.id, ev.athlete_id, ev.event_type, ev.category,
                        ev.title, ev.description, ev.occurred_at, ev.metadata,
                        ev.event_source AS source,
                        a.name AS athlete_name, a.school, a.sport,
                        NULL::uuid AS team_id
                 FROM athlete_events ev
                 JOIN athletes a ON a.id = ev.athlete_id
                 WHERE TRUE"""
        if sport_filter:
            params.append([s.lower() for s in sport_filter])
            sql += f" AND LOWER(a.sport) = ANY(${len(params)}::text[])"
        if general_cat_filter:
            params.append(general_cat_filter)
            sql += f" AND ev.category = ANY(${len(params)}::text[])"
        if before_dt is not None:
            params.append(before_dt)
            sql += f" AND ev.occurred_at < ${len(params)}::timestamptz"
        sql += f" ORDER BY ev.occurred_at DESC LIMIT {per_source}"
        rows = await db.fetch(sql, *params)
        items.extend(_athlete_event_to_item(r) for r in rows)

    # ---------- 2. athlete_nil_deals ------------------------------------------
    # NIL deals show up as NIL_DEAL items. They predate the category column
    # on athlete_events so we read them directly to avoid losing the
    # brand_name / deal_value detail.
    want_nil = cat_filter is None or "NIL_DEAL" in cat_filter
    if want_nil:
        nil_athletes: list[uuid.UUID] = list(relevant_athletes)
        if "general" in sources and not nil_athletes:
            # If only "general" is requested with no watchlist/team match,
            # we still want to surface NIL deals sport-wide.
            nil_athletes = []  # signals "all athletes" below

        params = []
        if nil_athletes:
            params.append(nil_athletes)
            athlete_clause = f" AND nd.athlete_id = ANY(${len(params)}::uuid[])"
        elif "general" in sources:
            athlete_clause = ""  # all athletes (still bounded by limit + sport)
        else:
            athlete_clause = " AND FALSE"

        sql = f"""SELECT nd.id, nd.athlete_id, nd.deal_value, nd.brand_name,
                         nd.deal_type, nd.deal_date, nd.verified,
                         nd.source, nd.source_url, nd.ingested_at,
                         a.name AS athlete_name, a.school, a.sport
                  FROM athlete_nil_deals nd
                  JOIN athletes a ON a.id = nd.athlete_id
                  WHERE TRUE {athlete_clause}"""
        if sport_filter:
            params.append([s.lower() for s in sport_filter])
            sql += f" AND LOWER(a.sport) = ANY(${len(params)}::text[])"
        if before_dt is not None:
            params.append(before_dt)
            sql += (
                f" AND COALESCE(nd.deal_date, nd.ingested_at::date) < (${len(params)}::timestamptz)::date"
            )
        sql += f" ORDER BY COALESCE(nd.deal_date, nd.ingested_at::date) DESC NULLS LAST, nd.ingested_at DESC LIMIT {per_source}"
        rows = await db.fetch(sql, *params)
        items.extend(_nil_deal_to_item(r) for r in rows)

    # ---------- 3. team_events ------------------------------------------------
    # Team events for favorited teams (and, for "general", any team in the
    # user's active sports).
    relevant_team_ids: list[uuid.UUID] = list(team_ids)
    if "general" in sources:
        # widen to any team in active sports if any
        params = []
        sql = """SELECT te.id, te.team_id, te.category, te.title, te.body,
                        te.source, te.source_url, te.occurred_at, te.metadata,
                        t.school_name, t.sport
                 FROM team_events te
                 JOIN teams t ON t.id = te.team_id
                 WHERE TRUE"""
        if sport_filter:
            params.append([_team_sport_for(s) for s in sport_filter])
            sql += f" AND t.sport = ANY(${len(params)}::text[])"
        if general_cat_filter:
            params.append(general_cat_filter)
            sql += f" AND te.category = ANY(${len(params)}::text[])"
        if before_dt is not None:
            params.append(before_dt)
            sql += f" AND te.occurred_at < ${len(params)}::timestamptz"
        sql += f" ORDER BY te.occurred_at DESC LIMIT {per_source}"
        rows = await db.fetch(sql, *params)
        items.extend(_team_event_to_item(r) for r in rows)
    elif relevant_team_ids:
        params = [relevant_team_ids]
        sql = """SELECT te.id, te.team_id, te.category, te.title, te.body,
                        te.source, te.source_url, te.occurred_at, te.metadata,
                        t.school_name, t.sport
                 FROM team_events te
                 JOIN teams t ON t.id = te.team_id
                 WHERE te.team_id = ANY($1::uuid[])"""
        if cat_filter:
            params.append(cat_filter)
            sql += f" AND te.category = ANY(${len(params)}::text[])"
        if before_dt is not None:
            params.append(before_dt)
            sql += f" AND te.occurred_at < ${len(params)}::timestamptz"
        sql += f" ORDER BY te.occurred_at DESC LIMIT {per_source}"
        rows = await db.fetch(sql, *params)
        items.extend(_team_event_to_item(r) for r in rows)

    # Dedupe by composite id and sort.
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for it in items:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        deduped.append(it)
    deduped.sort(key=lambda x: x["occurred_at"] or "", reverse=True)
    deduped = deduped[:limit]
    next_cursor = deduped[-1]["occurred_at"] if len(deduped) >= limit else None
    return {"items": deduped, "next_before": next_cursor}


def _team_sport_for(cap_sport: str) -> str:
    """Map a UI cap-sport (CFB/NCAAB/NCAAW) to the teams.sport slug."""
    s = (cap_sport or "").upper()
    if s == "CFB":
        return "cfb"
    if s == "NCAAB":
        return "ncaab_mens"
    if s == "NCAAW":
        return "ncaab_womens"
    return s.lower()
