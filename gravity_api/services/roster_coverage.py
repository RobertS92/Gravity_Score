"""Success gate for ESPN roster sync: N complete Power 5 CFB team payloads."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from gravity_api.services.roster_retirement import roster_payload_complete

# One school from each Power 5 conference (ACC, Big 12, Big Ten, SEC x2).
POWER5_CANARY_TEAMS: tuple[tuple[str, str], ...] = (
    ("228", "Clemson Tigers"),
    ("251", "Texas Longhorns"),
    ("194", "Ohio State Buckeyes"),
    ("61", "Georgia Bulldogs"),
    ("333", "Alabama Crimson Tide"),
)

POWER5_CANARY_TEAM_IDS: tuple[str, ...] = tuple(tid for tid, _ in POWER5_CANARY_TEAMS)


def complete_team_results(
    team_results: Sequence[Mapping[str, Any]],
    *,
    sport: str = "cfb",
) -> list[dict[str, Any]]:
    complete: list[dict[str, Any]] = []
    for row in team_results:
        if roster_payload_complete(row, sport) and not row.get("error"):
            complete.append(dict(row))
    return complete


def coverage_report(
    team_results: Sequence[Mapping[str, Any]],
    *,
    sport: str = "cfb",
    min_teams: int = 5,
    required_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    complete = complete_team_results(team_results, sport=sport)
    complete_ids = {str(row.get("espn_team_id") or "") for row in complete}
    want = [
        str(tid)
        for tid in (
            required_ids
            if required_ids is not None
            else (POWER5_CANARY_TEAM_IDS if sport == "cfb" else ())
        )
    ]
    missing = [tid for tid in want if tid not in complete_ids]
    passed = len(complete) >= min_teams and not missing
    return {
        "passed": passed,
        "min_teams": min_teams,
        "complete_teams": len(complete),
        "complete_ids": sorted(complete_ids),
        "required_ids": want,
        "missing_ids": missing,
        "failed_teams": [
            {
                "espn_team_id": row.get("espn_team_id"),
                "team_name": row.get("team_name"),
                "players_seen": row.get("players_seen"),
                "error": row.get("error"),
            }
            for row in team_results
            if str(row.get("espn_team_id") or "") in set(missing)
            or (row.get("error") and str(row.get("espn_team_id") or "") in set(want))
        ],
    }
