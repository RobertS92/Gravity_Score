"""Retire college athletes who left for the draft, transferred off-index, or quit.

Two independent passes:

1. **Unseen-on-synced-team** — after an ESPN roster pull, anyone still tagged to a
   school we successfully fetched, but not on that payload, is no longer college-active.
2. **Pro overlay** — active college rows that match an active pro row (NFL/NBA/WNBA)
   are marked ``left_for_draft``. Name-only collisions are not auto-applied.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Literal, Mapping, Sequence

import asyncpg

logger = logging.getLogger(__name__)

COLLEGE_SPORTS = ("cfb", "ncaab_mens", "ncaab_womens")
PRO_SPORTS = ("nfl", "nba", "wnba")
SPORT_PAIRS = (
    ("cfb", "nfl"),
    ("ncaab_mens", "nba"),
    ("ncaab_womens", "wnba"),
)

Confidence = Literal["high", "medium", "low", "reject"]
CONFIDENCE_RANK = {"reject": 0, "low": 1, "medium": 2, "high": 3}

# Partial ESPN payloads must not retire a whole depth chart.
MIN_ROSTER_PLAYERS = {
    "cfb": 40,
    "ncaab_mens": 8,
    "ncaab_womens": 8,
    "ncaa_baseball": 18,
    "ncaa_volleyball": 10,
    "nfl": 45,
    "nba": 10,
    "wnba": 8,
}
DEFAULT_MIN_ROSTER_PLAYERS = 8

_FOOTBALL_FAMILY = {
    "qb": "qb",
    "rb": "rb",
    "hb": "rb",
    "fb": "rb",
    "tb": "rb",
    "wr": "wr",
    "te": "te",
    "ol": "ol",
    "ot": "ol",
    "og": "ol",
    "c": "ol",
    "g": "ol",
    "t": "ol",
    "iol": "ol",
    "oc": "ol",
    "dl": "dl",
    "de": "dl",
    "dt": "dl",
    "nt": "dl",
    "edge": "dl",
    "lb": "lb",
    "ilb": "lb",
    "olb": "lb",
    "mlb": "lb",
    "db": "db",
    "cb": "db",
    "s": "db",
    "ss": "db",
    "fs": "db",
    "saf": "db",
    "safety": "db",
    "nb": "db",
    "k": "st",
    "p": "st",
    "ls": "st",
    "pk": "st",
}
_BASKETBALL_FAMILY = {
    "g": "g",
    "pg": "g",
    "sg": "g",
    "guard": "g",
    "f": "f",
    "sf": "f",
    "pf": "f",
    "forward": "f",
    "c": "c",
    "center": "c",
    "g/f": "g",
    "f/c": "f",
}

_GRAD_CLASS_RE = re.compile(
    r"(^|[^a-z])(sr|senior|gr|grad(?:uate)?(?:\s+student)?)([^a-z]|$)",
    re.IGNORECASE,
)
_NOT_GRAD_RE = re.compile(r"fresh|soph|junior|\bfr\b|\bso\b|\bjr\b", re.IGNORECASE)


def position_family(position: str | None, *, sport: str) -> str | None:
    token = re.split(r"[/\s,-]+", str(position or "").strip().lower())[0]
    if not token:
        return None
    table = _FOOTBALL_FAMILY if sport in {"cfb", "nfl"} else _BASKETBALL_FAMILY
    return table.get(token)


def looks_graduated(class_year: str | None) -> bool:
    text = str(class_year or "").strip()
    if not text or _NOT_GRAD_RE.search(text):
        return False
    return bool(_GRAD_CLASS_RE.search(text))


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def classify_identity_match(
    college: Mapping[str, Any],
    pro: Mapping[str, Any],
) -> Confidence:
    """Decide whether a college row and a pro row are the same person."""
    college_espn = str(college.get("espn_id") or "").strip()
    pro_college_espn = str(pro.get("college_espn_id") or "").strip()
    if college_espn and pro_college_espn and college_espn == pro_college_espn:
        return "high"

    college_h = _int_or_none(college.get("height_inches") or college.get("college_height_inches"))
    pro_h = _int_or_none(pro.get("height_inches") or pro.get("pro_height_inches"))
    college_w = _int_or_none(college.get("weight_lbs") or college.get("college_weight_lbs"))
    pro_w = _int_or_none(pro.get("weight_lbs") or pro.get("pro_weight_lbs"))
    if college_h is not None and pro_h is not None and abs(college_h - pro_h) > 2:
        return "reject"
    if college_w is not None and pro_w is not None and abs(college_w - pro_w) > 35:
        return "reject"

    college_sport = str(college.get("sport") or college.get("college_sport") or "")
    pro_sport = str(pro.get("sport") or pro.get("pro_sport") or "")
    college_fam = position_family(
        college.get("position") or college.get("college_position"),
        sport=college_sport,
    )
    pro_fam = position_family(
        pro.get("position") or pro.get("pro_position"),
        sport=pro_sport,
    )
    if college_fam and pro_fam and college_fam != pro_fam:
        return "reject"

    have_height = college_h is not None and pro_h is not None
    have_weight = college_w is not None and pro_w is not None
    body_ok = have_height and (have_weight or bool(college_fam and pro_fam and college_fam == pro_fam))
    if body_ok and looks_graduated(college.get("class_year")):
        return "medium"
    return "low"


def meets_confidence(actual: Confidence, minimum: Confidence) -> bool:
    return CONFIDENCE_RANK[actual] >= CONFIDENCE_RANK[minimum] and actual != "reject"


def roster_payload_complete(result: Mapping[str, Any], sport: str) -> bool:
    if result.get("error"):
        return False
    minimum = MIN_ROSTER_PLAYERS.get(sport, DEFAULT_MIN_ROSTER_PLAYERS)
    try:
        seen = int(result.get("players_seen") or 0)
    except (TypeError, ValueError):
        return False
    return seen >= minimum


def synced_school_names(
    team_results: Sequence[Mapping[str, Any]],
    sport: str,
    *,
    index_aliases: Sequence[Mapping[str, Any]] | None = None,
) -> list[str]:
    """School labels we are allowed to retire against after a successful pull."""
    names: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if not text or text in seen:
            return
        seen.add(text)
        names.append(text)

    by_team_id = {
        str(row.get("espn_team_id") or ""): row
        for row in (index_aliases or [])
        if row.get("espn_team_id")
    }
    for result in team_results:
        if not roster_payload_complete(result, sport):
            continue
        add(result.get("team_name"))
        alias = by_team_id.get(str(result.get("espn_team_id") or ""))
        if alias:
            add(alias.get("school_name"))
    return names


def departure_status(class_year: str | None, *, has_pro_match: bool) -> tuple[str, str]:
    if has_pro_match:
        return "left_for_draft", "active_pro_roster_match"
    if looks_graduated(class_year):
        return "graduated", "absent_from_current_espn_roster"
    return "out_other", "absent_from_current_espn_roster"


async def _raw_table_exists(conn: asyncpg.Connection) -> bool:
    row = await conn.fetchval("SELECT to_regclass($1)", "public.raw_athlete_data")
    return row is not None


async def retire_unseen_on_synced_teams(
    conn: asyncpg.Connection,
    *,
    sport: str,
    seen_athlete_ids: Sequence[str],
    synced_schools: Sequence[str],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Deactivate college/pro rows still assigned to a school we just fetched."""
    ts = now or datetime.now(timezone.utc)
    schools = [s for s in synced_schools if str(s).strip()]
    seen = [str(aid) for aid in seen_athlete_ids if aid]
    if not schools:
        return {"skipped": "no_complete_team_payloads", "deactivated": 0, "rows": []}
    if not seen:
        return {"skipped": "empty_seen_set", "deactivated": 0, "rows": []}

    rows = await conn.fetch(
        """
        UPDATE athletes AS a
        SET is_active = FALSE,
            roster_status = CASE
                WHEN a.class_year ~* '(^|[^a-z])(sr|senior|gr|grad)'
                 AND a.class_year !~* 'fresh|soph|junior|(^|[^a-z])(fr|so|jr)([^a-z]|$)'
                    THEN 'graduated'
                ELSE 'out_other'
            END,
            roster_status_reason = 'absent_from_current_espn_roster',
            roster_status_changed_at = $4,
            updated_at = NOW()
        WHERE a.sport = $1
          AND COALESCE(a.is_active, TRUE) = TRUE
          AND COALESCE(a.roster_status, 'active_on_roster') IN ('active_on_roster', 'transferred')
          AND a.id <> ALL($2::uuid[])
          AND a.school = ANY($3::text[])
        RETURNING a.id::text AS id, a.name, a.school, a.class_year, a.roster_status
        """,
        sport,
        seen,
        schools,
        ts,
    )
    deactivated = [dict(row) for row in rows]
    logger.info(
        "Retired %s %s athletes absent from current ESPN rosters across %s school(s)",
        len(deactivated),
        sport,
        len(schools),
    )
    return {
        "skipped": None,
        "deactivated": len(deactivated),
        "schools": schools,
        "rows": deactivated,
    }


