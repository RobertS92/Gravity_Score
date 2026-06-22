"""Diff roster snapshots to detect transfers, departures, and additions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class SnapshotRow:
    athlete_id: str
    espn_athlete_id: str
    espn_team_id: str
    team: str
    conference: str
    sport: str
    position: str | None
    class_year: str | None
    jersey_number: str | None


def index_by_espn_id(rows: list[SnapshotRow]) -> dict[str, SnapshotRow]:
    return {r.espn_athlete_id: r for r in rows}


def compute_roster_changes(
    previous: list[SnapshotRow],
    current: list[SnapshotRow],
    *,
    as_of: date,
) -> dict[str, list[dict[str, Any]]]:
    prev_by = index_by_espn_id(previous)
    cur_by = index_by_espn_id(current)
    prev_ids = set(prev_by)
    cur_ids = set(cur_by)

    events: dict[str, list[dict[str, Any]]] = {
        "TRANSFER_COMPLETED": [],
        "ROSTER_DEPARTURE": [],
        "ROSTER_ADDITION": [],
    }

    for eid in cur_ids & prev_ids:
        a, b = prev_by[eid], cur_by[eid]
        if a.espn_team_id != b.espn_team_id:
            events["TRANSFER_COMPLETED"].append(
                {
                    "athlete_id": b.athlete_id,
                    "event_type": "TRANSFER_COMPLETED",
                    "event_severity": "INFO",
                    "title": f"Transfer: {a.team} → {b.team}",
                    "description": None,
                    "metadata": {
                        "from_team": a.team,
                        "to_team": b.team,
                        "from_conference": a.conference,
                        "to_conference": b.conference,
                        "from_espn_team_id": a.espn_team_id,
                        "to_espn_team_id": b.espn_team_id,
                        "announced_date": as_of.isoformat(),
                    },
                    "source": "ROSTER_DIFF",
                }
            )

    for eid in cur_ids - prev_ids:
        row = cur_by[eid]
        events["ROSTER_ADDITION"].append(
            {
                "athlete_id": row.athlete_id,
                "event_type": "ROSTER_ADDITION",
                "event_severity": "INFO",
                "title": f"New roster entry: {row.team}",
                "description": None,
                "metadata": {
                    "team": row.team,
                    "espn_team_id": row.espn_team_id,
                    "sport": row.sport,
                },
                "source": "ROSTER_DIFF",
            }
        )

    for eid in prev_ids - cur_ids:
        row = prev_by[eid]
        events["ROSTER_DEPARTURE"].append(
            {
                "athlete_id": row.athlete_id,
                "event_type": "ROSTER_DEPARTURE",
                "event_severity": "WARN",
                "title": f"No longer on roster: {row.team}",
                "description": None,
                "metadata": {
                    "last_team": row.team,
                    "espn_team_id": row.espn_team_id,
                    "sport": row.sport,
                },
                "source": "ROSTER_DIFF",
            }
        )

    return events
