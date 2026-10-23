"""Map ESPN stat labels to canonical keys and flatten scrape payloads."""

from __future__ import annotations

import re
from typing import Any

from gravity_api.scrapers.parsers.stat_catalog import all_stat_keys_for_sport

_PERCENT_RE = re.compile(r"^([\d.]+)\s*%$")
_NUMBER_RE = re.compile(r"^[\d,]+(?:\.\d+)?$")


def parse_stat_value(raw: Any) -> float | None:
    """Coerce ESPN stat display values to float."""
    if raw is None or raw == "" or raw == "-":
        return None
    if isinstance(raw, bool):
        return float(raw)
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace(",", "")
    if not text:
        return None
    m = _PERCENT_RE.match(text)
    if m:
        return float(m.group(1))
    if text.endswith("%"):
        try:
            return float(text[:-1])
        except ValueError:
            return None
    if ":" in text and text.count(":") == 1:
        # innings pitched e.g. 45.1 — keep as decimal approximation
        parts = text.split(":")
        try:
            return float(parts[0]) + float(parts[1]) / 10.0
        except ValueError:
            pass
    try:
        return float(text)
    except ValueError:
        return None


# Ambiguous bare labels removed from flat aliases (WP2 / B4): Avg, INT, TD, YDS,
# Long, Rating. Map those only via (category, stat) pairs or unambiguous camelCase.


