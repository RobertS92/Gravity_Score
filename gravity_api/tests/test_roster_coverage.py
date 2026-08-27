from gravity_api.scrapers.clients.espn import EspnClient
from gravity_api.services.roster_coverage import (
    POWER5_CANARY_TEAM_IDS,
    coverage_report,
)
from gravity_api.services.roster_retirement import MIN_ROSTER_PLAYERS


def test_coverage_gate_requires_five_complete_power5_teams():
    results = [
        {"espn_team_id": "61", "team_name": "Georgia Bulldogs", "players_seen": 85},
        {"espn_team_id": "333", "team_name": "Alabama Crimson Tide", "players_seen": 90},
        {"espn_team_id": "194", "team_name": "Ohio State Buckeyes", "players_seen": 88},
        {"espn_team_id": "251", "team_name": "Texas Longhorns", "players_seen": 100},
        {"espn_team_id": "228", "team_name": "Clemson Tigers", "players_seen": 12, "error": None},
    ]
    report = coverage_report(results, min_teams=5)
    assert report["passed"] is False
    assert "228" in report["missing_ids"]

    results[-1] = {"espn_team_id": "228", "team_name": "Clemson Tigers", "players_seen": 95}
    report = coverage_report(results, min_teams=5)
    assert report["passed"] is True
    assert report["complete_teams"] == 5


def test_five_power5_cfb_rosters_fetch_live():
    """Live ESPN canary: one school from each Power 5 conference."""
    import asyncio

    async def fetch_all() -> list[dict]:
        client = EspnClient()
        out: list[dict] = []
        for tid in POWER5_CANARY_TEAM_IDS:
            payload = await client.fetch_roster_payload("cfb", tid)
            players = EspnClient.flatten_roster_players(payload) if payload else []
            team = (payload or {}).get("team") or {}
            out.append(
                {
                    "espn_team_id": tid,
                    "team_name": team.get("displayName"),
                    "players_seen": len(players),
                    "error": None if players else "empty_roster_payload",
                }
            )
        return out

    results = asyncio.run(fetch_all())
    report = coverage_report(results, min_teams=5, required_ids=list(POWER5_CANARY_TEAM_IDS))
    assert report["passed"], report
    minimum = MIN_ROSTER_PLAYERS["cfb"]
    for row in results:
        assert int(row["players_seen"]) >= minimum, row
