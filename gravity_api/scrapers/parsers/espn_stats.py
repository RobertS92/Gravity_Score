"""Parse multi-season and career splits from ESPN stats API payloads."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from gravity_api.scrapers.types import SeasonStatLine

_SEASON_YEAR_RE = re.compile(r"(20\d{2})")
_LOG = logging.getLogger(__name__)


class ParseConflict(Exception):
    """Duplicate or conflicting stat identity within a single ESPN category."""


def _is_empty_stat(val: Any) -> bool:
    if val is None or val == "" or val == "-":
        return True
    try:
        return float(val) == 0.0
    except (TypeError, ValueError):
        return False


def _merge_stat_dicts(*parts: dict[str, Any]) -> dict[str, Any]:
    """Legacy merge for flat callers; first non-empty value wins, non-zero beats zero.

    Prefer ``parse_core_season_statistics`` + namespaced keys for new code paths.
    """
    out: dict[str, Any] = {}
    for part in parts:
        if not part:
            continue
        for key, val in part.items():
            if val is None or val == "" or val == "-":
                continue
            if key not in out:
                out[key] = val
                continue
            # Passing category often stamps sacks/INT=0 before defensive values land.
            if _is_empty_stat(out[key]) and not _is_empty_stat(val):
                out[key] = val
    return out


# Offensive categories reuse the key "sacks" for QB sacks taken — remap so they
# cannot clobber defensive sack totals during a flat merge (legacy path only).
_PASSING_SACK_KEYS = frozenset({"sacks", "SACK", "SACKS"})
_OFFENSIVE_CAT_NAMES = frozenset(
    {"passing", "rushing", "receiving", "scoring", "offensive", "kicking", "punting"}
)
_DEFENSIVE_CAT_NAMES = frozenset(
    {"defensive", "defense", "defensiveInterceptions", "miscellaneous"}
)


def _remap_category_keys(cat_name: str, stats: dict[str, Any]) -> dict[str, Any]:
    """Disambiguate category-local ESPN keys before a cross-category merge."""
    if not stats:
        return stats
    name = (cat_name or "").strip()
    name_l = name.lower()
    out = dict(stats)
    if name_l in _OFFENSIVE_CAT_NAMES or name_l.startswith("pass"):
        for key in list(out):
            if key in _PASSING_SACK_KEYS or str(key).lower() == "sacks":
                out.setdefault("sacksTaken", out.pop(key))
    return out


def _coerce_stat_float(val: Any) -> float | None:
    if val is None or val == "" or val == "-":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _namespaced_stats_from_categories(categories: list[Any]) -> dict[str, float]:
    """Keep category namespace: keys are ``\"category.stat\"``.

    Within one category, duplicate stat names log a ``ParseConflict`` and the
    duplicate is skipped (first value kept). Categories are never flattened
    by bare name across the payload.
    """
    out: dict[str, float] = {}
    for cat in categories:
        if not isinstance(cat, dict):
            continue
        cat_name = str(cat.get("name") or cat.get("displayName") or "").strip()
        if not cat_name:
            continue
        seen_in_cat: dict[str, float] = {}
        for stat in cat.get("stats") or []:
            if not isinstance(stat, dict):
                continue
            raw_key = (
                stat.get("name")
                or stat.get("abbreviation")
                or stat.get("shortDisplayName")
            )
            if not raw_key:
                continue
            key = str(raw_key)
            val = stat.get("value")
            if val is None:
                val = stat.get("displayValue")
            parsed = _coerce_stat_float(val)
            if parsed is None:
                continue
            if key in seen_in_cat:
                conflict = ParseConflict(
                    f"duplicate stat '{key}' in category '{cat_name}' "
                    f"(kept {seen_in_cat[key]}, skipped {parsed})"
                )
                _LOG.warning("%s", conflict)
                continue
            seen_in_cat[key] = parsed
        # Parallel labels/names + values shape (no object ``stats`` entries).
        if not seen_in_cat:
            labels = cat.get("labels") or cat.get("names")
            values = cat.get("stats") or cat.get("values")
            if labels and values and len(labels) == len(values):
                for name, val in zip(labels, values):
                    if not name:
                        continue
                    key = str(name)
                    raw = val.get("value") if isinstance(val, dict) else val
                    parsed = _coerce_stat_float(raw)
                    if parsed is None:
                        continue
                    if key in seen_in_cat:
                        conflict = ParseConflict(
                            f"duplicate stat '{key}' in category '{cat_name}' "
                            f"(kept {seen_in_cat[key]}, skipped {parsed})"
                        )
                        _LOG.warning("%s", conflict)
                        continue
                    seen_in_cat[key] = parsed
        for key, parsed in seen_in_cat.items():
            out[f"{cat_name}.{key}"] = parsed
    return out


def parse_core_season_statistics(
    payload: dict[str, Any],
    *,
    league: str,
    season_year: int,
    season_type: str,
    team_id: str,
    team_name: str | None,
    is_total: bool,
    source_url: str,
    stats_as_of: datetime,
    source_key: str = "espn.core.statistics",
) -> SeasonStatLine:
    """Parse a season-scoped core ``…/statistics`` payload into a ``SeasonStatLine``.

    Stats keep their ESPN category namespace (``defensive.sacks``, ``passing.sacks``).
    Call ``normalize_namespaced_stats`` to map to canonical keys.
    """
    if not payload:
        namespaced: dict[str, float] = {}
    else:
        splits = payload.get("splits") or {}
        categories = splits.get("categories") or payload.get("categories") or []
        if not isinstance(categories, list):
            categories = []
        namespaced = _namespaced_stats_from_categories(categories)
    if season_type not in {"regular", "postseason"}:
        raise ValueError(f"season_type must be 'regular' or 'postseason', got {season_type!r}")
    return SeasonStatLine(
        league=league,
        season_year=int(season_year),
        season_type=season_type,
        team_id=str(team_id),
        team_name=team_name,
        is_total=bool(is_total),
        stats=namespaced,
        source_key=source_key,
        source_url=source_url,
        stats_as_of=stats_as_of,
    )


def _stats_from_single_category(cat: dict[str, Any]) -> dict[str, Any]:
    """Stats from one ESPN category block (object stats or labels/names row)."""
    if not isinstance(cat, dict):
        return {}
    out: dict[str, Any] = {}
    for stat in cat.get("stats") or []:
        if not isinstance(stat, dict):
            continue
        key = stat.get("name") or stat.get("abbreviation") or stat.get("shortDisplayName")
        val = stat.get("value")
        if val is None:
            val = stat.get("displayValue")
        if key:
            out[str(key)] = val
    if out:
        return _remap_category_keys(
            str(cat.get("name") or cat.get("displayName") or ""), out
        )
    labels = cat.get("labels") or cat.get("names")
    values = cat.get("stats") or cat.get("values")
    if labels and values and len(labels) == len(values):
        row: dict[str, Any] = {}
        for name, val in zip(labels, values):
            if not name:
                continue
            row[str(name)] = val.get("value") if isinstance(val, dict) else val
        return _remap_category_keys(
            str(cat.get("name") or cat.get("displayName") or ""), row
        )
    return {}


def _stats_from_category_block(categories: list[Any]) -> dict[str, Any]:
    """Legacy flat merge: defensive preferred over offensive zeros after remap."""
    defensive: dict[str, Any] = {}
    other: dict[str, Any] = {}
    for cat in categories:
        if not isinstance(cat, dict):
            continue
        merged = _stats_from_single_category(cat)
        if not merged:
            continue
        name = str(cat.get("name") or cat.get("displayName") or "").lower()
        if name in _DEFENSIVE_CAT_NAMES or "defensive" in name or name == "defense":
            defensive = _merge_stat_dicts(defensive, merged)
        else:
            other = _merge_stat_dicts(other, merged)
    # Defensive values win on conflict (after remap, sacks should only be defensive).
    return _merge_stat_dicts(other, defensive)


def stats_from_espn_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Extract flat stats from a single-season ESPN stats payload."""
    if not data:
        return {}
    stats: dict[str, Any] = {}

    splits = data.get("splits") or {}
    categories = splits.get("categories") or data.get("categories") or []
    stats = _merge_stat_dicts(stats, _stats_from_category_block(
        categories if isinstance(categories, list) else []
    ))

    # Top-level statistics array (common on CFB site API)
    for block in data.get("statistics") or []:
        if not isinstance(block, dict):
            continue
        block_cats = block.get("splits") or block.get("categories") or []
        if isinstance(block_cats, dict):
            block_cats = block_cats.get("categories") or []
        stats = _merge_stat_dicts(
            stats,
            _stats_from_category_block(block_cats if isinstance(block_cats, list) else []),
        )

    # Tabular fallback: names + stat row at payload root
    names = data.get("names") or data.get("labels")
    values = data.get("stats") or data.get("values")
    if names and values and len(names) == len(values):
        row: dict[str, Any] = {}
        for name, val in zip(names, values):
            if name:
                row[str(name)] = val.get("value") if isinstance(val, dict) else val
        stats = _merge_stat_dicts(stats, row)

    if stats:
        return stats

    # Last resort: first category with stats in splits
    if isinstance(data.get("splits"), dict):
        for split in data["splits"].get("categories") or []:
            if isinstance(split, dict):
                partial = _stats_from_single_category(split)
                if partial:
                    return partial
    return stats