def _alias_table() -> dict[str, dict[str, tuple[str, ...]]]:
    """Flat ESPN label/abbreviation aliases → canonical key (legacy callers).

    Ambiguous abbreviations without a category (Avg/INT/TD/YDS/Long/Rating) are
    intentionally omitted. Prefer ``normalize_namespaced_stats`` for new paths.
    """
    football = {
        "pass_yards": (
            "passingYards",
            "passYards",
            "pass_yards",
            "Pass Yds",
            "Passing Yards",
            "pass yds",
        ),
        "pass_td": ("passingTouchdowns", "passTD", "Pass TD", "pass td"),
        "pass_int": ("passINT", "Pass INT", "pass int", "passingInterceptions"),
        "pass_attempts": ("passingAttempts", "ATT", "passAtt", "Pass Att"),
        "pass_completions": ("completions", "CMP", "passCmp", "Pass Cmp"),
        "completion_pct": ("completionPct", "CMP%", "Comp %", "completionPercentage"),
        # ESPN exposes the standard 0-158.3 passer rating as "QBRating"; "ESPNQBRating"
        # is a different cumulative points metric (can be 50k+) and must NOT be used.
        "passer_rating": ("QBRating", "passerRating", "RTG", "pass rating"),
        "qbr": ("QBR", "qbr", "adjQBR"),
        "pass_yards_per_attempt": ("yardsPerPassAttempt", "YPA"),
        "pass_long": ("longPass", "longPassing"),
        # QB sacks taken — never alias bare "sacks" (that is defensive).
        "pass_sacks": ("sacksTaken", "sacked", "sackYardsLost", "SacksTaken"),
        "rush_yards": ("rushingYards", "rushYards", "RUSH YDS", "Rush Yds"),
        "rush_attempts": ("rushingAttempts", "CAR", "rushAtt", "Rush Att"),
        "rush_td": ("rushingTouchdowns", "rushTD", "Rush TD"),
        "yards_per_carry": ("yardsPerRushAttempt", "YPC", "rush avg"),
        "rush_long": ("longRushing", "longRush"),
        "rec_yards": ("receivingYards", "recYards", "REC YDS", "Rec Yds"),
        "receptions": ("receptions", "REC", "rec"),
        "rec_td": ("receivingTouchdowns", "recTD", "Rec TD"),
        "rec_targets": ("receivingTargets", "TGTS", "Targets"),
        "yards_per_catch": ("yardsPerReception", "Y/R"),
        "scrimmage_yards": ("scrimmageYards", "SCRIM YDS", "Scrimmage Yds"),
        "fumbles": ("fumbles", "FUM", "fumblesLost"),
        "tackles": ("totalTackles", "TOT", "tackles", "Tackles"),
        "solo_tackles": ("soloTackles", "SOLO"),
        "assist_tackles": ("assistTackles", "AST"),
        # Defensive sacks only — avgSackYards / sackYards must NOT map here.
        "sacks": ("sacks", "SACK", "sackTotal", "totalSacks"),
        "tfl": ("tacklesForLoss", "TFL", "tfl", "tackles_for_loss"),
        "stuffs": ("stuffs", "STUFF", "runStuffs"),
        "qb_hits": ("qbHits", "QBH"),
        "qb_hurries": ("hurries", "HUR"),
        # Bare "interceptions" maps defensive; QB packs remapped when pass_yards present.
        # Do not alias bare INT/int (ambiguous with pass_int without category).
        "interceptions": ("interceptions",),
        "passes_defended": ("passesDefended", "PD", "pass def"),
        "forced_fumbles": ("forcedFumbles", "FF"),
        "completion_pct_allowed": ("cmpPctAllowed", "Cmp% Allowed"),
        "fg_pct": ("fieldGoalPct", "FG%", "FG Pct"),
        "fg_made": ("fieldGoalsMade", "FGM", "FG Made"),
        "fg_attempts": ("fieldGoalAttempts", "FGA"),
        "xp_pct": ("extraPointPct", "XP%", "XP Pct"),
        "xp_attempts": ("extraPointAttempts", "XPA"),
        "long_fg": ("longFieldGoal", "Long FG", "longFG"),
        "punt_avg": ("grossAvgPuntYards", "Punt Avg", "punt avg"),
        "punt_yards": ("puntYards", "Punt Yds"),
        "punt_attempts": ("punts", "Punts"),
        "games_started": ("gamesStarted", "GS"),
        "games_played_season": ("gamesPlayed", "GP", "G", "games"),
        "snap_count": ("snapCounts", "Snaps", "snaps"),
        "epa_per_play": ("epa", "EPA", "epaPerPlay"),
    }
    basketball = {
        "pts": ("points", "PTS", "Pts", "pointsPerGame", "PPG"),
        "ast": ("assists", "AST", "Ast", "assistsPerGame"),
        "reb": ("totalRebounds", "rebounds", "REB", "Reb"),
        "oreb": ("offensiveRebounds", "OR", "OREB"),
        "dreb": ("defensiveRebounds", "DR", "DREB"),
        "stl": ("steals", "STL", "Stl"),
        "blk": ("blocks", "BLK", "Blk"),
        "to": ("turnovers", "TO", "TOV"),
        "pf": ("fouls", "PF", "personalFouls"),
        "fgm": ("fieldGoalsMade", "FGM"),
        "fga": ("fieldGoalsAttempted", "FGA"),
        "fg_pct": ("fieldGoalPct", "FG%", "FG Pct"),
        "fg3m": ("threePointFieldGoalsMade", "3PM", "3PTM"),
        "fg3a": ("threePointFieldGoalsAttempted", "3PA", "3PTA"),
        "three_pct": ("threePointFieldGoalPct", "3P%", "3PT%"),
        "ftm": ("freeThrowsMade", "FTM"),
        "fta": ("freeThrowsAttempted", "FTA"),
        "ft_pct": ("freeThrowPct", "FT%", "FT Pct"),
        "ts_pct": ("trueShootingPct", "TS%", "trueShootingPercentage"),
        "efg_pct": ("effectiveFieldGoalPct", "eFG%"),
        "min": ("minutes", "MIN", "Min", "minutesPerGame"),
        "gp": ("gamesPlayed", "GP", "G"),
        "games_played_season": ("gamesPlayed", "GP", "G"),
        "games_started": ("gamesStarted", "GS", "starts"),
        "double_doubles": ("doubleDouble", "doubleDoubles", "DD"),
        "triple_doubles": ("tripleDouble", "tripleDoubles"),
        "per": ("playerEfficiencyRating", "PER"),
        "bpm": ("boxPlusMinus", "BPM"),
        "usage": ("usageRate", "USG%", "usage"),
        "plus_minus": ("plusMinus", "+/-", "plusMinusRating"),
        "pie": ("pie", "PIE"),
        "ast_to_ratio": ("assistTurnoverRatio", "AST/TO"),
    }
    baseball = {
        "era": ("earnedRunAvg", "ERA"),
        "whip": ("WHIP", "whip"),
        "k9": ("strikeoutsPerNineInnings", "K/9", "K9"),
        "bb9": ("walksPerNineInnings", "BB/9", "BB9"),
        "ip": ("innings", "IP", "inningsPitched"),
        "wins": ("wins", "W"),
        "l": ("losses", "L"),
        "saves": ("saves", "SV"),
        "bs": ("blownSaves", "BS"),
        "hld": ("holds", "HLD"),
        "so": ("strikeouts", "SO", "K"),
        "bb": ("walks", "BB", "baseOnBalls"),
        "h": ("hits", "H"),
        "hr": ("homeRuns", "HR"),
        "rbi": ("RBIs", "RBI"),
        "r": ("runs", "R"),
        "avg": ("avg", "AVG", "battingAverage"),
        "obp": ("OBP", "onBasePct", "onBasePercentage"),
        "slg": ("SLG", "sluggingPct", "sluggingPercentage"),
        "ops": ("OPS", "onBasePlusSlugging"),
        "sb": ("stolenBases", "SB"),
        "cs": ("caughtStealing", "CS"),
        "fielding_pct": ("fieldingPct", "FLD%", "fieldingPercentage"),
        "cs_pct": ("caughtStealingPct", "CS%"),
        "rf_assists": ("outfieldAssists", "A"),
        "er": ("earnedRuns", "ER"),
        "h_allowed": ("hitsAllowed", "H"),
        "ab": ("atBats", "AB"),
        "g": ("gamesPlayed", "G"),
        "gs": ("gamesStarted", "GS"),
        "games_played_season": ("gamesPlayed", "G", "GP"),
    }
    volleyball = {
        "kills": ("kills", "K", "Kills"),
        "kills_per_set": ("killsPerSet", "K/S", "KPS"),
        "hitting_pct": ("hittingPct", "HIT%", "Hitting %", "attackPct"),
        "errors": ("attackErrors", "E", "Err"),
        "total_attacks": ("attackAttempts", "TA", "Attacks"),
        "assists": ("assists", "A", "Assists"),
        "assists_per_set": ("assistsPerSet", "A/S", "APS"),
        "aces": ("serviceAces", "SA", "Aces"),
        "service_errors": ("serviceErrors", "SE"),
        "blocks": ("blocks", "BLK", "Total Blocks"),
        "blocks_per_set": ("blocksPerSet", "B/S", "BPS"),
        "digs": ("digs", "D", "Digs"),
        "digs_per_set": ("digsPerSet", "D/S", "DPS"),
        "receive_rating": ("receptionRating", "Recv Rtg"),
        "setting_efficiency": ("settingEfficiency", "Set Eff"),
        "gp": ("gamesPlayed", "GP"),
        "sets_played": ("sets", "Sets"),
        "games_played_season": ("gamesPlayed", "GP"),
        "points": ("points", "PTS"),
        "points_per_set": ("pointsPerSet", "P/S"),
    }
    return {
        "cfb": football,
        "nfl": football,
        "ncaab_mens": basketball,
        "ncaab_womens": basketball,
        "nba": basketball,
        "wnba": basketball,
        "ncaa_baseball": baseball,
        "ncaa_volleyball": volleyball,
    }


