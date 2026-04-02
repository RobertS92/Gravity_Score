"""
Shared Power 5 configuration and player dataclasses for CFB + NCAAB scrapers.

Field semantics: each scalar field is either a real value, None (not found), or the
string ``\"ERROR\"`` when collection failed (per pipeline contract).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

TriStateStr = str | None  # real str, None, or "ERROR"
TriStateInt = int | None  # real int, None, or "ERROR" as invalid — use object

# --- Conferences → canonical display names (must match ESPN_TEAM_ID keys) ---

CFB_TEAMS_BY_CONFERENCE: dict[str, list[str]] = {
    "SEC": [
        "Alabama",
        "Arkansas",
        "Auburn",
        "Florida",
        "Georgia",
        "Kentucky",
        "LSU",
        "Ole Miss",
        "Mississippi State",
        "Missouri",
        "Oklahoma",
        "South Carolina",
        "Tennessee",
        "Texas",
        "Texas A&M",
        "Vanderbilt",
    ],
    "Big Ten": [
        "Illinois",
        "Indiana",
        "Iowa",
        "Maryland",
        "Michigan",
        "Michigan State",
        "Minnesota",
        "Nebraska",
        "Northwestern",
        "Ohio State",
        "Oregon",
        "Penn State",
        "Purdue",
        "Rutgers",
        "USC",
        "UCLA",
        "Washington",
        "Wisconsin",
    ],
    "Big 12": [
        "Arizona",
        "Arizona State",
        "Baylor",
        "BYU",
        "Cincinnati",
        "Colorado",
        "Houston",
        "Iowa State",
        "Kansas",
        "Kansas State",
        "Oklahoma State",
        "TCU",
        "Texas Tech",
        "UCF",
        "West Virginia",
        "Utah",
    ],
    "ACC": [
        "Boston College",
        "Cal",
        "Clemson",
        "Duke",
        "Florida State",
        "Georgia Tech",
        "Louisville",
        "Miami",
        "NC State",
        "North Carolina",
        "Notre Dame",
        "Pittsburgh",
        "SMU",
        "Stanford",
        "Syracuse",
        "Virginia",
        "Virginia Tech",
        "Wake Forest",
    ],
}

NCAAB_TEAMS_BY_CONFERENCE: dict[str, list[str]] = {
    **CFB_TEAMS_BY_CONFERENCE,
    "Big East": [
        "Butler",
        "UConn",
        "Creighton",
        "DePaul",
        "Georgetown",
        "Marquette",
        "Providence",
        "Seton Hall",
        "St. John's",
        "Villanova",
        "Xavier",
    ],
}

# ESPN site API team ids (numeric string). Resolves roster + avoids slug 400s.
CFB_ESPN_TEAM_ID: dict[str, str] = {
    "Alabama": "333",
    "Arkansas": "8",
    "Auburn": "2",
    "Florida": "57",
    "Georgia": "61",
    "Kentucky": "96",
    "LSU": "99",
    "Ole Miss": "145",
    "Mississippi State": "344",
    "Missouri": "142",
    "Oklahoma": "201",
    "South Carolina": "2579",
    "Tennessee": "2633",
    "Texas": "251",
    "Texas A&M": "245",
    "Vanderbilt": "238",
    "Illinois": "356",
    "Indiana": "84",
    "Iowa": "2294",
    "Maryland": "120",
    "Michigan": "130",
    "Michigan State": "127",
    "Minnesota": "135",
    "Nebraska": "158",
    "Northwestern": "77",
    "Ohio State": "194",
    "Oregon": "2483",
    "Penn State": "213",
    "Purdue": "2509",
    "Rutgers": "164",
    "USC": "30",
    "UCLA": "26",
    "Washington": "264",
    "Wisconsin": "275",
    "Arizona": "12",
    "Arizona State": "9",
    "Baylor": "239",
    "BYU": "252",
    "Cincinnati": "2132",
    "Colorado": "38",
    "Houston": "248",
    "Iowa State": "66",
    "Kansas": "2305",
    "Kansas State": "2306",
    "Oklahoma State": "197",
    "TCU": "2628",
    "Texas Tech": "2641",
    "UCF": "2116",
    "West Virginia": "277",
    "Utah": "254",
    "Boston College": "103",
    "Cal": "25",
    "Clemson": "228",
    "Duke": "150",
    "Florida State": "52",
    "Georgia Tech": "59",
    "Louisville": "97",
    "Miami": "2390",
    "NC State": "152",
    "North Carolina": "153",
    "Notre Dame": "87",
    "Pittsburgh": "221",
    "SMU": "2567",
    "Stanford": "24",
    "Syracuse": "183",
    "Virginia": "258",
    "Virginia Tech": "259",
    "Wake Forest": "154",
}

NCAAB_ESPN_TEAM_ID: dict[str, str] = {
    **CFB_ESPN_TEAM_ID,
    "Butler": "2086",
    "UConn": "41",
    "Creighton": "156",
    "DePaul": "305",
    "Georgetown": "46",
    "Marquette": "269",
    "Providence": "2507",
    "Seton Hall": "2550",
    "St. John's": "2599",
    "Villanova": "222",
    "Xavier": "2752",
}

_TEAM_ALIASES: dict[str, str] = {
    "uconn": "UConn",
    "connecticut": "UConn",
    "florida st": "Florida State",
    "florida state": "Florida State",
    "nc state": "NC State",
    "north carolina state": "NC State",
    "ole miss": "Ole Miss",
    "texas a&m": "Texas A&M",
    "texas am": "Texas A&M",
    "miami (fl)": "Miami",
    "california": "Cal",
    "pit": "Pittsburgh",
    "pitt": "Pittsburgh",
    "st johns": "St. John's",
    "st. johns": "St. John's",
    "saint johns": "St. John's",
    "bc": "Boston College",
    "usc": "USC",
    "ucla": "UCLA",
    "byu": "BYU",
    "smu": "SMU",
    "ucf": "UCF",
    "tcu": "TCU",
    "lsu": "LSU",
}


def normalize_team_lookup_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def resolve_team_display_name(
    conference: str,
    team_query: str,
    sport: Literal["cfb", "ncaab"],
) -> str:
    table = CFB_TEAMS_BY_CONFERENCE if sport == "cfb" else NCAAB_TEAMS_BY_CONFERENCE
    conf_key = next(
        (k for k in table if k.lower() == conference.strip().lower()),
        None,
    )
    if not conf_key:
        raise ValueError(f"Unknown conference: {conference}")
    teams = table[conf_key]

    raw = team_query.strip()
    alias = _TEAM_ALIASES.get(normalize_team_lookup_key(raw))
    if alias and alias in teams:
        return alias

    key = normalize_team_lookup_key(raw)
    for t in teams:
        if normalize_team_lookup_name(t) == key:
            return t
    for t in teams:
        if key in normalize_team_lookup_name(t) or normalize_team_lookup_name(t).startswith(key):
            return t
    raise ValueError(f"Team {team_query!r} not found in conference {conference}")


def normalize_team_lookup_name(display: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", display.lower())


def espn_team_id(display_name: str, sport: Literal["cfb", "ncaab"]) -> str:
    table = CFB_ESPN_TEAM_ID if sport == "cfb" else NCAAB_ESPN_TEAM_ID
    if display_name not in table:
        raise KeyError(f"No ESPN id mapped for team {display_name!r}")
    return table[display_name]


def conference_containing_team(
    team_display: str, sport: Literal["cfb", "ncaab"]
) -> str:
    table = CFB_TEAMS_BY_CONFERENCE if sport == "cfb" else NCAAB_TEAMS_BY_CONFERENCE
    for conf, tlist in table.items():
        if team_display in tlist:
            return conf
    raise ValueError(f"Team {team_display!r} not in Power 5 configuration")


@dataclass
class CFBPlayer:
    player_name: str | None = None
    team: str | None = None
    conference: str | None = None
    position: str | None = None
    jersey_number: str | None = None
    age: int | None = None
    birth_date: str | None = None
    height: str | None = None
    weight: str | None = None
    hometown: str | None = None
    college: str | None = None
    class_year: str | None = None
    eligibility_years_remaining: int | None = None
    recruiting_stars: float | None = None
    recruiting_rank_national: int | None = None
    recruiting_rank_position: int | None = None
    transfer_portal_status: str | None = None
    previous_schools: list[str] | None = None
    career_stats: dict[str, Any] | None = None
    current_season_stats: dict[str, Any] | None = None
    heisman_votes: int | None = None
    all_american_count: int | None = None
    conference_awards: list[str] | None = None
    nil_valuation: str | None = None
    nil_ranking: str | None = None
    nil_deals: list[str] | None = None
    instagram_handle: str | None = None
    instagram_followers: int | str | None = None
    twitter_handle: str | None = None
    twitter_followers: int | str | None = None
    news_count_30d: int | str | None = None
    google_trends_score: float | str | None = None
    injury_history: list[str] | None = None
    current_injury_status: str | None = None
    data_quality_score: float | None = None
    collection_errors: list[str] = field(default_factory=list)
    collection_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NCAABPlayer:
    player_name: str | None = None
    team: str | None = None
    conference: str | None = None
    gender: Literal["mens", "womens"] | None = None
    position: str | None = None
    jersey_number: str | None = None
    age: int | None = None
    birth_date: str | None = None
    height: str | None = None
    weight: str | None = None
    hometown: str | None = None
    college: str | None = None
    class_year: str | None = None
    eligibility_years_remaining: int | None = None
    recruiting_stars: float | None = None
    recruiting_rank_national: int | None = None
    recruiting_rank_position: int | None = None
    transfer_portal_status: str | None = None
    previous_schools: list[str] | None = None
    career_stats: dict[str, Any] | None = None
    current_season_stats: dict[str, Any] | None = None
    ppg: float | str | None = None
    rpg: float | str | None = None
    apg: float | str | None = None
    fg_pct: float | str | None = None
    three_pt_pct: float | str | None = None
    ft_pct: float | str | None = None
    career_points: int | str | None = None
    career_rebounds: int | str | None = None
    career_assists: int | str | None = None
    all_american_count: int | None = None
    wooden_award_finalist: bool | str | None = None
    naismith_finalist: bool | str | None = None
    wnba_draft_projection: str | None = None
    nba_draft_projection: str | None = None
    nil_valuation: str | None = None
    nil_ranking: str | None = None
    nil_deals: list[str] | None = None
    instagram_handle: str | None = None
    instagram_followers: int | str | None = None
    twitter_handle: str | None = None
    twitter_followers: int | str | None = None
    news_count_30d: int | str | None = None
    google_trends_score: float | str | None = None
    injury_history: list[str] | None = None
    current_injury_status: str | None = None
    data_quality_score: float | None = None
    collection_errors: list[str] = field(default_factory=list)
    collection_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# ML shared schema — keep column names aligned with scraper JSON / CSV export.
# `gravity.ml.feature_engineer` consumes this set + optional runtime `sport`.
# ---------------------------------------------------------------------------

GRAVITY_ML_SPORT: tuple[str, ...] = ("cfb", "ncaab_mens", "ncaab_womens")

# Union of C FBPlayer and NCAABPlayer JSON keys (order stable for docs/tests).
GRAVITY_ML_RAW_FIELD_NAMES: tuple[str, ...] = (
    "sport",
    "age",
    "all_american_count",
    "apg",
    "birth_date",
    "career_assists",
    "career_points",
    "career_rebounds",
    "career_stats",
    "class_year",
    "collection_errors",
    "collection_timestamp",
    "college",
    "conference",
    "conference_awards",
    "current_injury_status",
    "current_season_stats",
    "data_quality_score",
    "eligibility_years_remaining",
    "fg_pct",
    "ft_pct",
    "gender",
    "google_trends_score",
    "height",
    "heisman_votes",
    "hometown",
    "injury_history",
    "instagram_followers",
    "instagram_handle",
    "jersey_number",
    "naismith_finalist",
    "nba_draft_projection",
    "news_count_30d",
    "nil_deals",
    "nil_ranking",
    "nil_valuation",
    "player_name",
    "position",
    "ppg",
    "previous_schools",
    "recruiting_rank_national",
    "recruiting_rank_position",
    "recruiting_stars",
    "rpg",
    "team",
    "three_pt_pct",
    "transfer_portal_status",
    "twitter_followers",
    "twitter_handle",
    "weight",
    "wooden_award_finalist",
    "wnba_draft_projection",
)


def count_scalar_errors(val: Any) -> bool:
    return val == "ERROR"


def compute_data_quality_score(
    record: dict[str, Any],
    tracked_fields: list[str],
) -> float:
    total = len(tracked_fields)
    if total == 0:
        return 0.0
    good = 0
    for k in tracked_fields:
        v = record.get(k)
        if v is None or v == "ERROR":
            continue
        if isinstance(v, (list, dict)) and not v:
            continue
        good += 1
    return round(good / total, 4)


def field_completeness_percent(
    rows: list[dict[str, Any]], fields: list[str]
) -> dict[str, str]:
    if not rows:
        return {f: "0%" for f in fields}
    out: dict[str, str] = {}
    n = len(rows)
    for f in fields:
        ok = 0
        for r in rows:
            v = r.get(f)
            if v is None or v == "ERROR":
                continue
            if isinstance(v, (list, dict)) and len(v) == 0:
                continue
            ok += 1
        out[f] = f"{100 * ok // n}%" if n else "0%"
    return out
