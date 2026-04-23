"""
Position group filters: `athletes.position_group` is often NULL while `position`
holds abbreviations (WR, DE, OT, …). Match either column so UI groups (QB, TE, OL, …) work.
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
    # Basketball
    "PG": ["PG", "G", "POINT GUARD"],
    "SG": ["SG", "G", "SHOOTING GUARD"],
    "SF": ["SF", "SMALL FORWARD"],
    "PF": ["PF", "POWER FORWARD"],
    "C": ["C", "CENTER"],
}


def position_aliases_for_group(position_group: str) -> list[str]:
    """Normalized uppercase tokens to match against `athletes.position`."""
    key = position_group.strip().upper()
    return _POSITION_GROUP_ABBREVS.get(key, [key])


def position_group_sql_predicate(
    position_group: str,
    idx: int,
    *,
    table_alias: str = "a",
) -> Tuple[str, List[Any], int]:
    """
    SQL fragment and params for (position_group match OR position in alias list).

    Returns (sql, params_to_extend, next_param_index).
    """
    key = position_group.strip().upper()
    aliases = position_aliases_for_group(position_group)
    t = table_alias
    # Slash-separated roles (WR/KR, OT/OG) match if any token is in the alias list.
    sql = (
        f"(UPPER(TRIM(COALESCE({t}.position_group, ''))) = ${idx} "
        f"OR UPPER(TRIM(COALESCE({t}.position, ''))) = ANY(${idx + 1}::text[]) "
        f"OR string_to_array(UPPER(TRIM(COALESCE({t}.position, ''))), '/') "
        f"&& ${idx + 1}::text[])"
    )
    return sql, [key, aliases], idx + 2