def _category_pair_table() -> dict[str, dict[tuple[str, str], str]]:
    """Map ``(category, espn_stat_name)`` → canonical key per sport family.

    Category and stat names are matched after ``_normalize_key``.
    """
    football_pairs: dict[tuple[str, str], str] = {
        # Passing
        ("passing", "passingyards"): "pass_yards",
        ("passing", "passyards"): "pass_yards",
        ("passing", "passingtouchdowns"): "pass_td",
        ("passing", "interceptions"): "pass_int",
        ("passing", "passinginterceptions"): "pass_int",
        ("passing", "passingattempts"): "pass_attempts",
        ("passing", "completions"): "pass_completions",
        ("passing", "completionpct"): "completion_pct",
        ("passing", "completionpercentage"): "completion_pct",
        ("passing", "qbrating"): "passer_rating",
        ("passing", "passerrating"): "passer_rating",
        ("passing", "qbr"): "qbr",
        ("passing", "yardsperpassattempt"): "pass_yards_per_attempt",
        ("passing", "longpass"): "pass_long",
        ("passing", "longpassing"): "pass_long",
        ("passing", "sacks"): "pass_sacks",
        ("passing", "sackstaken"): "pass_sacks",
        ("passing", "sacked"): "pass_sacks",
        ("passing", "sackyardslost"): "pass_sacks",
        ("passing", "gamesplayed"): "games_played_season",
        ("passing", "gamesstarted"): "games_started",
        # Rushing
        ("rushing", "rushingyards"): "rush_yards",
        ("rushing", "rushyards"): "rush_yards",
        ("rushing", "rushingattempts"): "rush_attempts",
        ("rushing", "rushingtouchdowns"): "rush_td",
        ("rushing", "yardsperrushattempt"): "yards_per_carry",
        ("rushing", "longrushing"): "rush_long",
        ("rushing", "longrush"): "rush_long",
        ("rushing", "gamesplayed"): "games_played_season",
        # Receiving
        ("receiving", "receivingyards"): "rec_yards",
        ("receiving", "recyards"): "rec_yards",
        ("receiving", "receptions"): "receptions",
        ("receiving", "receivingtouchdowns"): "rec_td",
        ("receiving", "receivingtargets"): "rec_targets",
        ("receiving", "yardsperreception"): "yards_per_catch",
        ("receiving", "gamesplayed"): "games_played_season",
        # Defensive
        ("defensive", "totaltackles"): "tackles",
        ("defensive", "tackles"): "tackles",
        ("defensive", "solotackles"): "solo_tackles",
        ("defensive", "assisttackles"): "assist_tackles",
        ("defensive", "sacks"): "sacks",
        ("defensive", "sacktotal"): "sacks",
        ("defensive", "totalsacks"): "sacks",
        ("defensive", "tacklesforloss"): "tfl",
        ("defensive", "tfl"): "tfl",
        ("defensive", "stuffs"): "stuffs",
        ("defensive", "runstuffs"): "stuffs",
        ("defensive", "qbhits"): "qb_hits",
        ("defensive", "hurries"): "qb_hurries",
        ("defensive", "interceptions"): "interceptions",
        ("defensive", "passesdefended"): "passes_defended",
        ("defensive", "forcedfumbles"): "forced_fumbles",
        ("defensive", "fumbles"): "fumbles",
        ("defensive", "gamesplayed"): "games_played_season",
        ("defensive", "gamesstarted"): "games_started",
        ("defense", "sacks"): "sacks",
        ("defense", "tacklesforloss"): "tfl",
        ("defense", "interceptions"): "interceptions",
        ("defense", "totaltackles"): "tackles",
        ("defensiveinterceptions", "interceptions"): "interceptions",
        ("defensiveinterceptions", "passesdefended"): "passes_defended",
        # General / misc counting
        ("general", "gamesplayed"): "games_played_season",
        ("general", "gamesstarted"): "games_started",
        ("general", "fumbles"): "fumbles",
        ("miscellaneous", "fumbles"): "fumbles",
        # Kicking / punting
        ("kicking", "fieldgoalpct"): "fg_pct",
        ("kicking", "fieldgoalsmade"): "fg_made",
        ("kicking", "fieldgoalattempts"): "fg_attempts",
        ("kicking", "extrapointpct"): "xp_pct",
        ("kicking", "extrapointattempts"): "xp_attempts",
        ("kicking", "longfieldgoal"): "long_fg",
        ("punting", "grossavgpuntyards"): "punt_avg",
        ("punting", "puntyards"): "punt_yards",
        ("punting", "punts"): "punt_attempts",
    }
    basketball_pairs: dict[tuple[str, str], str] = {
        ("offensive", "points"): "pts",
        ("offensive", "assists"): "ast",
        ("offensive", "turnovers"): "to",
        ("defensive", "steals"): "stl",
        ("defensive", "blocks"): "blk",
        ("defensive", "defensiverebounds"): "dreb",
        ("general", "gamesplayed"): "games_played_season",
        ("general", "gamesstarted"): "games_started",
        ("general", "minutes"): "min",
        ("general", "points"): "pts",
        ("general", "assists"): "ast",
        ("general", "rebounds"): "reb",
        ("general", "totalrebounds"): "reb",
        ("general", "offensiverebounds"): "oreb",
        ("general", "defensiverebounds"): "dreb",
        ("general", "steals"): "stl",
        ("general", "blocks"): "blk",
        ("general", "turnovers"): "to",
        ("general", "fouls"): "pf",
        ("general", "personalfouls"): "pf",
        ("offensive", "fieldgoalsmade"): "fgm",
        ("offensive", "fieldgoalsattempted"): "fga",
        ("offensive", "fieldgoalpct"): "fg_pct",
        ("offensive", "threepointfieldgoalsmade"): "fg3m",
        ("offensive", "threepointfieldgoalsattempted"): "fg3a",
        ("offensive", "threepointfieldgoalpct"): "three_pct",
        ("offensive", "freethrowsmade"): "ftm",
        ("offensive", "freethrowsattempted"): "fta",
        ("offensive", "freethrowpct"): "ft_pct",
        ("offensive", "offensiverebounds"): "oreb",
        ("scoring", "points"): "pts",
        ("scoring", "fieldgoalsmade"): "fgm",
        ("scoring", "fieldgoalsattempted"): "fga",
        ("scoring", "threepointfieldgoalsmade"): "fg3m",
        ("scoring", "freethrowsmade"): "ftm",
    }
    # Baseball / volleyball: category names vary; pairs cover common ESPN labels.
    baseball_pairs: dict[tuple[str, str], str] = {
        ("pitching", "earnedrunavg"): "era",
        ("pitching", "era"): "era",
        ("pitching", "whip"): "whip",
        ("pitching", "innings"): "ip",
        ("pitching", "inningspitched"): "ip",
        ("pitching", "wins"): "wins",
        ("pitching", "losses"): "l",
        ("pitching", "saves"): "saves",
        ("pitching", "strikeouts"): "so",
        ("pitching", "walks"): "bb",
        ("pitching", "hits"): "h_allowed",
        ("pitching", "earnedruns"): "er",
        ("pitching", "gamesplayed"): "games_played_season",
        ("batting", "avg"): "avg",
        ("batting", "battingaverage"): "avg",
        ("batting", "homeruns"): "hr",
        ("batting", "rbis"): "rbi",
        ("batting", "runs"): "r",
        ("batting", "hits"): "h",
        ("batting", "atbats"): "ab",
        ("batting", "stolenbases"): "sb",
        ("batting", "obp"): "obp",
        ("batting", "slg"): "slg",
        ("batting", "ops"): "ops",
        ("batting", "gamesplayed"): "games_played_season",
        ("general", "gamesplayed"): "games_played_season",
        ("general", "gamesstarted"): "gs",
    }
    volleyball_pairs: dict[tuple[str, str], str] = {
        ("attacking", "kills"): "kills",
        ("attacking", "attackerrors"): "errors",
        ("attacking", "attackattempts"): "total_attacks",
        ("attacking", "hittingpct"): "hitting_pct",
        ("setting", "assists"): "assists",
        ("serving", "serviceaces"): "aces",
        ("serving", "serviceerrors"): "service_errors",
        ("blocking", "blocks"): "blocks",
        ("digging", "digs"): "digs",
        ("general", "gamesplayed"): "games_played_season",
        ("general", "sets"): "sets_played",
        ("general", "points"): "points",
    }
    return {
        "cfb": football_pairs,
        "nfl": football_pairs,
        "ncaab_mens": basketball_pairs,
        "ncaab_womens": basketball_pairs,
        "nba": basketball_pairs,
        "wnba": basketball_pairs,
        "ncaa_baseball": baseball_pairs,
        "ncaa_volleyball": volleyball_pairs,
    }


