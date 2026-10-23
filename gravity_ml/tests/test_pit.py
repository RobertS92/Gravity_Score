"""F1 — point-in-time snapshot builder."""

from __future__ import annotations

from datetime import datetime, timezone

from gravity_ml.data.pit import assemble_snapshot, build_snapshot


class _FakeConn:
    """Routes by table name substring in the SQL."""

    def __init__(self, tables: dict[str, list[dict]]):
        self.tables = tables

    def fetch(self, query: str, *_args):
        q = query.lower()
        if "athlete_season_stats" in q:
            if "validation_status" in q and "team_id" in q:
                return list(self.tables.get("season", []))
            # Legacy path — still return season rows.
            return list(self.tables.get("season", []))
        if "social_snapshots" in q:
            return list(self.tables.get("social", []))
        if "athlete_metric_history" in q:
            return list(self.tables.get("metric", []))
        raise RuntimeError(f"unexpected query: {query[:80]}")


def test_pit_excludes_future_stats_and_mismatch():
    as_of = datetime(2025, 12, 1, tzinfo=timezone.utc)
    athlete = "11111111-1111-1111-1111-111111111111"
    season = [
        {
            "athlete_id": athlete,
            "stat_key": "points_per_game",
            "stat_value": 22.0,
            "stats_as_of": datetime(2025, 11, 1, tzinfo=timezone.utc),
            "observed_at": datetime(2025, 11, 1, tzinfo=timezone.utc),
            "validation_status": "matched",
        },
        # 2026 season line — must not appear for as_of 2025-12-01
        {
            "athlete_id": athlete,
            "stat_key": "points_per_game",
            "stat_value": 30.0,
            "stats_as_of": datetime(2026, 2, 1, tzinfo=timezone.utc),
            "observed_at": datetime(2026, 2, 1, tzinfo=timezone.utc),
            "validation_status": "matched",
        },
        # mismatch row — excluded even if timely
        {
            "athlete_id": athlete,
            "stat_key": "games_played_season",
            "stat_value": 99.0,
            "stats_as_of": datetime(2025, 10, 1, tzinfo=timezone.utc),
            "observed_at": datetime(2025, 10, 1, tzinfo=timezone.utc),
            "validation_status": "mismatch",
        },
        {
            "athlete_id": athlete,
            "stat_key": "games_played_season",
            "stat_value": 12.0,
            "stats_as_of": datetime(2025, 10, 1, tzinfo=timezone.utc),
            "observed_at": datetime(2025, 10, 1, tzinfo=timezone.utc),
            "validation_status": "matched",
        },
    ]
    social = [
        {
            "athlete_id": athlete,
            "scraped_at": datetime(2025, 11, 15, tzinfo=timezone.utc),
            "instagram_followers": 1000,
            "tiktok_followers": None,
            "twitter_followers": 50,
            "youtube_subscribers": None,
        },
        {
            "athlete_id": athlete,
            "scraped_at": datetime(2026, 1, 5, tzinfo=timezone.utc),
            "instagram_followers": 999999,
            "tiktok_followers": 1,
            "twitter_followers": 1,
            "youtube_subscribers": 1,
        },
    ]
    df = assemble_snapshot(
        athlete_ids=[athlete],
        as_of=as_of,
        feature_set="pit_core",
        season_rows=season,
        social_rows=social,
    )
    assert len(df) == 1
    row = df.iloc[0]
    assert row["points_per_game"] == 22.0
    assert row["games_played_season"] == 12.0
    assert row["instagram_followers"] == 1000
    assert row["twitter_followers"] == 50
    assert 0.0 < row["feature_coverage"] <= 1.0


def test_build_snapshot_via_connection():
    as_of = datetime(2025, 12, 1, tzinfo=timezone.utc)
    athlete = "22222222-2222-2222-2222-222222222222"
    conn = _FakeConn(
        {
            "season": [
                {
                    "athlete_id": athlete,
                    "stat_key": "recruiting_stars",
                    "stat_value": 4.0,
                    "stats_as_of": datetime(2024, 6, 1, tzinfo=timezone.utc),
                    "observed_at": datetime(2024, 6, 1, tzinfo=timezone.utc),
                    "validation_status": "matched",
                }
            ],
            "social": [],
            "metric": [
                {
                    "athlete_id": athlete,
                    "metric_key": "google_trends_score",
                    "numeric_value": 41.0,
                    "period_start": datetime(2025, 11, 1, tzinfo=timezone.utc),
                    "observed_at": datetime(2025, 11, 1, tzinfo=timezone.utc),
                },
                {
                    "athlete_id": athlete,
                    "metric_key": "google_trends_score",
                    "numeric_value": 90.0,
                    "period_start": datetime(2026, 3, 1, tzinfo=timezone.utc),
                    "observed_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
                },
            ],
        }
    )
    df = build_snapshot(conn, [athlete], as_of, "pit_core")
    assert df.iloc[0]["recruiting_stars"] == 4.0
    assert df.iloc[0]["google_trends_score"] == 41.0
