"""Shared athlete signal enrichment.

Merges scraped ``raw_athlete_data`` and ``social_snapshots`` onto an athlete
dict so the profile endpoint, the CSC report builder, and any other consumer
see the *same* social / news / search signals.

Historically each consumer re-implemented this merge, which is why the CSC
report surfaced ``N/A`` for fields the profile endpoint resolved correctly
(followers, engagement, news, search interest, etc.). This module is the single
source of truth for that merge.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional, Sequence


def parse_raw_data(raw_data: Any) -> dict[str, Any]:
    """Coerce a ``raw_athlete_data.raw_data`` cell into a plain dict.

    Accepts the asyncpg-decoded ``dict``, a JSON ``str``, or anything
    dict-coercible. Returns ``{}`` for empty / unparseable input.
    """
    if not raw_data:
        return {}
    if isinstance(raw_data, str):
        try:
            parsed = json.loads(raw_data)
        except (ValueError, TypeError):
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    if isinstance(raw_data, Mapping):
        return dict(raw_data)
    try:
        return dict(raw_data)
    except (TypeError, ValueError):
        return {}


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def social_signal_fields(
    raw_signals: Mapping[str, Any],
    snap: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Return the canonical social/exposure signal fields for an athlete.

    ``raw_signals`` is the latest ``raw_athlete_data.raw_data`` dict;
    ``snap`` (optional) is the latest ``social_snapshots`` row used to backfill
    follower / engagement / news fields when the raw scrape is missing them.

    Only real, scraped values are returned — this function never fabricates
    follower counts (that is the scoring imputation layer's job, and those
    imputed values are deliberately kept out of report-facing surfaces).
    """
    raw_signals = raw_signals or {}
    snap = snap or {}

    def pick(*keys: str) -> Any:
        for source in (raw_signals, snap):
            for key in keys:
                val = source.get(key)
                if val is not None and val != "":
                    return val
        return None

    ig = pick("instagram_followers")
    tw = pick("twitter_followers")
    tt = pick("tiktok_followers")
    reach_parts = [v for v in (_to_float(ig), _to_float(tw), _to_float(tt)) if v]
    social_reach = sum(reach_parts) if reach_parts else None

    return {
        "instagram_followers": ig,
        "twitter_followers": tw,
        "tiktok_followers": tt,
        "social_combined_reach": social_reach,
        "instagram_engagement_rate": pick("instagram_engagement_rate"),
        "news_mentions_30d": pick("news_mentions_30d", "news_count_30d"),
        "wikipedia_page_views_30d": pick("wikipedia_page_views_30d"),
        "google_trends_score": pick("google_trends_score"),
        "nil_valuation_raw": pick("nil_valuation"),
        "on3_nil_rank": pick("nil_ranking"),
    }


def enrich_athlete_dict(
    athlete_d: dict[str, Any],
    *,
    raw_signals: Optional[Mapping[str, Any]] = None,
    snap: Optional[Mapping[str, Any]] = None,
    conference: Optional[str] = None,
    verified_deals_count: Optional[int] = None,
    gravity_delta_30d: Optional[float] = None,
    nil_valuation_delta_30d: Optional[float] = None,
) -> dict[str, Any]:
    """Merge scraped signals onto ``athlete_d`` in place and return it.

    A resolved ``conference`` (e.g. from ``team_conferences``) overrides the
    stored athlete-row conference so downstream "Market Proof" signals never
    show ``N/A`` when the report header already resolved a conference.

    Existing non-null athlete values are never clobbered with ``None`` — the
    scrape only *fills gaps*.
    """
    fields = social_signal_fields(raw_signals or {}, snap)
    for key, value in fields.items():
        if value is not None:
            athlete_d[key] = value
        else:
            athlete_d.setdefault(key, None)

    if conference:
        athlete_d["conference"] = conference

    if verified_deals_count is not None:
        athlete_d["verified_deals_count"] = int(verified_deals_count)
    else:
        athlete_d.setdefault("verified_deals_count", None)

    if gravity_delta_30d is not None:
        athlete_d["gravity_delta_30d"] = gravity_delta_30d
    else:
        athlete_d.setdefault("gravity_delta_30d", None)

    if nil_valuation_delta_30d is not None:
        athlete_d["nil_valuation_delta_30d"] = nil_valuation_delta_30d
    else:
        athlete_d.setdefault("nil_valuation_delta_30d", None)

    return athlete_d


def score_delta_30d(scores: Sequence[Mapping[str, Any]]) -> Optional[float]:
    """Gravity-score change vs. the score closest to 30 days before the latest.

    ``scores`` must be ordered newest-first (as returned by the score-history
    queries). Returns ``None`` when there is insufficient history.
    """
    return _series_delta_30d(
        [
            (row.get("calculated_at"), row.get("gravity_score"))
            for row in scores
        ],
        round_to=1,
    )


def value_delta_30d(series: Sequence[tuple[Any, Any]]) -> Optional[float]:
    """Generic 30-day delta for a ``(timestamp, value)`` series (newest-first)."""
    return _series_delta_30d(series, round_to=2)


def _coerce_ts(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _series_delta_30d(
    series: Sequence[tuple[Any, Any]],
    *,
    round_to: int,
) -> Optional[float]:
    points: list[tuple[datetime, float]] = []
    for ts, val in series:
        ts_dt = _coerce_ts(ts)
        num = _to_float(val)
        if ts_dt is not None and num is not None:
            points.append((ts_dt, num))
    if len(points) < 2:
        return None
    points.sort(key=lambda p: p[0], reverse=True)
    latest_ts, latest_val = points[0]
    target = latest_ts - timedelta(days=30)
    best_val: Optional[float] = None
    best_diff: Optional[float] = None
    for ts_dt, num in points[1:]:
        diff = abs((ts_dt - target).total_seconds())
        if best_diff is None or diff < best_diff:
            best_val = num
            best_diff = diff
    if best_val is None:
        return None
    return round(latest_val - best_val, round_to)