def _normalize_key(text: str) -> str:
    # Preserve percent so CMP% ≠ CMP after stripping punctuation.
    lowered = text.lower().replace("%", "pct")
    return re.sub(r"[^a-z0-9]+", "", lowered)


# Intentional dual canonicals (same ESPN label written to both keys).
_ALIAS_SYNONYM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"gp", "games_played_season"}),
    frozenset({"gs", "games_started"}),
)


def _canonicals_compatible(a: str, b: str) -> bool:
    if a == b:
        return True
    for group in _ALIAS_SYNONYM_GROUPS:
        if a in group and b in group:
            return True
    return False


def _build_reverse_lookup(sport: str) -> dict[str, str]:
    tables = _alias_table()
    sport_aliases = tables.get(sport, {})
    reverse: dict[str, str] = {}
    for canonical, aliases in sport_aliases.items():
        reverse[_normalize_key(canonical)] = canonical
        for alias in aliases:
            reverse[_normalize_key(alias)] = canonical
    return reverse


def category_pair_aliases(sport: str) -> dict[tuple[str, str], str]:
    """Public accessor: ``(category, stat)`` → canonical for ``sport``."""
    return dict(_category_pair_table().get(sport, {}))


def aliases_unique_within_category_scope(sport: str) -> None:
    """Raise ``AssertionError`` if any alias maps to two canonicals in one category.

    Flat aliases are one scope (synonym pairs like gp/games_played_season allowed).
    Category-pair aliases are checked per category.
    """
    # Flat table: each normalized alias → at most one canonical family.
    flat = _alias_table().get(sport, {})
    seen: dict[str, str] = {}
    for canonical, aliases in flat.items():
        for alias in (canonical, *aliases):
            key = _normalize_key(alias)
            if key in seen and not _canonicals_compatible(seen[key], canonical):
                raise AssertionError(
                    f"{sport}: flat alias {alias!r} maps to both "
                    f"{seen[key]!r} and {canonical!r}"
                )
            seen[key] = canonical

    # Forbidden ambiguous bare abbreviations (WP2 / B4) — must not appear as
    # aliases unless the alias *is* the canonical name (e.g. baseball ``avg``).
    banned_bare = frozenset({"avg", "int", "td", "yds", "long", "rating"})
    for canonical, aliases in flat.items():
        for alias in aliases:
            if str(alias).strip().lower() not in banned_bare:
                continue
            if _normalize_key(alias) == _normalize_key(canonical):
                continue
            raise AssertionError(
                f"{sport}: banned ambiguous bare alias {alias!r} "
                f"still maps to {canonical!r}"
            )

    # Category pairs: within one category, each stat name → one canonical.
    pairs = _category_pair_table().get(sport, {})
    by_cat: dict[str, dict[str, str]] = {}
    for (cat, stat), canonical in pairs.items():
        bucket = by_cat.setdefault(cat, {})
        if stat in bucket and bucket[stat] != canonical:
            raise AssertionError(
                f"{sport}: ({cat},{stat}) maps to both "
                f"{bucket[stat]!r} and {canonical!r}"
            )
        bucket[stat] = canonical


