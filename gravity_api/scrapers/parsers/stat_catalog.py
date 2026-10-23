"""Canonical stat keys per sport — scoring keys + extended scrape targets.

Each key carries ``is_counting`` (SCRAPER_FIX_SPEC §4.2): counting stats are
summed into ``athlete_career_stats``; rate stats are recomputed via
``derive_rates``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

# Extended stats scraped and stored even when not weighted in proof composites.
EXTENDED_STATS: dict[str, tuple[str, ...]] = {
    "cfb": (
        "pass_attempts",
        "pass_completions",
        "pass_cmp_pct",
        "pass_yards_per_attempt",
        "pass_long",
        "pass_sacks",
        "pass_sack_yards_lost",
        "rush_attempts",
        "rush_long",
        "rec_targets",
        "rec_long",
        "scrimmage_plays",
        "total_tackles",
        "solo_tackles",
        "assist_tackles",
        "passes_defended",
        "forced_fumbles",
        "fumble_recoveries",
        "defensive_td",
        "qb_hurries",
        "fg_attempts",
        "fg_missed",
        "xp_attempts",
        "punt_attempts",
        "punt_yards",
        "kickoff_touchbacks",
        "snaps",
        "snap_pct",
    ),
    "nfl": (
        "gp",
        "gs",
        "games_started",
        "games_played_season",
        "pass_attempts",
        "pass_completions",
        "pass_cmp_pct",
        "pass_yards_per_attempt",
        "pass_long",
        "pass_sacks",
        "rush_attempts",
        "rec_targets",
        "total_tackles",
        "solo_tackles",
        "passes_defended",
        "forced_fumbles",
        "epa_per_play",
        "epa_pass",
        "epa_rush",
        "snap_count",
        "snap_pct",
        "fg_attempts",
        "punt_yards",
    ),
    "ncaab_mens": (
        "min",
        "gp",
        "games_started",
        "gs",
        "fgm",
        "fga",
        "fg_pct",
        "fg3m",
        "fg3a",
        "ftm",
        "fta",
        "ft_pct",
        "oreb",
        "dreb",
        "pf",
        "eff",
        "per",
        "bpm",
        "usage",
        "ts_pct",
        "efg_pct",
        "ast_to_ratio",
        "double_doubles",
        "triple_doubles",
    ),
    "ncaab_womens": (
        "min",
        "gp",
        "games_started",
        "gs",
        "fgm",
        "fga",
        "fg_pct",
        "fg3m",
        "fg3a",
        "ftm",
        "fta",
        "ft_pct",
        "oreb",
        "dreb",
        "pf",
        "eff",
        "per",
        "bpm",
        "usage",
        "ts_pct",
        "double_doubles",
    ),
    "nba": (
        "min",
        "gp",
        "games_started",
        "gs",
        "fgm",
        "fga",
        "fg_pct",
        "fg3m",
        "fg3a",
        "ftm",
        "fta",
        "ft_pct",
        "oreb",
        "dreb",
        "pf",
        "per",
        "bpm",
        "usage",
        "ts_pct",
        "efg_pct",
        "ast_to_ratio",
        "double_doubles",
        "triple_doubles",
        "plus_minus",
        "pie",
        "vorp",
        "ws",
        "ws_per_48",
    ),
    "wnba": (
        "min",
        "gp",
        "games_started",
        "gs",
        "fgm",
        "fga",
        "fg_pct",
        "fg3m",
        "fg3a",
        "ftm",
        "fta",
        "ft_pct",
        "oreb",
        "dreb",
        "pf",
        "per",
        "bpm",
        "usage",
        "ts_pct",
        "double_doubles",
        "plus_minus",
    ),
    "ncaa_baseball": (
        "g",
        "gs",
        "ab",
        "r",
        "h",
        "hr",
        "rbi",
        "bb",
        "so",
        "hbp",
        "sf",
        "sb",
        "cs",
        "avg",
        "obp",
        "slg",
        "ops",
        "whip",
        "k9",
        "bb9",
        "k_bb",
        "w",
        "l",
        "sv",
        "bs",
        "hld",
        "ip",
        "h_allowed",
        "er",
        "era",
        "fielding_pct",
        "errors",
        "rf_assists",
        "cs_pct",
        "pickoffs",
    ),
    "ncaa_volleyball": (
        "gp",
        "sets_played",
        "kills",
        "kills_per_set",
        "errors",
        "total_attacks",
        "hitting_pct",
        "assists",
        "assists_per_set",
        "aces",
        "service_errors",
        "blocks",
        "blocks_per_set",
        "block_errors",
        "digs",
        "digs_per_set",
        "reception_errors",
        "receive_rating",
        "setting_efficiency",
        "points",
        "points_per_set",
    ),
}

# Tokens that mark a key as a rate / average (not summable across seasons).
# Mirrors the SQL exclusion in migrations/038_athlete_season_stats_v2.sql.
_RATE_TOKENS: tuple[str, ...] = (
    "avg",
    "pct",
    "percent",
    "rate",
    "per_game",
    "pergame",
    "per_attempt",
    "per_carry",
    "per_catch",
    "yards_per",
    "passer_rating",
    "per_set",
    "usage",
    "ts_pct",
    "efg",
    "whip",
    "obp",
    "slg",
    "ops",
    "k9",
    "bb9",
    "k_bb",
    "snap_pct",
    "receive_rating",
    "setting_efficiency",
    "hitting_pct",
    "fielding_pct",
    "completion_pct",
    "ws_per_48",
    "ast_to_ratio",
    "epa_per_play",
)

# Exact keys that are rates even when token match is ambiguous.
_RATE_EXACT: frozenset[str] = frozenset(
    {
        "rating",
        "long",
        "pass_long",
        "rush_long",
        "rec_long",
        "long_fg",
        "bpm",
        "per",
        "era",
        "avg",
        "qbr",
        "pie",
        "vorp",
        "ws",
        "eff",
        "plus_minus",
    }
)


@dataclass(frozen=True)
class StatKeyInfo:
    """Metadata for one canonical stat key."""

    key: str
    is_counting: bool


def is_counting(stat_key: str) -> bool:
    """True when ``stat_key`` is a summable counting stat (not a rate/average)."""
    key = str(stat_key or "").strip()
    if not key:
        return False
    kl = key.lower()
    if kl in _RATE_EXACT:
        return False
    if any(tok in kl for tok in _RATE_TOKENS):
        return False
    # Season-long max / non-summable "long" suffix.
    if kl.endswith("_long") or kl.startswith("long_"):
        return False
    return True


def _scoring_keys_for_sport(sport: str) -> set[str]:
    from gravity_api.feature_engineering.sport_specs import get_sport_spec

    try:
        spec = get_sport_spec(sport)
    except KeyError:
        return set()
    keys: set[str] = set()
    for pg in spec.position_groups:
        for sw in pg.performance_stats:
            keys.add(sw.stat_key)
        keys.update(pg.recruiting_stats)
    return keys


def all_stat_keys_for_sport(sport: str) -> frozenset[str]:
    """Union of proof-weighted keys + extended scrape keys for a sport."""
    keys = _scoring_keys_for_sport(sport)
    keys.update(EXTENDED_STATS.get(sport, ()))
    keys.add("games_played_season")
    keys.add("games_played_career")
    keys.add("games_started")
    keys.add("gs")
    keys.add("gp")
    return frozenset(keys)


def stat_key_info_for_sport(sport: str) -> dict[str, StatKeyInfo]:
    """Map every known key for ``sport`` to ``StatKeyInfo`` (includes ``is_counting``)."""
    return {
        key: StatKeyInfo(key=key, is_counting=is_counting(key))
        for key in all_stat_keys_for_sport(sport)
    }


def counting_keys_for_sport(sport: str) -> frozenset[str]:
    return frozenset(k for k in all_stat_keys_for_sport(sport) if is_counting(k))


def filter_counting_stats(stats: dict[str, float]) -> dict[str, float]:
    """Drop rate/average keys from a flat stats dict."""
    return {k: v for k, v in stats.items() if is_counting(k)}


def _safe_div(num: float | None, den: float | None) -> float | None:
    if num is None or den is None:
        return None
    if den == 0:
        return None
    return float(num) / float(den)


def derive_rates(sport: str, totals: dict[str, float]) -> dict[str, float]:
    """Recompute rate stats from counting totals (never average rates across seasons).

    ``totals`` should be career or season counting sums (e.g. from
    ``athlete_career_stats``). Returns only derived rate keys that can be
    computed from the provided counts.
    """
    t = {str(k): float(v) for k, v in totals.items() if v is not None}
    out: dict[str, float] = {}

    gp = t.get("gp") or t.get("games_played_season") or t.get("g")
    pts = t.get("pts") or t.get("points")
    reb = t.get("reb") or (
        (t["oreb"] + t["dreb"]) if "oreb" in t and "dreb" in t else t.get("reb")
    )
    ast = t.get("ast") or t.get("assists")

    for key, num, den in (
        ("ppg", pts, gp),
        ("rpg", reb, gp),
        ("apg", ast, gp),
        ("fg_pct", t.get("fgm"), t.get("fga")),
        ("fg3_pct", t.get("fg3m"), t.get("fg3a")),
        ("ft_pct", t.get("ftm"), t.get("fta")),
        (
            "pass_cmp_pct",
            t.get("pass_completions"),
            t.get("pass_attempts"),
        ),
        (
            "pass_yards_per_attempt",
            t.get("pass_yards"),
            t.get("pass_attempts"),
        ),
        (
            "yards_per_carry",
            t.get("rush_yards"),
            t.get("rush_attempts"),
        ),
        (
            "yards_per_catch",
            t.get("rec_yards"),
            t.get("receptions"),
        ),
        (
            "kills_per_set",
            t.get("kills"),
            t.get("sets_played"),
        ),
        (
            "assists_per_set",
            t.get("assists"),
            t.get("sets_played"),
        ),
        (
            "blocks_per_set",
            t.get("blocks"),
            t.get("sets_played"),
        ),
        (
            "digs_per_set",
            t.get("digs"),
            t.get("sets_played"),
        ),
        (
            "points_per_set",
            t.get("points"),
            t.get("sets_played"),
        ),
    ):
        derived = _safe_div(num, den)
        if derived is not None:
            out[key] = derived

    # Baseball rates from counting components when present.
    ab = t.get("ab")
    h = t.get("h")
    bb = t.get("bb")
    hbp = t.get("hbp")
    sf = t.get("sf")
    hr = t.get("hr")
    if ab and ab > 0 and h is not None:
        out["avg"] = h / ab
    obp_den = None
    if ab is not None:
        obp_den = ab + (bb or 0) + (hbp or 0) + (sf or 0)
    if obp_den and obp_den > 0 and h is not None:
        out["obp"] = (h + (bb or 0) + (hbp or 0)) / obp_den
    ip = t.get("ip")
    er = t.get("er")
    if ip and ip > 0 and er is not None:
        out["era"] = 9.0 * er / ip
    if ip and ip > 0:
        walks = bb or 0
        hits_allowed = t.get("h_allowed")
        if hits_allowed is not None:
            out["whip"] = (walks + hits_allowed) / ip

    _ = (sport, hr)  # sport is part of the §4.2 API; hr reserved for richer SLG
    return out


def counting_keys(keys: Iterable[str]) -> frozenset[str]:
    return frozenset(k for k in keys if is_counting(k))


__all__ = [
    "EXTENDED_STATS",
    "StatKeyInfo",
    "all_stat_keys_for_sport",
    "counting_keys",
    "counting_keys_for_sport",
    "derive_rates",
    "filter_counting_stats",
    "is_counting",
    "stat_key_info_for_sport",
]
