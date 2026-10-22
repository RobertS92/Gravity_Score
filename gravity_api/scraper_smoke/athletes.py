"""Well-known athletes for scraper smoke tests — ESPN IDs verified live."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SmokeAthlete:
    sport: str
    name: str
    espn_id: str
    team_hint: str
    position_hint: str | None = None
    # Substrings that must appear in scraped player_name (case-insensitive).
    name_tokens: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name_tokens:
            object.__setattr__(self, "name_tokens", tuple(self.name.split()))


# Two athletes per priority sport. IDs confirmed via ESPN profile/stats pages.
# Phase-1 free-tier set (2026-10): CFB/NFL/NBA named; CBB M/W chosen for 2025-26.
SMOKE_ATHLETES: tuple[SmokeAthlete, ...] = (
    # NFL
    SmokeAthlete(
        sport="nfl",
        name="Patrick Mahomes",
        espn_id="3139477",
        team_hint="Chiefs",
        position_hint="QB",
        name_tokens=("Patrick", "Mahomes"),
    ),
    SmokeAthlete(
        sport="nfl",
        name="Will Anderson Jr.",
        espn_id="4685724",
        team_hint="Texans",
        position_hint="DE",
        name_tokens=("Will", "Anderson"),
    ),
    # NBA
    SmokeAthlete(
        sport="nba",
        name="LeBron James",
        espn_id="1966",
        team_hint="Lakers",
        position_hint="F",
        name_tokens=("LeBron", "James"),
    ),
    SmokeAthlete(
        sport="nba",
        name="Kevin Durant",
        espn_id="3202",
        team_hint="Rockets",
        position_hint="F",
        name_tokens=("Kevin", "Durant"),
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
    # Men's college basketball — 2025-26 stars
    # AJ Dybantsa: BYU freshman, national scoring leader / AP All-America 2025-26.
    # Cameron Boozer: Duke freshman, consensus National Player of the Year 2025-26.
    SmokeAthlete(
        sport="ncaab_mens",
        name="AJ Dybantsa",
        espn_id="5142718",
        team_hint="BYU",
        position_hint="F",
        name_tokens=("Dybantsa",),
    ),
    SmokeAthlete(
        sport="ncaab_mens",
        name="Cameron Boozer",
        espn_id="5041935",
        team_hint="Duke",
        position_hint="F",
        name_tokens=("Cameron", "Boozer"),
    ),
    # Women's college basketball — 2025-26 stars
    # Sarah Strong: UConn, 2025-26 AP POY / Naismith / Wade Trophy.
    # Mikayla Blakes: Vanderbilt, 2025-26 scoring champ / AP First-Team All-America.
    # (JuJu Watkins sat out 2025-26 ACL recovery — omitted as not a current-season player.)
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
    ),
)


def athletes_by_sport() -> dict[str, list[SmokeAthlete]]:
    out: dict[str, list[SmokeAthlete]] = {}
    for a in SMOKE_ATHLETES:
        out.setdefault(a.sport, []).append(a)
    return out