def _apply_defensive_tfl_fallback(out: dict[str, float]) -> dict[str, float]:
    """When ESPN zeros tacklesForLoss but stuffs+sacks exist, TFL ≈ sacks+stuffs."""
    tfl = out.get("tfl")
    sacks = out.get("sacks")
    stuffs = out.get("stuffs")
    has_tackle_signal = any(
        out.get(k) not in (None, 0.0) for k in ("tackles", "solo_tackles", "assist_tackles")
    )
    if (
        has_tackle_signal
        and (tfl is None or tfl == 0.0)
        and sacks is not None
        and stuffs is not None
    ):
        combined = float(sacks) + float(stuffs)
        if combined > 0:
            out["tfl"] = combined
    return out


def normalize_namespaced_stats(
    sport: str, namespaced: dict[str, float]
) -> dict[str, float]:
    """Map ``\"category.stat\"`` keys to canonical keys via (category, stat) pairs.

    Splits each key on the first ``.``. Literal zeros from ESPN are kept except:
    if ``pass_sacks`` is set and ``sacks`` would be ``0.0`` only (QB with empty
    defensive sacks), omit ``sacks``.
    """
    if not namespaced:
        return {}
    pairs = _category_pair_table().get(sport, {})
    out: dict[str, float] = {}
    for raw_key, raw_val in namespaced.items():
        key = str(raw_key)
        if "." not in key:
            continue
        category, stat = key.split(".", 1)
        pair = (_normalize_key(category), _normalize_key(stat))
        canonical = pairs.get(pair)
        if not canonical:
            continue
        val = parse_stat_value(raw_val)
        if val is None:
            continue
        if canonical not in out:
            out[canonical] = val
        elif out[canonical] == 0.0 and val != 0.0:
            out[canonical] = val
    # QB pack: defensive.sacks=0 must not invent a defensive sacks feature when
    # times-sacked (pass_sacks) is the real signal.
    if "pass_sacks" in out and out.get("sacks") == 0.0:
        out.pop("sacks", None)
    return _apply_defensive_tfl_fallback(out)


