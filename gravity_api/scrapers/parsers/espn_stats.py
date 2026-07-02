"""Parse multi-season and career splits from ESPN stats API payloads."""

from __future__ import annotations

import re
from typing import Any

_SEASON_YEAR_RE = re.compile(r"(20\d{2})")


def _merge_stat_dicts(*parts: dict[str, Any]) -> dict[str, Any]:
    """Merge ESPN stat dicts; first non-empty value wins per key."""
    out: dict[str, Any] = {}
    for part in parts:
        if not part:
            continue
        for key, val in part.items():
            if val is None or val == "" or val == "-":
                continue
            if key not in out:
                out[key] = val
    return out


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
        return out
    labels = cat.get("labels") or cat.get("names")
    values = cat.get("stats") or cat.get("values")
    if labels and values and len(labels) == len(values):
        row: dict[str, Any] = {}
        for name, val in zip(labels, values):
            if not name:
                continue
            row[str(name)] = val.get("value") if isinstance(val, dict) else val
        return row
    return {}


def _stats_from_category_block(categories: list[Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for cat in categories:
        if not isinstance(cat, dict):
            continue
        merged = _stats_from_single_category(cat)
        out = _merge_stat_dicts(out, merged)
    return out


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


def _season_label_to_key(label: str) -> str:
    m = _SEASON_YEAR_RE.search(label or "")
    return m.group(1) if m else label.strip() or "unknown"


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
            season_key = _season_label_to_key(str(label))
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
            season_key = _season_label_to_key(label)
            categories = split.get("categories") or split.get("stats") or []
            stats = _stats_from_category_block(categories if isinstance(categories, list) else [])
            if stats:
                if season_key in history:
                    history[season_key] = _merge_stat_dicts(history[season_key], stats)
                else:
                    history[season_key] = stats

    return history


def extract_career_totals(data: dict[str, Any]) -> dict[str, Any]:
    """Pull career / total row when ESPN exposes it."""
    if not data:
        return {}
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


def build_stats_bundle(data: dict[str, Any]) -> dict[str, Any]:
    """Full stats bundle: current season, history, career."""
    history = extract_season_history(data)
    current = _merge_stat_dicts(
        stats_from_espn_payload(data),
        _latest_season_stats_from_history(history),
    )
    career = extract_career_totals(data)

    # CFB: merge all category blocks from latest splitCategories season
    if history:
        latest_key = sorted(history.keys(), reverse=True)[0]
        latest = history.get(latest_key) or {}
        current = _merge_stat_dicts(current, latest)

    return {
        "current": current,
        "history": history,
        "career": career,
        "stats_as_of": data.get("season") or data.get("displaySeason"),
        "raw": data,
    }


__all__ = [
    "build_stats_bundle",
    "extract_career_totals",
    "extract_season_history",
    "stats_from_espn_payload",
]
