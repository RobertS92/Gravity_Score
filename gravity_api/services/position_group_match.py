"""
Position group filters: `athletes.position_group` is often NULL while `position`
holds abbreviations (WR, DE, OT, G, …). Match either column so UI groups work.

IMPORTANT: Football and basketball share tokens (`G`, `C`). Without a sport,
this module keeps the historical football-first mapping (`G`/`C` → OL) for
watchlist/search callers that only know a group code. Callers that know the
athlete's sport MUST pass `sport` so basketball guards resolve to PG/SG and
centers to C — never OL.
"""

from __future__ import annotations

from typing import Any, List, Tuple

# Uppercase keys = Watchlist / market scan dropdown values.
# Values = allowed UPPER(TRIM(athletes.position)) matches for that group.
_POSITION_GROUP_ABBREVS: dict[str, list[str]] = {
    # Football
    "QB": ["QB", "QUARTERBACK"],
    "RB": ["RB", "FB", "TB", "FULLBACK", "RUNNING BACK"],
    "WR": ["WR", "WIDE RECEIVER"],
    "TE": ["TE", "TIGHT END"],
    "OL": [
        "OL",
        "OT",
        "OG",
        "OC",
        "C",
        "G",
        "T",
        "LT",
        "RT",
        "LG",
        "RG",
        "IOL",
        "C/G",
        "OG/C",
        "OT/OG",
        "OL/DL",
    ],
    "DL": ["DL", "DE", "DT", "NT", "EDGE", "DE/OLB", "DT/DE", "DL/LB"],
    "LB": ["LB", "ILB", "OLB", "MLB", "WLB", "SLB", "LOLB", "ROLB", "MIKE", "SAM", "WILL"],
    "DB": ["DB", "CB", "S", "FS", "SS", "SAF", "NICKEL", "STAR", "NB", "DS"],
    "K": ["K", "PK", "P", "LS", "K/P", "K/K", "PLACE KICKER", "PUNTER"],
    # Basketball (sport-agnostic lookup only — prefer sport-aware APIs below)
    "PG": ["PG", "G", "POINT GUARD"],
    "SG": ["SG", "G", "SHOOTING GUARD"],
    "SF": ["SF", "SMALL FORWARD"],
    "PF": ["PF", "POWER FORWARD"],
    "C": ["C", "CENTER"],
}


def canonical_feature_sport(sport: str | None) -> str | None:
    """Map UI/DB sport tokens (NCAAW, wcbb, …) to feature-engineering slugs."""
    if not sport:
        return None
    from gravity_api.feature_engineering.positions import SPORT_POSITION_GROUPS
    from gravity_api.services.partner_sports import (
        normalize_db_sport_slug,
        partner_codes_to_db_slugs,
    )

    for slug in partner_codes_to_db_slugs([str(sport)]):
        canon = normalize_db_sport_slug(slug)
        if canon in SPORT_POSITION_GROUPS:
            return canon
    canon = normalize_db_sport_slug(str(sport))
    return canon if canon in SPORT_POSITION_GROUPS else None


def position_aliases_for_group(
    position_group: str,
    sport: str | None = None,
) -> list[str]:
    """Normalized uppercase tokens to match against `athletes.position`."""
    feature_sport = canonical_feature_sport(sport)
    if feature_sport:
        from gravity_api.feature_engineering.positions import position_aliases

        return position_aliases(position_group, feature_sport)

    key = position_group.strip().upper()
    return _POSITION_GROUP_ABBREVS.get(key, [key])


def derive_position_group(
    position: str | None,
    sport: str | None = None,
) -> str | None:
    """Best-effort canonical group from raw position token(s).

    When ``sport`` is provided, uses sport-aware mapping (basketball ``G`` → PG,
    not football OL). Without sport, keeps football-first legacy behavior.
    """
    feature_sport = canonical_feature_sport(sport)
    if feature_sport:
        from gravity_api.feature_engineering.positions import (
            derive_position_group as sport_aware_derive,
        )

        return sport_aware_derive(position, feature_sport)

    if not position:
        return None
    token = position.strip().upper()
    if not token:
        return None
    candidates = {part.strip() for part in token.split("/") if part.strip()}
    candidates.add(token)
    for group, aliases in _POSITION_GROUP_ABBREVS.items():
        alias_set = set(aliases)
        if candidates.intersection(alias_set):
            return group
    return token


def position_group_valid_for_sport(position_group: str | None, sport: str | None) -> bool:
    """True when the group is allowed for the sport (or sport is unknown)."""
    if not position_group:
        return False
    feature_sport = canonical_feature_sport(sport)
    if not feature_sport:
        return True
    from gravity_api.feature_engineering.positions import SPORT_POSITION_GROUPS

    allowed = SPORT_POSITION_GROUPS.get(feature_sport, ())
    return position_group.strip().upper() in allowed


def position_group_sql_predicate(
    position_group: str,
    idx: int,
    *,
    table_alias: str = "a",
    sport: str | None = None,
) -> Tuple[str, List[Any], int]:
    """
    SQL fragment and params for (position_group match OR position in alias list).

    Returns (sql, params_to_extend, next_param_index).
    """
    key = position_group.strip().upper()
    aliases = position_aliases_for_group(position_group, sport)
    t = table_alias
    # Slash-separated roles (WR/KR, OT/OG) match if any token is in the alias list.
    sql = (
        f"(UPPER(TRIM(COALESCE({t}.position_group, ''))) = ${idx} "
        f"OR UPPER(TRIM(COALESCE({t}.position, ''))) = ANY(${idx + 1}::text[]) "
        f"OR string_to_array(UPPER(TRIM(COALESCE({t}.position, ''))), '/') "
        f"&& ${idx + 1}::text[])"
    )
    return sql, [key, aliases], idx + 2