def normalize_espn_stats(sport: str, raw_stats: dict[str, Any]) -> dict[str, float]:
    """Map a flat ESPN stat dict to canonical numeric keys (legacy path).

    If keys are already namespaced (``category.stat``), delegates to
    ``normalize_namespaced_stats``.
    """
    if not raw_stats:
        return {}
    # Namespaced input → category-aware path.
    if any("." in str(k) for k in raw_stats):
        coerced: dict[str, float] = {}
        for k, v in raw_stats.items():
            if "." not in str(k):
                continue
            parsed = parse_stat_value(v)
            if parsed is not None:
                coerced[str(k)] = parsed
        if coerced:
            return normalize_namespaced_stats(sport, coerced)

    lookup = _build_reverse_lookup(sport)
    out: dict[str, float] = {}
    for raw_key, raw_val in raw_stats.items():
        norm = _normalize_key(str(raw_key))
        # Exact normalized-alias match ONLY. A previous substring fallback
        # (`alias_norm in norm or norm in alias_norm`) caused severe
        # miscategorization: short aliases like "td"/"tot"/"int"/"rating"
        # matched inside unrelated ESPN fields (passingFirstDowns→pass_td,
        # netTotalYards→tackles, interceptionPct→pass_int, ESPNQBRating→
        # passer_rating), assigning wildly wrong values. The alias tables
        # already include ESPN's camelCase names, so exact matching keeps the
        # real fields and simply drops unknown ones instead of corrupting.
        canonical = lookup.get(norm)
        if not canonical:
            continue
        val = parse_stat_value(raw_val)
        if val is None:
            continue
        if canonical not in out:
            out[canonical] = val
        elif out[canonical] == 0.0 and val != 0.0:
            # Prefer real defensive totals over a prior zero from another category.
            out[canonical] = val
    # Passing vs defensive INT disambiguation when ESPN uses generic "interceptions"
    if "interceptions" in out and "pass_yards" in out and "pass_int" not in out:
        out["pass_int"] = out.pop("interceptions")
    return _apply_defensive_tfl_fallback(out)


_SEASON_GP_CAPS = {
    "cfb": 17,
    "nfl": 17,
    "ncaab_mens": 45,
    "ncaab_womens": 45,
    "nba": 82,
    "wnba": 50,
}


