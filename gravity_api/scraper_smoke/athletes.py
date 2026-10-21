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


# Two athletes per priority sport. IDs confirmed via ESPN site.web.api roster/profile.
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
        name="Ja'Marr Chase",
        espn_id="4362628",
        team_hint="Bengals",
        position_hint="WR",
        name_tokens=("Chase",),
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
        name="Stephen Curry",
        espn_id="3975",
        team_hint="Warriors",
        position_hint="G",
        name_tokens=("Stephen", "Curry"),
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
        name="Julian Sayin",
        espn_id="5079712",
        team_hint="Ohio State",
        position_hint="QB",
        name_tokens=("Julian", "Sayin"),
    ),
    # Men's college basketball
    SmokeAthlete(
        sport="ncaab_mens",
        name="Zoom Diallo",
        espn_id="5060705",
        team_hint="Kentucky",
        position_hint="G",
        name_tokens=("Diallo",),
    ),
    SmokeAthlete(
        sport="ncaab_mens",
        name="Cayden Boozer",
        espn_id="5041937",
        team_hint="Duke",
        position_hint="G",
        name_tokens=("Cayden", "Boozer"),
    ),
    # Women's college basketball
    SmokeAthlete(
        sport="ncaab_womens",
        name="JuJu Watkins",
        espn_id="5175946",
        team_hint="USC",
        position_hint="G",
        name_tokens=("Watkins",),
    ),
    SmokeAthlete(
        sport="ncaab_womens",
        name="Sarah Strong",
        espn_id="5239592",
        team_hint="UConn",
        position_hint="F",
        name_tokens=("Sarah", "Strong"),
    ),
)


def athletes_by_sport() -> dict[str, list[SmokeAthlete]]:
    out: dict[str, list[SmokeAthlete]] = {}
    for a in SMOKE_ATHLETES:
        out.setdefault(a.sport, []).append(a)
    return out
