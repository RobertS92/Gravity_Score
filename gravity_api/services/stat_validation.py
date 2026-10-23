"""Second-source season validation (SCRAPER_FIX_SPEC §4.4 / WP6).

Completed season rows are compared against CFBD (cfb) or Sports-Reference
(other leagues) on ``games_played`` plus the sport's primary counting stats.
In-progress seasons are not required to have a second source.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Literal, Mapping

from gravity_api.feature_engineering.positions import derive_position_group
from gravity_api.scrapers.parsers.stat_normalizer import normalize_namespaced_stats
from gravity_api.scrapers.season_calendar import normalize_league, season_status
from gravity_api.scrapers.types import SeasonStatLine

logger = logging.getLogger(__name__)

ValidationStatus = Literal["matched", "mismatch", "no_second_source", "unvalidated"]

# Spec §4.4 primary stats. ``gp`` is the comparison key; aliases normalized below.
_BASKETBALL_PRIMARY: tuple[str, ...] = ("gp", "pts", "reb", "ast", "min")
_FOOTBALL_QB: tuple[str, ...] = (
    "gp",
    "pass_yards",
    "pass_td",
    "pass_int",
    "pass_attempts",
)
_FOOTBALL_SKILL: tuple[str, ...] = (
    "gp",
    "rush_yards",
    "rush_td",
    "receptions",
    "rec_yards",
)
_FOOTBALL_DEFENSE: tuple[str, ...] = (
    "gp",
    "tackles",
    "sacks",
    "tfl",
    "interceptions",
)

_BASKETBALL_LEAGUES = frozenset(
    {"nba", "wnba", "ncaab_mens", "ncaab_womens", "ncaab", "mcbb", "wcbb"}
)
_FOOTBALL_LEAGUES = frozenset({"nfl", "cfb", "ncaaf"})

# Zero tolerance on integer counts; ±0.1 on decimal counting stats (sacks, tfl).
_DECIMAL_PRIMARY = frozenset({"sacks", "tfl"})
_COUNT_TOLERANCE = 0.0
_DECIMAL_TOLERANCE = 0.1

# Synonyms folded into the primary comparison key.
_STAT_ALIASES: dict[str, str] = {
    "games_played_season": "gp",
    "games_played": "gp",
    "g": "gp",
    "games": "gp",
    "mp": "min",
    "minutes": "min",
}


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validating one ``SeasonStatLine`` against a second source."""

    status: ValidationStatus
    details: dict[str, Any] = field(default_factory=dict)


def primary_stat_keys(
    league: str,
    position: str | None = None,
    *,
    line_stats: Mapping[str, float] | None = None,
) -> tuple[str, ...]:
    """Return the ordered primary keys for §4.4 comparison."""
    lg = normalize_league(league)
    if lg in _BASKETBALL_LEAGUES:
        return _BASKETBALL_PRIMARY
    if lg not in _FOOTBALL_LEAGUES:
        # Unknown league: still check GP when present.
        return ("gp",)

    group = derive_position_group(position, lg) if position else None
    if group is None and line_stats:
        group = _infer_football_group(line_stats)

    if group == "QB":
        return _FOOTBALL_QB
    if group in {"RB", "WR", "TE"}:
        return _FOOTBALL_SKILL
    if group in {"DL", "LB", "DB"}:
        return _FOOTBALL_DEFENSE
    # Fallback: prefer whichever package has signal in the line.
    if line_stats:
        inferred = _infer_football_group(line_stats)
        if inferred == "QB":
            return _FOOTBALL_QB
        if inferred in {"RB", "WR", "TE"}:
            return _FOOTBALL_SKILL
        if inferred == "DL":
            return _FOOTBALL_DEFENSE
    return _FOOTBALL_DEFENSE


def canonicalize_stat_dict(stats: Mapping[str, Any] | None) -> dict[str, float]:
    """Flatten aliases (``games_played_season`` → ``gp``) to comparable floats."""
    if not stats:
        return {}
    out: dict[str, float] = {}
    for raw_key, raw_val in stats.items():
        if raw_val is None:
            continue
        key = _STAT_ALIASES.get(str(raw_key).strip().lower(), str(raw_key).strip().lower())
        try:
            val = float(raw_val)
        except (TypeError, ValueError):
            continue
        # Prefer a non-zero / first-seen value; do not overwrite a real value with 0.
        if key not in out or (out[key] == 0.0 and val != 0.0):
            out[key] = val
    return out


def line_canonical_stats(line: SeasonStatLine) -> dict[str, float]:
    """Canonical flat stats from a ``SeasonStatLine`` (namespaced or flat)."""
    raw = dict(line.stats or {})
    if any("." in str(k) for k in raw):
        return canonicalize_stat_dict(normalize_namespaced_stats(line.league, raw))
    return canonicalize_stat_dict(raw)


def values_match(key: str, ours: float, theirs: float) -> bool:
    """Zero tolerance on counts; ±0.1 on decimal primary stats (sacks, tfl)."""
    tol = _DECIMAL_TOLERANCE if key in _DECIMAL_PRIMARY else _COUNT_TOLERANCE
    # Round to avoid binary float edge cases at exactly ±0.1 (e.g. 20.0 vs 20.1).
    return round(abs(float(ours) - float(theirs)), 9) <= tol