def derive_career_from_history(
    history: dict[str, dict[str, float]] | None,
) -> dict[str, float]:
    """SUM per-season counting stats (career is derived, never scraped)."""
    if not history:
        return {}
    totals: dict[str, float] = {}
    for season_blob in history.values():
        if not isinstance(season_blob, dict):
            continue
        for key, val in season_blob.items():
            kl = str(key).lower()
            if kl.startswith("avg") or "pct" in kl or "rate" in kl:
                continue
            try:
                totals[key] = totals.get(key, 0.0) + float(val)
            except (TypeError, ValueError):
                continue
        gp = season_blob.get("games_played_season") or season_blob.get("gp")
        if gp is not None:
            try:
                totals["games_played_career"] = totals.get(
                    "games_played_career", 0.0
                ) + float(gp)
            except (TypeError, ValueError):
                pass
    return totals


def merge_stat_layers(
    sport: str,
    *,
    current: dict[str, Any] | None = None,
    history: dict[str, dict[str, Any]] | None = None,
    career: dict[str, Any] | None = None,
    stats_scope: str | None = None,
    stats_as_of: Any = None,
) -> dict[str, Any]:
    """Build raw_athlete_data stat fields with flat current-season scalars.

    ``career`` is ignored for season GP / season_stats. Career totals are derived
    from ``history`` when present.
    """
    fields: dict[str, Any] = {}
    normalized_current = normalize_espn_stats(sport, current or {})
    if normalized_current:
        fields["season_stats"] = normalized_current
        fields.update(normalized_current)
    if history:
        normalized_history: dict[str, dict[str, float]] = {}
        for season_key, stats in history.items():
            norm = normalize_espn_stats(sport, stats)
            if norm:
                normalized_history[str(season_key)] = norm
        if normalized_history:
            fields["season_stats_history"] = normalized_history

    # Career is derived from season history — never from scraped career aggregates.
    _ = career  # explicitly unused for season fields (spec: career never scraped)
    normalized_career = derive_career_from_history(fields.get("season_stats_history"))
    if normalized_career:
        fields["career_stats"] = normalized_career
        if normalized_career.get("games_played_career") is not None:
            fields["games_played_career"] = int(normalized_career["games_played_career"])

    gp = normalized_current.get("games_played_season") or normalized_current.get("gp")
    if gp is None:
        history_blob = fields.get("season_stats_history")
        if isinstance(history_blob, dict) and history_blob:
            latest = history_blob[sorted(history_blob.keys(), reverse=True)[0]]
            gp = latest.get("games_played_season") or latest.get("gp")
    if gp is None and normalized_current:
        stat_keys = all_stat_keys_for_sport(sport) - {"games_played_season", "gp"}
        if sum(1 for k in stat_keys if normalized_current.get(k) is not None) >= 1:
            gp = 1

    scope = stats_scope
    if not scope:
        from gravity_api.scrapers.parsers.espn_stats import infer_stats_scope

        scope = infer_stats_scope(
            history=fields.get("season_stats_history"),
            career=None,
            current=normalized_current,
            sport=sport,
        )
    # If current GP exceeds a single-season cap, treat it as career and clear season GP.
    cap = _SEASON_GP_CAPS.get((sport or "").lower())
    if gp is not None and cap is not None and float(gp) > cap:
        fields["games_played_career"] = int(gp)
        if scope == "season":
            scope = "career"
        # Prefer latest history season GP for games_played_season when available.
        history_blob = fields.get("season_stats_history")
        season_gp = None
        if isinstance(history_blob, dict) and history_blob:
            latest = history_blob[sorted(history_blob.keys(), reverse=True)[0]]
            season_gp = latest.get("games_played_season") or latest.get("gp")
        if season_gp is not None and float(season_gp) <= cap:
            gp = season_gp
            scope = "season"
        else:
            gp = None
            # Don't advertise career totals as season_stats GP.
            season = fields.get("season_stats")
            if isinstance(season, dict):
                season = dict(season)
                season.pop("games_played_season", None)
                season.pop("gp", None)
                fields["season_stats"] = season
            fields.pop("games_played_season", None)
            fields.pop("gp", None)

    if gp is not None:
        fields["games_played_season"] = int(gp)
    if scope:
        fields["stats_scope"] = scope
    if stats_as_of is not None and str(stats_as_of).strip():
        fields["stats_as_of"] = str(stats_as_of).strip()
    return finalize_stat_fields(sport, fields)


