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


def _alias_table() -> dict[str, dict[str, tuple[str, ...]]]:
    """ESPN label/abbreviation aliases → canonical key, grouped by sport family."""
    football = {
        "pass_yards": (
            "passingYards",
            "passYards",
            "pass_yards",
            "YDS",
            "Pass Yds",
            "Passing Yards",
            "pass yds",
        ),
        "pass_td": ("passingTouchdowns", "passTD", "TD", "Pass TD", "pass td"),
        "pass_int": ("interceptions", "INT", "passINT", "Pass INT", "pass int"),
        "pass_attempts": ("passingAttempts", "ATT", "passAtt", "Pass Att"),
        "pass_completions": ("completions", "CMP", "passCmp", "Pass Cmp"),
        "completion_pct": ("completionPct", "CMP%", "Comp %", "completionPercentage"),
        # ESPN exposes the standard 0-158.3 passer rating as "QBRating"; "ESPNQBRating"
        # is a different cumulative points metric (can be 50k+) and must NOT be used.
        "passer_rating": ("QBRating", "passerRating", "RTG", "Rating", "pass rating"),
        "qbr": ("QBR", "qbr", "adjQBR"),
        "pass_yards_per_attempt": ("yardsPerPassAttempt", "YPA", "Avg"),
        "pass_long": ("longPass", "longPassing", "Long"),
        "pass_sacks": ("sacks", "SACKS", "sacked"),
        "rush_yards": ("rushingYards", "rushYards", "RUSH YDS", "Rush Yds"),
        "rush_attempts": ("rushingAttempts", "CAR", "rushAtt", "Rush Att"),
        "rush_td": ("rushingTouchdowns", "rushTD", "Rush TD"),
        "yards_per_carry": ("yardsPerRushAttempt", "YPC", "Avg", "rush avg"),
        "rush_long": ("longRushing", "longRush"),
        "rec_yards": ("receivingYards", "recYards", "REC YDS", "Rec Yds"),
        "receptions": ("receptions", "REC", "rec"),
        "rec_td": ("receivingTouchdowns", "recTD", "Rec TD"),
        "rec_targets": ("receivingTargets", "TGTS", "Targets"),
        "yards_per_catch": ("yardsPerReception", "Y/R", "Avg"),
        "scrimmage_yards": ("scrimmageYards", "SCRIM YDS", "Scrimmage Yds"),
        "fumbles": ("fumbles", "FUM", "fumblesLost"),
        "tackles": ("totalTackles", "TOT", "tackles", "Tackles"),
        "solo_tackles": ("soloTackles", "SOLO"),
        "assist_tackles": ("assistTackles", "AST"),
        "sacks": ("sacks", "SACK", "sacks"),
        "tfl": ("tacklesForLoss", "TFL", "tfl"),
        "qb_hits": ("qbHits", "QBH"),
        "qb_hurries": ("hurries", "HUR"),
        "interceptions": ("interceptions", "INT", "int"),
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
        "triple_doubles": ("tripleDouble", "tripleDoubles", "TD"),
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


def _normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _build_reverse_lookup(sport: str) -> dict[str, str]:
    tables = _alias_table()
    sport_aliases = tables.get(sport, {})
    reverse: dict[str, str] = {}
    for canonical, aliases in sport_aliases.items():
        reverse[_normalize_key(canonical)] = canonical
        for alias in aliases:
            reverse[_normalize_key(alias)] = canonical
    return reverse


def normalize_espn_stats(sport: str, raw_stats: dict[str, Any]) -> dict[str, float]:
    """Map a flat ESPN stat dict to canonical numeric keys."""
    if not raw_stats:
        return {}
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
    # Passing vs defensive INT disambiguation when ESPN uses generic "interceptions"
    if "interceptions" in out and "pass_yards" in out and "pass_int" not in out:
        out["pass_int"] = out.pop("interceptions")
    return out


def merge_stat_layers(
    sport: str,
    *,
    current: dict[str, Any] | None = None,
    history: dict[str, dict[str, Any]] | None = None,
    career: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build raw_athlete_data stat fields with flat current-season scalars."""
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
    if career:
        normalized_career = normalize_espn_stats(sport, career)
        if normalized_career:
            fields["career_stats"] = normalized_career
            if normalized_career.get("games_played_season") is not None:
                fields["games_played_career"] = normalized_career["games_played_season"]
            elif normalized_career.get("gp") is not None:
                fields["games_played_career"] = normalized_career["gp"]
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
    if gp is not None:
        fields["games_played_season"] = int(gp)
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
    "finalize_stat_fields",
    "flatten_raw_for_stats",
    "merge_stat_layers",
    "normalize_espn_stats",
    "parse_stat_value",
    "promote_legacy_prefixed_stats",
]