def _season_year_key(label: str) -> str:
    """Normalize a season label to a four-digit year key for history maps.

    Uses any ``YYYY`` (including pre-2000). Prefer ``season_calendar.parse_season_label``
    when the league is known.
    """
    m = re.search(r"(\d{4})", label or "")
    return m.group(1) if m else (label.strip() or "unknown")


def _categoried_rows(data: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Parse ESPN common/v3 athlete stats shape.

    Each ``categories[]`` block (passing, rushing, receiving, ...) carries a
    ``names`` header array plus:
      * ``statistics[]`` — one row per season, each with ``season.year`` and a
        ``stats`` array parallel to ``names`` (true per-season data), and
      * ``totals`` — a career row parallel to ``names``.

    Returns ``(history_by_year, career)`` with raw (un-normalized) stat names.
    """
    history: dict[str, dict[str, Any]] = {}
    career: dict[str, Any] = {}
    cats = data.get("categories")
    if not isinstance(cats, list):
        return history, career
    for cat in cats:
        if not isinstance(cat, dict):
            continue
        names = cat.get("names") or cat.get("labels")
        if not isinstance(names, list) or not names:
            continue
        for srow in cat.get("statistics") or []:
            if not isinstance(srow, dict):
                continue
            stats = srow.get("stats")
            if not isinstance(stats, list) or len(stats) != len(names):
                continue
            season = srow.get("season")
            year = season.get("year") or season.get("displayName") if isinstance(season, dict) else season
            if year is None:
                continue
            row = {str(names[i]): stats[i] for i in range(len(names))}
            cat_name = str(cat.get("name") or cat.get("displayName") or "")
            row = _remap_category_keys(cat_name, row)
            key = _season_year_key(str(year))
            history[key] = _merge_stat_dicts(history.get(key, {}), row)
        totals = cat.get("totals")
        if isinstance(totals, list) and len(totals) == len(names):
            trow = {str(names[i]): totals[i] for i in range(len(names))}
            trow = _remap_category_keys(
                str(cat.get("name") or cat.get("displayName") or ""), trow
            )
            career = _merge_stat_dicts(career, trow)
    return history, career


def extract_season_history(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return {season_year: stats_dict} from ESPN multi-split payloads."""
    history: dict[str, dict[str, Any]] = {}
    if not data:
        return history

    split_categories = data.get("splitCategories") or data.get("seasons") or []
    if isinstance(split_categories, list):
        for block in split_categories:
            if not isinstance(block, dict):
                continue
            label = (
                block.get("displayName")
                or block.get("shortDisplayName")
                or block.get("name")
                or block.get("label")
                or ""
            )
            season_key = _season_year_key(str(label))
            categories = block.get("splits") or block.get("categories") or []
            if isinstance(categories, dict):
                categories = categories.get("categories") or []
            stats = _stats_from_category_block(categories if isinstance(categories, list) else [])
            if not stats and block.get("stats"):
                stats = _stats_from_category_block([block])
            if stats:
                if season_key in history:
                    history[season_key] = _merge_stat_dicts(history[season_key], stats)
                else:
                    history[season_key] = stats

    # Some responses nest per-season under "seasonTypes"
    for st in data.get("seasonTypes") or []:
        if not isinstance(st, dict):
            continue
        for split in st.get("splits") or []:
            if not isinstance(split, dict):
                continue
            label = str(split.get("displayName") or split.get("name") or st.get("displayName") or "")
            season_key = _season_year_key(label)
            categories = split.get("categories") or split.get("stats") or []
            stats = _stats_from_category_block(categories if isinstance(categories, list) else [])
            if stats:
                if season_key in history:
                    history[season_key] = _merge_stat_dicts(history[season_key], stats)
                else:
                    history[season_key] = stats

    # ESPN common/v3 categories[].statistics[] per-season shape.
    cat_history, _ = _categoried_rows(data)
    for key, stats in cat_history.items():
        history[key] = _merge_stat_dicts(history.get(key, {}), stats)

    return history


def extract_career_totals(data: dict[str, Any]) -> dict[str, Any]:
    """Pull career / total row when ESPN exposes it."""
    if not data:
        return {}
    # ESPN common/v3 categories[].totals career row (most reliable when present).
    _, cat_career = _categoried_rows(data)
    if cat_career:
        return cat_career
    for block in data.get("splitCategories") or []:
        if not isinstance(block, dict):
            continue
        label = str(block.get("displayName") or block.get("name") or "").lower()
        if "career" not in label and "total" not in label and "cumulative" not in label:
            continue
        categories = block.get("splits") or block.get("categories") or []
        if isinstance(categories, dict):
            categories = categories.get("categories") or []
        stats = _stats_from_category_block(categories if isinstance(categories, list) else [])
        if stats:
            return stats
    totals = data.get("career") or data.get("totals")
    if isinstance(totals, dict):
        return stats_from_espn_payload(totals)
    return {}


def _latest_season_stats_from_history(history: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {}
    latest_key = sorted(history.keys(), reverse=True)[0]
    return dict(history.get(latest_key) or {})


def infer_stats_scope(
    *,
    history: dict[str, dict[str, Any]] | None,
    career: dict[str, Any] | None,
    current: dict[str, Any] | None,
    sport: str | None = None,
) -> str:
    """Classify whether current stats are season, career, or multi-season aggregates."""
    hist = history or {}
    years = [y for y in hist.keys() if _SEASON_YEAR_RE.search(str(y))]
    if len(years) >= 2:
        # Current should be latest season row when history is present.
        return "season"
    if len(years) == 1:
        return "season"
    cur = current or {}
    gp = None
    for key in ("gamesPlayed", "games_played_season", "GP", "G", "gp"):
        if cur.get(key) is not None:
            try:
                gp = float(cur[key])
                break
            except (TypeError, ValueError):
                pass
    sport_l = (sport or "").lower()
    season_cap = {
        "cfb": 17,
        "nfl": 17,
        "ncaab_mens": 45,
        "ncaab_womens": 45,
        "nba": 82,
        "wnba": 50,
    }.get(sport_l)
    if gp is not None and season_cap is not None and gp > season_cap:
        return "career" if career else "multi_season"
    if career and not years and gp is not None and season_cap and gp > season_cap:
        return "career"
    return "season"


_CAREER_ONLY_KEYS = frozenset(
    {"gamesPlayed", "gamesStarted", "GP", "G", "gp", "gs"}
)


def build_stats_bundle(
    data: dict[str, Any], *, sport: str | None = None
) -> dict[str, Any]:
    """Full stats bundle: current season + history.

    Career aggregates are **not** used as season fields. When ESPN only exposes a
    career/total row (no per-season history), ``current`` stays empty and
    ``stats_scope`` is left unset so callers do not stamp career GP into season
    columns. Career totals are derived downstream via SUM(season rows).
    """
    history = extract_season_history(data)
    # Still parse career for diagnostics / explicit career_stats blobs, but never
    # promote it into ``current`` season fields.
    career = extract_career_totals(data)
    latest = _latest_season_stats_from_history(history)
    flat = stats_from_espn_payload(data)

    def _payload_is_season_scoped(payload: dict[str, Any]) -> bool:
        """Core ``seasons/{year}/types/{n}/…/statistics`` responses are single-season."""
        if payload.get("seasonType"):
            return True
        if payload.get("displaySeason"):
            return True
        season = payload.get("season")
        if isinstance(season, dict) and (
            season.get("$ref") or season.get("year") or season.get("displayName")
        ):
            return True
        if isinstance(season, (str, int)) and str(season).strip():
            return True
        return False

    if latest:
        # Prefer true per-season rows; fill gaps from flat payload but never let
        # career-sized GP/GS from an aggregate flat payload overwrite season.
        current = dict(latest)
        for key, val in (flat or {}).items():
            if key in current and not _is_empty_stat(current.get(key)):
                continue
            if key in _CAREER_ONLY_KEYS:
                continue
            current[key] = val
    elif flat and _payload_is_season_scoped(data):
        current = dict(flat)
    else:
        # No per-season history and not a season-scoped core payload — do not
        # promote a career / multi-season aggregate into season fields.
        current = {}

    stats_as_of = data.get("season") or data.get("displaySeason")
    if isinstance(stats_as_of, dict):
        stats_as_of = (
            stats_as_of.get("year")
            or stats_as_of.get("displayName")
            or (
                str(stats_as_of.get("$ref", "")).split("/seasons/")[-1].split("?")[0]
                if stats_as_of.get("$ref")
                else None
            )
        )
    if history:
        latest_key = sorted(history.keys(), reverse=True)[0]
        if not stats_as_of:
            stats_as_of = latest_key

    scope = infer_stats_scope(
        history=history, career=None, current=current, sport=sport
    )
    if not history and not current:
        scope = None
    return {
        "current": current,
        "history": history,
        # Intentionally omitted from season path — derive via SUM(season rows).
        "career": {},
        "career_scraped_disabled": career or {},
        "stats_as_of": stats_as_of,
        "stats_scope": scope,
        "raw": data,
    }


__all__ = [
    "ParseConflict",
    "build_stats_bundle",
    "extract_career_totals",
    "extract_season_history",
    "infer_stats_scope",
    "parse_core_season_statistics",
    "stats_from_espn_payload",
]