def finalize_stat_fields(sport: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Sync gp ↔ games_played_season and gs ↔ games_started at top level + season_stats."""
    if not fields:
        return fields

    season = fields.get("season_stats")
    season_out = dict(season) if isinstance(season, dict) else {}

    gp = (
        fields.get("games_played_season")
        or fields.get("gp")
        or season_out.get("games_played_season")
        or season_out.get("gp")
    )
    gs = (
        fields.get("games_started")
        or fields.get("gs")
        or season_out.get("games_started")
        or season_out.get("gs")
    )

    if gp is not None:
        gp_int = int(gp)
        fields["games_played_season"] = gp_int
        fields["gp"] = float(gp_int)
        season_out["games_played_season"] = float(gp_int)
        season_out["gp"] = float(gp_int)

    if gs is not None:
        gs_int = int(gs)
        fields["games_started"] = gs_int
        fields["gs"] = float(gs_int)
        season_out["games_started"] = float(gs_int)
        season_out["gs"] = float(gs_int)

    if season_out and (gp is not None or gs is not None or season):
        fields["season_stats"] = season_out

    return fields


# Legacy scrape payloads stored sport-prefixed counting stats (cfb_passing_yards)
# instead of canonical proof keys (pass_yards). Promote them so feature engineering
# and win-impact see the same fields as modern ESPN/Sports-Reference scrapes.
_LEGACY_PREFIXED_STAT_MAP: dict[str, dict[str, str]] = {
    "cfb": {
        "cfb_games_played": "games_played_season",
        "cfb_games_started": "games_started",
        "cfb_passing_yards": "pass_yards",
        "cfb_passing_tds": "pass_td",
        "cfb_passer_rating": "passer_rating",
        "cfb_pass_attempts": "pass_attempts",
        "cfb_pass_completions": "pass_completions",
        "cfb_completion_pct": "completion_pct",
        "cfb_interceptions": "pass_int",
        "cfb_rushing_yards": "rush_yards",
        "cfb_rushing_tds": "rush_td",
        "cfb_rush_attempts": "rush_attempts",
        "cfb_receiving_yards": "rec_yards",
        "cfb_receiving_tds": "rec_td",
        "cfb_receptions": "receptions",
        "cfb_tackles": "tackles",
        "cfb_sacks": "sacks",
        "cfb_ints_def": "interceptions",
        "cfb_passes_defended": "passes_defended",
        "cfb_forced_fumbles": "forced_fumbles",
        "cfb_tfl": "tfl",
    },
    "nfl": {
        "nfl_games_played": "games_played_season",
        "nfl_games_started": "games_started",
        "nfl_passing_yards": "pass_yards",
        "nfl_passing_tds": "pass_td",
        "nfl_passer_rating": "passer_rating",
        "nfl_interceptions": "pass_int",
        "nfl_rushing_yards": "rush_yards",
        "nfl_rushing_tds": "rush_td",
        "nfl_receiving_yards": "rec_yards",
        "nfl_receiving_tds": "rec_td",
        "nfl_receptions": "receptions",
        "nfl_tackles": "tackles",
        "nfl_sacks": "sacks",
        "nfl_ints_def": "interceptions",
        "nfl_passes_defended": "passes_defended",
    },
}


def promote_legacy_prefixed_stats(raw: dict[str, Any], sport: str) -> dict[str, Any]:
    """Copy sport-prefixed legacy stats onto canonical keys without clobbering."""
    mapping = _LEGACY_PREFIXED_STAT_MAP.get((sport or "").lower())
    if not mapping or not raw:
        return raw

    out = dict(raw)
    season = out.get("season_stats")
    season_out = dict(season) if isinstance(season, dict) else {}

    for legacy_key, canonical in mapping.items():
        if out.get(canonical) not in (None, ""):
            continue
        val = out.get(legacy_key)
        if val in (None, ""):
            val = season_out.get(legacy_key)
        parsed = parse_stat_value(val)
        if parsed is None:
            continue
        out[canonical] = parsed
        season_out.setdefault(canonical, parsed)

    if season_out:
        out["season_stats"] = season_out
    return finalize_stat_fields(sport, out)


def flatten_raw_for_stats(raw: dict[str, Any], sport: str) -> dict[str, float]:
    """Collect all numeric stats from top-level raw and nested season_stats."""
    promoted = promote_legacy_prefixed_stats(raw, sport)
    out: dict[str, float] = {}
    nested = promoted.get("season_stats")
    if isinstance(nested, dict):
        out.update(normalize_espn_stats(sport, nested))
    for key in all_stat_keys_for_sport(sport):
        val = promoted.get(key)
        if val is None and isinstance(nested, dict):
            val = nested.get(key)
        parsed = parse_stat_value(val)
        if parsed is not None:
            out[key] = parsed
    return out


__all__ = [
    "aliases_unique_within_category_scope",
    "category_pair_aliases",
    "finalize_stat_fields",
    "flatten_raw_for_stats",
    "merge_stat_layers",
    "normalize_espn_stats",
    "normalize_namespaced_stats",
    "parse_stat_value",
    "promote_legacy_prefixed_stats",
]
