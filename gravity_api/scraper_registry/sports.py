"""Sport catalog for scraper registry expansion."""

from __future__ import annotations

from typing import TypedDict


class SportConfig(TypedDict):
    display_name: str
    league_tier: str
    terminal_visible: bool
    espn_slug: str


SPORTS: dict[str, SportConfig] = {
    # College — terminal visible
    "cfb": {
        "display_name": "College Football",
        "league_tier": "college",
        "terminal_visible": True,
        "espn_slug": "football/college-football",
    },
    "ncaab_mens": {
        "display_name": "Men's College Basketball",
        "league_tier": "college",
        "terminal_visible": True,
        "espn_slug": "basketball/mens-college-basketball",
    },
    "ncaab_womens": {
        "display_name": "Women's College Basketball",
        "league_tier": "college",
        "terminal_visible": True,
        "espn_slug": "basketball/womens-college-basketball",
    },
    "ncaa_baseball": {
        "display_name": "College Baseball",
        "league_tier": "college",
        "terminal_visible": True,
        "espn_slug": "baseball/college-baseball",
    },
    "ncaa_volleyball": {
        "display_name": "College Volleyball (W)",
        "league_tier": "college",
        "terminal_visible": True,
        "espn_slug": "volleyball/womens-college-volleyball",
    },
    # Pro — background scoring only
    "nfl": {
        "display_name": "NFL",
        "league_tier": "pro",
        "terminal_visible": False,
        "espn_slug": "football/nfl",
    },
    "nba": {
        "display_name": "NBA",
        "league_tier": "pro",
        "terminal_visible": False,
        "espn_slug": "basketball/nba",
    },
    "wnba": {
        "display_name": "WNBA",
        "league_tier": "pro",
        "terminal_visible": False,
        "espn_slug": "basketball/wnba",
    },
}

COLLEGE_SPORTS = [k for k, v in SPORTS.items() if v["league_tier"] == "college"]
PRO_SPORTS = [k for k, v in SPORTS.items() if v["league_tier"] == "pro"]
