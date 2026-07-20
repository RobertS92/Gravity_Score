"""Position groups and aliases for all target sports."""

from __future__ import annotations

from gravity_api.services.position_group_match import (
    _POSITION_GROUP_ABBREVS as _FB_BB_ALIASES,
    derive_position_group as _derive_fb_bb,
)

# Football — college + pro (all skill/line positions)
FOOTBALL_POSITIONS = ("QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB", "K")

# Basketball — college + pro
BASKETBALL_POSITIONS = ("PG", "SG", "SF", "PF", "C")

# Basketball position aliases. Ordered specific → generic so that a precise
# ESPN position ("PG") resolves exactly, while coarse tokens ("G", "F") — which
# is all ESPN exposes for many players — still map to a valid cohort. NOTE: the
# shared football matcher maps "G"/"C" to the offensive line (OL), so basketball
# MUST use this table instead of delegating to it.
BASKETBALL_ALIASES: dict[str, list[str]] = {
    "PG": ["PG", "POINT GUARD"],
    "SG": ["SG", "SHOOTING GUARD"],
    "SF": ["SF", "SMALL FORWARD"],
    "PF": ["PF", "POWER FORWARD"],
    "C": ["C", "CENTER"],
}
# Coarse/ambiguous tokens → default cohort (guards and forwards share stat
# profiles within their tier, so a deterministic default is acceptable).
_BASKETBALL_GENERIC: dict[str, str] = {
    "G": "PG",
    "GUARD": "PG",
    "F": "SF",
    "FORWARD": "SF",
    "W": "SF",
    "WING": "SF",
    "B": "C",
    "BIG": "C",
    "FC": "C",
    "CF": "C",
    "GF": "SF",
    "FG": "SF",
}


def _derive_basketball_group(position: str) -> str | None:
    token = position.strip().upper()
    if not token:
        return None
    parts = [p.strip() for p in token.replace("-", "/").split("/") if p.strip()]
    candidates = list(dict.fromkeys([token, *parts]))  # preserve order, dedupe
    # Specific alias match first.
    for cand in candidates:
        for group, aliases in BASKETBALL_ALIASES.items():
            if cand in aliases:
                return group
    # Generic/coarse fallback (e.g. "G", "F", "G/F").
    for cand in candidates:
        norm = cand.replace("/", "").replace(" ", "")
        if norm in _BASKETBALL_GENERIC:
            return _BASKETBALL_GENERIC[norm]
        if cand in _BASKETBALL_GENERIC:
            return _BASKETBALL_GENERIC[cand]
    return None

# Baseball
BASEBALL_ALIASES: dict[str, list[str]] = {
    "SP": ["SP", "STARTER", "STARTING PITCHER"],
    "RP": ["RP", "MR", "SU", "CL", "CLOSER", "RELIEF", "RELIEVER", "P"],
    "C": ["C", "CATCHER"],
    "IF": ["IF", "1B", "2B", "3B", "SS", "INF", "INFIELD", "INFIELDER"],
    "OF": ["OF", "LF", "CF", "RF", "OUTFIELD", "OUTFIELDER"],
    "UT": ["UT", "UTIL", "UTILITY", "DH", "DESIGNATED HITTER"],
}
BASEBALL_POSITIONS = tuple(BASEBALL_ALIASES.keys())

# Volleyball (women's college)
VOLLEYBALL_ALIASES: dict[str, list[str]] = {
    "OH": ["OH", "OUTSIDE HITTER", "OUTSIDE"],
    "MB": ["MB", "MIDDLE", "MIDDLE BLOCKER"],
    "S": ["S", "SETTER"],
    "LIB": ["LIB", "L", "LIBERO", "DS", "DEFENSIVE SPECIALIST"],
    "OPP": ["OPP", "OPPOSITE", "RIGHT SIDE", "RS"],
}
VOLLEYBALL_POSITIONS = tuple(VOLLEYBALL_ALIASES.keys())

SPORT_POSITION_GROUPS: dict[str, tuple[str, ...]] = {
    "cfb": FOOTBALL_POSITIONS,
    "nfl": FOOTBALL_POSITIONS,
    "ncaab_mens": BASKETBALL_POSITIONS,
    "ncaab_womens": BASKETBALL_POSITIONS,
    "nba": BASKETBALL_POSITIONS,
    "wnba": BASKETBALL_POSITIONS,
    "ncaa_baseball": BASEBALL_POSITIONS,
    "ncaa_volleyball": VOLLEYBALL_POSITIONS,
}

SPORT_LEAGUE: dict[str, str] = {
    "cfb": "ncaa",
    "ncaab_mens": "ncaa",
    "ncaab_womens": "ncaa",
    "ncaa_baseball": "ncaa",
    "ncaa_volleyball": "ncaa",
    "nfl": "nfl",
    "nba": "nba",
    "wnba": "wnba",
}


def position_aliases(position_group: str, sport: str) -> list[str]:
    key = position_group.strip().upper()
    if sport in ("ncaab_mens", "ncaab_womens", "nba", "wnba"):
        aliases = list(BASKETBALL_ALIASES.get(key, [key]))
        aliases += [tok for tok, grp in _BASKETBALL_GENERIC.items() if grp == key]
        return list(dict.fromkeys(aliases))
    if sport in ("cfb", "nfl"):
        return _FB_BB_ALIASES.get(key, [key])
    if sport == "ncaa_baseball":
        return BASEBALL_ALIASES.get(key, [key])
    if sport == "ncaa_volleyball":
        return VOLLEYBALL_ALIASES.get(key, [key])
    return [key]


def derive_position_group(position: str | None, sport: str) -> str | None:
    if not position:
        return None
    token = position.strip().upper()
    if not token:
        return None
    candidates = {part.strip() for part in token.split("/") if part.strip()}
    candidates.add(token)

    if sport in ("ncaab_mens", "ncaab_womens", "nba", "wnba"):
        return _derive_basketball_group(position)

    if sport in ("cfb", "nfl"):
        return _derive_fb_bb(position)

    alias_map = BASEBALL_ALIASES if sport == "ncaa_baseball" else VOLLEYBALL_ALIASES
    for group, aliases in alias_map.items():
        if candidates.intersection(set(aliases)):
            return group
    return token


def cohort_key(
    *,
    league: str,
    sport: str,
    position_group: str,
    season_year: int | None,
    window: str = "season",
) -> str:
    season = str(season_year) if season_year is not None else "all"
    return f"{league}:{sport}:{position_group}:{season}:{window}"
