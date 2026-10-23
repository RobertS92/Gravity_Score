"""Point-in-time feature snapshot builder (SCORING_ML_FIX_SPEC §3 F1).

Every feature value must satisfy ``observed_at <= as_of``:
- season stats via ``athlete_season_stats.stats_as_of`` (fallback ``observed_at``)
- socials via ``social_snapshots.scraped_at``
- metrics via ``athlete_metric_history.period_start``

Rows with ``validation_status = 'mismatch'`` are excluded.
Returns ``feature_coverage`` per athlete (fraction observed vs imputed/missing).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Protocol, Sequence

import pandas as pd

from gravity_ml.features.manifest import allowed_features, assert_features_allowed

_SOCIAL_METRIC_MAP: dict[str, str] = {
    "instagram_followers": "instagram_followers",
    "tiktok_followers": "tiktok_followers",
    "twitter_followers": "twitter_followers",
    "youtube_subscribers": "youtube_subscribers",
    "trusted_social_reach": "trusted_social_reach",
    "news_count_30d": "news_count_30d",
    "google_trends_score": "google_trends_score",
}

_STAT_KEY_MAP: dict[str, str] = {
    "games_played": "games_played_season",
    "games_played_season": "games_played_season",
    "gp": "games_played_season",
    "games_started": "games_started",
    "points_per_game": "points_per_game",
    "ppg": "points_per_game",
    "rebounds_per_game": "rebounds_per_game",
    "assists_per_game": "assists_per_game",
    "minutes_per_game": "minutes_per_game",
    "recruiting_stars": "recruiting_stars",
    "data_quality_score": "data_quality_score",
}


class PitConnection(Protocol):
    """Minimal DB surface used by ``build_snapshot``."""

    def fetch(self, query: str, *args: Any) -> Sequence[Mapping[str, Any]]: ...


def _ensure_aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_aware(value)
    if isinstance(value, str):
        text = value.replace("Z", "+00:00")
        try:
            return _ensure_aware(datetime.fromisoformat(text))
        except ValueError:
            return None
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def assemble_snapshot(
    *,
    athlete_ids: Sequence[str],
    as_of: datetime,
    feature_set: str,
    season_rows: Sequence[Mapping[str, Any]] = (),
    social_rows: Sequence[Mapping[str, Any]] = (),
    metric_rows: Sequence[Mapping[str, Any]] = (),
) -> pd.DataFrame:
    """Pure merge of pre-fetched PIT rows into a feature frame."""
    feature_names = allowed_features(feature_set)
    assert_features_allowed(feature_names)
    as_of = _ensure_aware(as_of)
    id_list = [str(a) for a in athlete_ids]

    if not id_list:
        return pd.DataFrame(columns=["athlete_id", "as_of", "feature_coverage", *feature_names])

    by_athlete: dict[str, dict[str, Any]] = {
        aid: {"athlete_id": aid, "as_of": as_of, **{f: None for f in feature_names}}
        for aid in id_list
    }
    observed: dict[str, set[str]] = {aid: set() for aid in id_list}

    # Season stats: caller should pass newest-first; we keep first valid per feature.
    for row in season_rows:
        aid = str(row["athlete_id"])
        if aid not in by_athlete:
            continue
        if str(row.get("validation_status") or "").lower() == "mismatch":
            continue
        observed_at = _as_datetime(row.get("stats_as_of") or row.get("observed_at"))
        if observed_at is None or observed_at > as_of:
            continue
        feature = _STAT_KEY_MAP.get(str(row.get("stat_key") or ""))
        if feature is None or feature not in by_athlete[aid]:
            continue
        if feature in observed[aid]:
            continue
        by_athlete[aid][feature] = _to_float(row.get("stat_value"))
        observed[aid].add(feature)

    for row in social_rows:
        aid = str(row["athlete_id"])
        if aid not in by_athlete:
            continue
        scraped_at = _as_datetime(row.get("scraped_at"))
        if scraped_at is None or scraped_at > as_of:
            continue
        for src_key, feature in _SOCIAL_METRIC_MAP.items():
            if feature not in by_athlete[aid] or feature in observed[aid]:
                continue
            if src_key in row and row[src_key] is not None:
                by_athlete[aid][feature] = _to_float(row[src_key])
                observed[aid].add(feature)

    for row in metric_rows:
        aid = str(row["athlete_id"])
        if aid not in by_athlete:
            continue
        period_start = _as_datetime(row.get("period_start"))
        if period_start is None or period_start > as_of:
            continue
        key = str(row.get("metric_key") or "")
        feature = _SOCIAL_METRIC_MAP.get(key) or _STAT_KEY_MAP.get(key)
        if feature is None or feature not in by_athlete[aid] or feature in observed[aid]:
            continue
        by_athlete[aid][feature] = _to_float(row.get("numeric_value"))
        observed[aid].add(feature)

    n_features = max(len(feature_names), 1)
    frames = []
    for aid in id_list:
        row = by_athlete[aid]
        row["feature_coverage"] = round(len(observed[aid]) / n_features, 6)
        frames.append(row)

    df = pd.DataFrame(frames)
    return df[["athlete_id", "as_of", "feature_coverage", *feature_names]]


def build_snapshot(
    conn: PitConnection,
    athlete_ids: Sequence[str],
    as_of: datetime,
    feature_set: str,
) -> pd.DataFrame:
    """Build a point-in-time feature frame for ``athlete_ids`` at ``as_of``."""
    as_of = _ensure_aware(as_of)
    id_list = [str(a) for a in athlete_ids]
    season_rows = _fetch_season_stats(conn, id_list, as_of)
    social_rows = _fetch_social_snapshots(conn, id_list, as_of)
    metric_rows = _fetch_metric_history(conn, id_list, as_of)
    return assemble_snapshot(
        athlete_ids=id_list,
        as_of=as_of,
        feature_set=feature_set,
        season_rows=season_rows,
        social_rows=social_rows,
        metric_rows=metric_rows,
    )


_SEASON_STATS_SQL = """
SELECT athlete_id::text AS athlete_id,
       stat_key,
       stat_value,
       COALESCE(stats_as_of, observed_at) AS stats_as_of,
       observed_at,
       validation_status
