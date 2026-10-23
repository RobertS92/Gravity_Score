"""Smoke/export CSV must expose full WP9 season provenance columns."""

from __future__ import annotations

from gravity_api.scraper_smoke.runner import (
    SMOKE_PROVENANCE_COLUMNS,
    normalize_stats_scope,
    smoke_csv_fieldnames,
    smoke_results_to_csv_rows,
    write_smoke_csv,
)
from gravity_api.services.training_export import (
    SEASON_PROVENANCE_KEYS,
    build_scraped_row,
    flatten_raw_data_export,
)


REQUIRED_PROVENANCE = (
    "season_year",
    "season_label",
    "season_type",
    "team_id",
    "is_total",
    "is_complete",
    "stats_as_of",
    "validation_status",
    "n_seasons",
)


def _payload_with_history() -> dict:
    return {
        "results": [
            {
                "sport": "nba",
                "name": "LeBron James",
                "espn_id": "1966",
                "mode": "espn_scrapers",
                "passed": True,
                "fields_sample": {
                    "stats_scope": "season",
                    "stats_as_of": "2026-10-22T00:00:00Z",
                    "team": "Philadelphia 76ers",
                    "games_played_season": 1,
                    "_fields": {
                        "stats_scope": "season",
                        "stats_as_of": "2026-10-22T00:00:00Z",
                        "games": "Philadelphia 76ers",
                        "games_played_season": 1,
                        "season_stats": {
                            "pts": 14.0,
                            "games_played_season": 1,
                        },
                        "season_stats_history": {
                            "2025-26": {
                                "pts": 24.0,
                                "games_played_season": 70,
                                "team_id": "13",
                                "is_total": False,
                            },
                            "2026-27": {
                                "pts": 14.0,
                                "games_played_season": 1,
                                "team_id": "20",
                                "is_total": False,
                            },
                        },
                        "career_stats": {
                            "pts": 40000.0,
                            "games_played_career": 1623,
                            "games_played_season": 1623,  # must not become career_*
                        },
                    },
                },
            }
        ]
    }


def test_normalize_stats_scope_only_season_or_career():
    assert normalize_stats_scope("season") == "season"
    assert normalize_stats_scope("career") == "career"
    assert normalize_stats_scope("multi_season") == "career"
    assert normalize_stats_scope("bogus") is None
    assert normalize_stats_scope(None) is None


def test_smoke_csv_rows_include_full_provenance_columns():
    rows = smoke_results_to_csv_rows(_payload_with_history())
    assert rows
    season_rows = [r for r in rows if r.get("stats_scope") == "season"]
    career_rows = [r for r in rows if r.get("stats_scope") == "career"]
    assert len(season_rows) == 2
    assert len(career_rows) == 1

    for row in rows:
        for col in REQUIRED_PROVENANCE:
            assert col in row, f"missing {col} on row scope={row.get('stats_scope')}"
        assert row.get("stats_scope") in ("season", "career")

    # Season grain populated on season rows.
    by_year = {r["season_year"]: r for r in season_rows}
    assert 2026 in by_year and 2027 in by_year
    assert by_year[2026]["season_label"] == "2025-26"
    assert by_year[2026]["season_type"] == "regular"
    assert by_year[2026]["team_id"] == "13"
    assert by_year[2026]["is_total"] is False
    assert by_year[2026]["stats_as_of"] == "2026-10-22T00:00:00Z"
    assert by_year[2026]["validation_status"] == "unvalidated"
    assert by_year[2026].get("games_played_season") == 70

    career = career_rows[0]
    assert career.get("n_seasons") == 2
    assert career.get("career_pts") == 40000.0
    assert career.get("career_games_played_career") == 1623
    # WP9: games_played_season must not appear in career context.
    assert "games_played_season" not in career or career.get("games_played_season") in (
        None,
        "",
    )
    assert "career_games_played_season" not in career


def test_smoke_csv_header_includes_provenance_and_career_keys(tmp_path):
    payload = _payload_with_history()
    path = tmp_path / "smoke.csv"
    n = write_smoke_csv(payload, path)
    assert n >= 3
    header = path.read_text(encoding="utf-8").splitlines()[0].split(",")
    for col in ("stats_scope", *SMOKE_PROVENANCE_COLUMNS):
        assert col in header
    assert "career_pts" in header
    # Fieldnames helper stays stable.
    rows = smoke_results_to_csv_rows(payload)
    names = smoke_csv_fieldnames(rows)
    for col in REQUIRED_PROVENANCE:
        assert col in names


def test_smoke_csv_rows_include_stats_scope_and_as_of():
    """Backward-compatible smoke of the original provenance assertion."""
    payload = {
        "results": [
            {
                "sport": "nba",
                "name": "LeBron James",
                "espn_id": "1966",
                "mode": "espn_scrapers",
                "passed": True,
                "fields_sample": {
                    "stats_scope": "season",
                    "stats_as_of": "2027",
                    "team": "Philadelphia 76ers",
                },
            }
        ]
    }
    rows = smoke_results_to_csv_rows(payload)
    assert rows[0]["stats_scope"] == "season"
    assert rows[0]["stats_as_of"] == "2027"
    for col in REQUIRED_PROVENANCE:
        assert col in rows[0]


def test_export_row_always_has_provenance_keys():
    row = build_scraped_row(
        entity_id="x",
        sport="cfb",
        identity={"name": "Arch Manning"},
        raw_data={},
        has_raw=False,
    )
    assert "stats_scope" in row
    for key in SEASON_PROVENANCE_KEYS:
        assert key in row
    flat = flatten_raw_data_export({"stats_scope": "season", "stats_as_of": "2026"})
    assert flat["stats_scope"] == "season"
    assert flat["stats_as_of"] == "2026"
    for key in SEASON_PROVENANCE_KEYS:
        assert key in flat


def test_export_career_scope_strips_games_played_season():
    raw = {
        "stats_scope": "multi_season",
        "stats_as_of": "2026-01-01T00:00:00Z",
        "games_played_season": 1623,
        "career_stats": {"pts": 1.0, "games_played_career": 1623, "gp": 99},
        "season_stats_history": {"2024": {"pts": 1.0}, "2025": {"pts": 2.0}},
        "season_year": 2025,
        "season_label": "2025",
        "season_type": "regular",
        "team_id": "TOT",
        "is_total": True,
        "is_complete": True,
        "validation_status": "unvalidated",
    }
    flat = flatten_raw_data_export(raw)
    assert flat["stats_scope"] == "career"
    assert "games_played_season" not in flat
    assert flat["career_pts"] == 1.0
    assert flat["career_games_played_career"] == 1623
    assert "career_gp" not in flat
    assert flat["n_seasons"] == 2

    row = build_scraped_row(
        entity_id="y",
        sport="nba",
        identity={"name": "LeBron James"},
        raw_data=raw,
        has_raw=True,
    )
    assert row["stats_scope"] == "career"
    assert "games_played_season" not in row
    assert row["career_pts"] == 1.0
    assert row["n_seasons"] == 2
