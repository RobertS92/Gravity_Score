"""Well-known athletes for scraper smoke tests — ESPN IDs verified live.

Team identity: smoke pass/fail compares scraped team to the **live ESPN roster
team** returned by ``EspnRosterScraper``, not to ``team_hint``. ``team_hint`` is
documentation / scrape-context seed only (avoids stale Lakers-style hard fails).

Lifecycle: draft departures are asserted as expected facts in
``DRAFT_DEPARTURE_FIXTURES`` / ``LIFECYCLE_FACTS`` (college inactive + pro row),
separately from current-team matching.

ESPN id crosswalk: fixture athletes (Dybantsa ``5142718``, Boozer ``5041935``)
reuse the same ESPN id for college and pro — no separate crosswalk table needed.
Pro ``college_espn_id`` covers different-id cases when ESPN issues them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SmokeAthlete:
    sport: str
    name: str
    espn_id: str
    # Docs / AthleteScrapeContext seed only — NOT smoke pass/fail for team.
    team_hint: str
    position_hint: str | None = None
    # Substrings that must appear in scraped player_name (case-insensitive).
    name_tokens: tuple[str, ...] = ()
    # Optional notes for Phase-1 report / CSV selection_note.
    selection_note: str = ""

    def __post_init__(self) -> None:
        if not self.name_tokens:
            object.__setattr__(self, "name_tokens", tuple(self.name.split()))


@dataclass(frozen=True)
class LifecycleFact:
    """Expected roster lifecycle after college→pro departure (not a team hint)."""

    name: str
    espn_id: str
    college_sport: str
    college_team: str
    pro_sport: str
    pro_team: str
    expected_roster_status: str = "left_for_draft"
    college_is_active: bool = False
    pro_record_exists: bool = True
    # Same ESPN id across leagues for these fixtures (no crosswalk row).
    same_espn_id_college_and_pro: bool = True


# Two athletes per priority sport. IDs confirmed via ESPN profile/stats pages.
# Phase-1 free-tier set (2026-10 sanity): draft departures classified as NBA;
# men's college slots replaced with athletes still on 2026-27 college rosters.
SMOKE_ATHLETES: tuple[SmokeAthlete, ...] = (
    # NFL
    SmokeAthlete(
        sport="nfl",
        name="Patrick Mahomes",
        espn_id="3139477",
        team_hint="Chiefs",
        position_hint="QB",
        name_tokens=("Patrick", "Mahomes"),
        selection_note="ACL Week 15 2025 — elevated injury risk for scoring.",
    ),
    SmokeAthlete(
        sport="nfl",
        name="Will Anderson Jr.",
        espn_id="4685724",
        team_hint="Texans",
        position_hint="DE",
        name_tokens=("Will", "Anderson"),
    ),
    # NBA — includes 2026 draft picks who left college
    SmokeAthlete(
        sport="nba",
        name="LeBron James",
        espn_id="1966",
        team_hint="76ers",
        position_hint="F",
        name_tokens=("LeBron", "James"),
        selection_note="Philadelphia 76ers (announced July 2026). team_hint is docs-only.",
    ),
    SmokeAthlete(
        sport="nba",
        name="Kevin Durant",
        espn_id="3202",
        team_hint="Rockets",
        position_hint="F",
        name_tokens=("Kevin", "Durant"),
    ),
    SmokeAthlete(
        sport="nba",
        name="AJ Dybantsa",
        espn_id="5142718",
        team_hint="Wizards",
        position_hint="F",
        name_tokens=("Dybantsa",),
        selection_note=(
            "2026 #1 pick, Washington Wizards. College (BYU) roster must be "
            "is_active=false / left_for_draft. Same ESPN id 5142718 college+NBA."
        ),
    ),
    SmokeAthlete(
        sport="nba",
        name="Cameron Boozer",
        espn_id="5041935",
        team_hint="Grizzlies",
        position_hint="F",
        name_tokens=("Cameron", "Boozer"),
        selection_note=(
            "2026 #3 pick, Memphis Grizzlies. College (Duke) roster must be "
            "is_active=false / left_for_draft."
        ),
    ),
    # CFB
    SmokeAthlete(
        sport="cfb",
        name="Arch Manning",
        espn_id="4870906",
        team_hint="Texas",
        position_hint="QB",
        name_tokens=("Arch", "Manning"),
    ),
    SmokeAthlete(
        sport="cfb",
        name="Colin Simmons",
        espn_id="5079689",
        team_hint="Texas",
        position_hint="EDGE",
        name_tokens=("Colin", "Simmons"),
    ),
    # Men's college basketball — still on 2026-27 college rosters
    SmokeAthlete(
        sport="ncaab_mens",
        name="Cayden Boozer",
        espn_id="5041937",
        team_hint="Duke",
        position_hint="G",
        name_tokens=("Cayden", "Boozer"),
        selection_note="Duke; still college 2026-27 (Cameron Boozer drafted).",
    ),
    SmokeAthlete(
        sport="ncaab_mens",
        name="Solo Ball",
        espn_id="4895737",
        team_hint="UConn",
        position_hint="G",
        name_tokens=("Solo", "Ball"),
        selection_note="UConn; still college 2026-27.",
    ),
    # Women's college basketball
    SmokeAthlete(
        sport="ncaab_womens",
        name="Sarah Strong",
        espn_id="5239592",
        team_hint="UConn",
        position_hint="F",
        name_tokens=("Sarah", "Strong"),
    ),
    SmokeAthlete(
        sport="ncaab_womens",
        name="Mikayla Blakes",
        espn_id="5239107",
        team_hint="Vanderbilt",
        position_hint="G",
        name_tokens=("Mikayla", "Blakes"),
        selection_note="Vanderbilt; JuJu Watkins sat out 2025-26 ACL recovery.",
    ),
)

# Regression fixtures: college rows that must retire after the 2026 NBA draft.
LIFECYCLE_FACTS: tuple[LifecycleFact, ...] = (
    LifecycleFact(
        name="AJ Dybantsa",
        espn_id="5142718",
        college_sport="ncaab_mens",
        college_team="BYU",
        pro_sport="nba",
        pro_team="Wizards",
        expected_roster_status="left_for_draft",
        college_is_active=False,
        pro_record_exists=True,
        same_espn_id_college_and_pro=True,
    ),
    LifecycleFact(
        name="Cameron Boozer",
        espn_id="5041935",
        college_sport="ncaab_mens",
        college_team="Duke",
        pro_sport="nba",
        pro_team="Grizzlies",
        expected_roster_status="left_for_draft",
        college_is_active=False,
        pro_record_exists=True,
        same_espn_id_college_and_pro=True,
    ),
)

# Back-compat alias for existing tests / retirement helpers.
DRAFT_DEPARTURE_FIXTURES: tuple[dict[str, str], ...] = tuple(
    {
        "name": f.name,
        "espn_id": f.espn_id,
        "college_sport": f.college_sport,
        "college_team": f.college_team,
        "pro_sport": f.pro_sport,
        "pro_team": f.pro_team,
        "expected_roster_status": f.expected_roster_status,
    }
    for f in LIFECYCLE_FACTS
)


def athletes_by_sport() -> dict[str, list[SmokeAthlete]]:
    out: dict[str, list[SmokeAthlete]] = {}
    for a in SMOKE_ATHLETES:
        out.setdefault(a.sport, []).append(a)
    return out


def lifecycle_facts_for_espn_id(espn_id: str) -> list[LifecycleFact]:
    eid = str(espn_id).strip()
    return [f for f in LIFECYCLE_FACTS if f.espn_id == eid]