FROM athlete_season_stats
WHERE athlete_id = ANY($1::uuid[])
  AND COALESCE(stats_as_of, observed_at) <= $2
  AND COALESCE(validation_status, 'unvalidated') <> 'mismatch'
  AND COALESCE(team_id, 'TOT') = 'TOT'
  AND COALESCE(season_type, 'regular') = 'regular'
ORDER BY COALESCE(stats_as_of, observed_at) DESC
"""

_SEASON_STATS_SQL_LEGACY = """
SELECT athlete_id::text AS athlete_id,
       stat_key,
       stat_value,
       observed_at AS stats_as_of,
       observed_at,
       NULL::text AS validation_status
FROM athlete_season_stats
WHERE athlete_id = ANY($1::uuid[])
  AND observed_at <= $2
ORDER BY observed_at DESC
"""

_SOCIAL_SQL = """
SELECT athlete_id::text AS athlete_id,
       scraped_at,
       instagram_followers,
       tiktok_followers,
       twitter_followers,
       youtube_subscribers
FROM social_snapshots
WHERE athlete_id = ANY($1::uuid[])
  AND scraped_at <= $2
ORDER BY scraped_at DESC
"""

_METRIC_SQL = """
SELECT athlete_id::text AS athlete_id,
       metric_key,
       numeric_value,
       period_start,
       observed_at
FROM athlete_metric_history
WHERE athlete_id = ANY($1::uuid[])
  AND period_start <= $2
ORDER BY period_start DESC
"""


def _fetch_season_stats(
    conn: PitConnection,
    athlete_ids: Sequence[str],
    as_of: datetime,
) -> Sequence[Mapping[str, Any]]:
    try:
        return conn.fetch(_SEASON_STATS_SQL, list(athlete_ids), as_of)
    except Exception:
        return conn.fetch(_SEASON_STATS_SQL_LEGACY, list(athlete_ids), as_of)


def _fetch_social_snapshots(
    conn: PitConnection,
    athlete_ids: Sequence[str],
    as_of: datetime,
) -> Sequence[Mapping[str, Any]]:
    try:
        return conn.fetch(_SOCIAL_SQL, list(athlete_ids), as_of)
    except Exception:
        return []


def _fetch_metric_history(
    conn: PitConnection,
    athlete_ids: Sequence[str],
    as_of: datetime,
) -> Sequence[Mapping[str, Any]]:
    try:
        return conn.fetch(_METRIC_SQL, list(athlete_ids), as_of)
    except Exception:
        return []