async def find_pro_college_duplicates(
    conn: asyncpg.Connection,
    *,
    name: str | None = None,
    college_ids: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    params: list[object] = [list(COLLEGE_SPORTS), list(PRO_SPORTS)]
    filters: list[str] = []
    if college_ids:
        params.append(list(college_ids))
        filters.append(f"AND college.id = ANY(${len(params)}::uuid[])")
    else:
        filters.append("AND COALESCE(college.is_active, TRUE) = TRUE")
    if name:
        params.append(name)
        filters.append(f"AND college.name ILIKE ${len(params)}")
    extra = "\n            ".join(filters)

    college_espn_expr = "NULL::text"
    join_raw = ""
    if await _raw_table_exists(conn):
        college_espn_expr = "pro_raw.college_espn_id"
        join_raw = """
        LEFT JOIN LATERAL (
          SELECT NULLIF(raw_data->>'college_espn_id', '') AS college_espn_id
          FROM raw_athlete_data
          WHERE athlete_id = pro.id
          ORDER BY scraped_at DESC NULLS LAST
          LIMIT 1
        ) pro_raw ON TRUE
        """

    rows = await conn.fetch(
        f"""
        WITH active_college AS (
          SELECT *,
                 regexp_replace(lower(name), '[^a-z0-9]+', '', 'g') AS name_key
          FROM athletes college
          WHERE sport = ANY($1::text[])
            AND name !~ '^[A-Z]\\.?\\s'
            {extra}
        ),
        active_pro AS (
          SELECT *
          FROM athletes
          WHERE sport = ANY($2::text[])
            AND COALESCE(is_active, TRUE) = TRUE
        )
        SELECT college.id::text AS college_id,
               college.name,
               college.sport AS college_sport,
               college.position AS college_position,
               college.school AS college_school,
               college.height_inches AS college_height_inches,
               college.weight_lbs AS college_weight_lbs,
               college.espn_id AS college_espn_id,
               college.class_year,
               college.updated_at AS college_updated_at,
               pro.id::text AS pro_id,
               pro.name AS pro_name,
               pro.sport AS pro_sport,
               pro.position AS pro_position,
               pro.school AS pro_team,
               pro.height_inches AS pro_height_inches,
               pro.weight_lbs AS pro_weight_lbs,
               pro.updated_at AS pro_updated_at,
               {college_espn_expr} AS pro_college_espn_id
        FROM active_college college
        JOIN active_pro pro
          ON regexp_replace(lower(pro.name), '[^a-z0-9]+', '', 'g') = college.name_key
         AND (
              (college.sport = 'cfb' AND pro.sport = 'nfl')
           OR (college.sport = 'ncaab_mens' AND pro.sport = 'nba')
           OR (college.sport = 'ncaab_womens' AND pro.sport = 'wnba')
         )
        {join_raw}
        ORDER BY college.name, college.sport, pro.updated_at DESC NULLS LAST
        """,
        *params,
    )
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        college_id = str(payload["college_id"])
        if college_id in seen:
            continue
        confidence = classify_identity_match(
            {
                "espn_id": payload.get("college_espn_id"),
                "sport": payload.get("college_sport"),
                "position": payload.get("college_position"),
                "height_inches": payload.get("college_height_inches"),
                "weight_lbs": payload.get("college_weight_lbs"),
                "class_year": payload.get("class_year"),
            },
            {
                "college_espn_id": payload.get("pro_college_espn_id"),
                "sport": payload.get("pro_sport"),
                "position": payload.get("pro_position"),
                "height_inches": payload.get("pro_height_inches"),
                "weight_lbs": payload.get("pro_weight_lbs"),
            },
        )
        payload["confidence"] = confidence
        if confidence == "reject":
            continue
        seen.add(college_id)
        output.append(payload)
    return output


async def apply_pro_college_hygiene(
    conn: asyncpg.Connection,
    *,
    apply: bool = False,
    min_confidence: Confidence = "medium",
    name: str | None = None,
    college_ids: Sequence[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Mark confident college/pro duplicates as left_for_draft."""
    ts = now or datetime.now(timezone.utc)
    candidates = await find_pro_college_duplicates(
        conn, name=name, college_ids=college_ids
    )
    actionable = [
        row for row in candidates if meets_confidence(row["confidence"], min_confidence)
    ]
    changed = 0
    if apply and actionable:
        ids = [row["college_id"] for row in actionable]
        status = await conn.execute(
            """
            UPDATE athletes
            SET is_active = FALSE,
                roster_status = 'left_for_draft',
                roster_status_reason = 'active_pro_roster_match',
                roster_status_changed_at = $3,
                updated_at = NOW()
            WHERE id = ANY($1::uuid[])
              AND sport = ANY($2::text[])
              AND roster_status IS DISTINCT FROM 'left_for_draft'
            """,
            ids,
            list(COLLEGE_SPORTS),
            ts,
        )
        changed = int(status.rsplit(" ", 1)[-1])
        logger.info("Marked %s college rows left_for_draft via pro roster match", changed)
    return {
        "mode": "apply" if apply else "dry_run",
        "min_confidence": min_confidence,
        "candidates": len(candidates),
        "actionable": len(actionable),
        "deactivated": changed,
        "by_confidence": {
            level: sum(1 for row in candidates if row["confidence"] == level)
            for level in ("high", "medium", "low")
        },
        "rows": candidates,
    }