def validate_completed_season(
    line: SeasonStatLine,
    *,
    second_source_stats: dict[str, float] | None = None,
    position: str | None = None,
    on: date | None = None,
) -> ValidationResult:
    """Compare a season line to a second-source dict (CFBD / Sports-Reference).

    * In-progress / future seasons → ``unvalidated`` (no second source required).
    * Completed + ``second_source_stats is None`` (or empty) → ``no_second_source``.
    * Completed + second source → ``matched`` or ``mismatch`` with both values.

    Callers that can reach CFBD / Sports-Reference should populate
    ``second_source_stats`` via :func:`fetch_second_source_stats` (or inject
    fixture dicts in tests).
    """
    day = on or datetime.now(tz=timezone.utc).date()
    lg = normalize_league(line.league)
    status = season_status(lg, int(line.season_year), day)

    base_details: dict[str, Any] = {
        "league": lg,
        "season_year": int(line.season_year),
        "season_type": line.season_type,
        "team_id": line.team_id,
        "season_status": status,
        "source_key": line.source_key,
    }

    if status != "complete":
        return ValidationResult(
            status="unvalidated",
            details={
                **base_details,
                "reason": "in_progress_or_future",
                "note": "Second-source validation applies only to completed seasons.",
            },
        )

    ours = line_canonical_stats(line)
    keys = primary_stat_keys(lg, position, line_stats=ours)
    base_details["primary_keys"] = list(keys)
    base_details["ours"] = {k: ours.get(k) for k in keys}

    if not second_source_stats:
        return ValidationResult(
            status="no_second_source",
            details={
                **base_details,
                "theirs": None,
                "reason": "second_source_stats_missing",
            },
        )

    theirs = canonicalize_stat_dict(second_source_stats)
    if not theirs:
        return ValidationResult(
            status="no_second_source",
            details={
                **base_details,
                "theirs": {},
                "reason": "second_source_stats_empty",
            },
        )

    comparisons: dict[str, dict[str, Any]] = {}
    mismatches: list[str] = []
    missing_on_second: list[str] = []
    missing_on_ours: list[str] = []

    for key in keys:
        our_val = ours.get(key)
        their_val = theirs.get(key)
        entry: dict[str, Any] = {"ours": our_val, "theirs": their_val}
        if our_val is None and their_val is None:
            entry["result"] = "both_absent"
        elif our_val is None:
            entry["result"] = "missing_ours"
            missing_on_ours.append(key)
            # Second source has a value we lack — treat as mismatch (parser gap).
            mismatches.append(key)
        elif their_val is None:
            entry["result"] = "missing_second_source"
            missing_on_second.append(key)
            # Key absent from second source: do not fail the whole season on that
            # key alone (second source may omit optional fields). Track only.
        elif values_match(key, our_val, their_val):
            entry["result"] = "matched"
        else:
            entry["result"] = "mismatch"
            mismatches.append(key)
        comparisons[key] = entry

    details = {
        **base_details,
        "theirs": {k: theirs.get(k) for k in keys},
        "comparisons": comparisons,
        "mismatches": mismatches,
        "missing_on_second_source": missing_on_second,
        "missing_on_ours": missing_on_ours,
    }

    # Require at least one overlapping primary key to claim a match.
    overlapped = [
        k
        for k, c in comparisons.items()
        if c.get("ours") is not None and c.get("theirs") is not None
    ]
    if not overlapped:
        return ValidationResult(
            status="no_second_source",
            details={
                **details,
                "reason": "no_overlapping_primary_keys",
            },
        )

    if mismatches:
        return ValidationResult(status="mismatch", details=details)
    return ValidationResult(status="matched", details=details)


async def fetch_second_source_stats(
    line: SeasonStatLine,
    *,
    athlete_name: str,
    position: str | None = None,
    team: str | None = None,
    school: str | None = None,
) -> dict[str, float] | None:
    """Fetch second-source season stats: CFBD for cfb, Sports-Reference otherwise.

    Returns a flat canonical dict suitable for ``validate_completed_season``, or
    ``None`` when the source is unavailable / empty. Does not raise on network
    errors — callers should treat ``None`` as ``no_second_source``.
    """
    lg = normalize_league(line.league)
    try:
        if lg in {"cfb", "ncaaf"}:
            return await _fetch_cfbd_stats(
                line,
                athlete_name=athlete_name,
                team=team or line.team_name,
            )
        return await _fetch_sports_reference_stats(
            line,
            athlete_name=athlete_name,
            school=school or team or line.team_name,
        )
    except Exception as exc:  # noqa: BLE001 — network / quota soft-fail
        logger.warning(
            "second-source fetch failed league=%s year=%s name=%s: %s",
            lg,
            line.season_year,
            athlete_name,
            exc,
        )
        return None


async def _fetch_cfbd_stats(
    line: SeasonStatLine,
    *,
    athlete_name: str,
    team: str | None,
) -> dict[str, float] | None:
    from gravity_api.scrapers.clients.cfbd import CfbdClient, cfbd_is_rate_limited

    if cfbd_is_rate_limited():
        logger.info("CFBD rate-limited; skipping second-source fetch")
        return None

    client = CfbdClient()
    _player, current, history = await client.fetch_player_stats_bundle(
        name=athlete_name,
        team=team,
        year=int(line.season_year),
    )
    year_key = str(int(line.season_year))
    stats = history.get(year_key) or current or {}
    canonical = canonicalize_stat_dict(stats)
    return canonical or None


async def _fetch_sports_reference_stats(
    line: SeasonStatLine,
    *,
    athlete_name: str,
    school: str | None,
) -> dict[str, float] | None:
    from gravity_api.scrapers.parsers.sports_reference_stats import fetch_sports_ref_stats

    lg = normalize_league(line.league)
    bundled = await fetch_sports_ref_stats(lg, athlete_name, school)
    season = bundled.get("season_stats") if isinstance(bundled, dict) else None
    if not isinstance(season, dict) or not season:
        return None
    # SR HTML parser returns the latest table row (often current season). Callers
    # validating historical seasons should prefer injected fixture dicts when the
    # live page year does not match ``line.season_year``.
    return canonicalize_stat_dict(season) or None


def _infer_football_group(stats: Mapping[str, float]) -> str | None:
    """Heuristic position group from which primary package has signal."""
    pass_signal = sum(
        1
        for k in ("pass_yards", "pass_td", "pass_attempts", "pass_int")
        if (stats.get(k) or 0) != 0
    )
    skill_signal = sum(
        1
        for k in ("rush_yards", "rush_td", "receptions", "rec_yards")
        if (stats.get(k) or 0) != 0
    )
    def_signal = sum(
        1
        for k in ("tackles", "sacks", "tfl", "interceptions")
        if (stats.get(k) or 0) != 0
    )
    best = max(
        (("QB", pass_signal), ("RB", skill_signal), ("DL", def_signal)),
        key=lambda x: x[1],
    )
    return best[0] if best[1] > 0 else None


def collection_errors_from_validation(
    result: ValidationResult,
    *,
    athlete_name: str | None = None,
) -> list[str]:
    """Format §4.4 mismatch details for ``collection_errors`` / scraper_jobs.

    Mismatch rows are still stored; callers must append these strings so both
    values are retained for ops review. Never rewrite ESPN toward the second
    source.
    """
    if result.status != "mismatch":
        return []
    details = result.details or {}
    who = athlete_name or "athlete"
    league = details.get("league")
    year = details.get("season_year")
    prefix = f"validation_mismatch:{who}:{league}:{year}"
    errors: list[str] = []
    comparisons = details.get("comparisons") or {}
    for key in details.get("mismatches") or []:
        cmp = comparisons.get(key) or {}
        errors.append(
            f"{prefix}:{key}:ours={cmp.get('ours')}:theirs={cmp.get('theirs')}"
        )
    if not errors:
        errors.append(f"{prefix}:keys={details.get('mismatches')}")
    return errors


def log_validation_result(
    result: ValidationResult,
    *,
    athlete_name: str | None = None,
) -> list[str]:
    """Log mismatch / no_second_source outcomes; return ``collection_errors`` strings."""
    errors = collection_errors_from_validation(result, athlete_name=athlete_name)
    if result.status == "mismatch":
        for err in errors:
            logger.warning("%s", err)
    elif result.status == "no_second_source":
        logger.info(
            "validation no_second_source athlete=%s league=%s year=%s reason=%s",
            athlete_name,
            (result.details or {}).get("league"),
            (result.details or {}).get("season_year"),
            (result.details or {}).get("reason"),
        )
    return errors


def validate_career_counting_stat(
    *,
    ours_total: float,
    second_source_total: float,
    stat_key: str = "pass_yards",
    league: str,
    athlete_name: str | None = None,
) -> ValidationResult:
    """Zero-tolerance career cross-check (SUM of season TOT rows vs second source)."""
    details: dict[str, Any] = {
        "league": normalize_league(league),
        "stat_key": stat_key,
        "ours": {stat_key: float(ours_total)},
        "theirs": {stat_key: float(second_source_total)},
        "comparisons": {
            stat_key: {
                "ours": float(ours_total),
                "theirs": float(second_source_total),
                "result": (
                    "matched"
                    if values_match(stat_key, float(ours_total), float(second_source_total))
                    else "mismatch"
                ),
            }
        },
        "mismatches": [],
        "athlete_name": athlete_name,
        "scope": "career",
    }
    if values_match(stat_key, float(ours_total), float(second_source_total)):
        return ValidationResult(status="matched", details=details)
    details["mismatches"] = [stat_key]
    return ValidationResult(status="mismatch", details=details)


__all__ = [
    "ValidationResult",
    "ValidationStatus",
    "canonicalize_stat_dict",
    "collection_errors_from_validation",
    "fetch_second_source_stats",
    "line_canonical_stats",
    "log_validation_result",
    "primary_stat_keys",
    "validate_career_counting_stat",
    "validate_completed_season",
    "values_match",
]
