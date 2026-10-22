"""Smoke/export CSV must always expose stats_scope + stats_as_of."""

from __future__ import annotations

from gravity_api.scraper_smoke.runner import smoke_results_to_csv_rows
from gravity_api.services.training_export import build_scraped_row, flatten_raw_data_export


def test_smoke_csv_rows_include_stats_scope_and_as_of():
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


def test_export_row_always_has_provenance_keys():
    row = build_scraped_row(
        entity_id="x",
        sport="cfb",
        identity={"name": "Arch Manning"},
        raw_data={},
        has_raw=False,
    )
    assert "stats_scope" in row
    assert "stats_as_of" in row
    flat = flatten_raw_data_export({"stats_scope": "season", "stats_as_of": "2026"})
    assert flat["stats_scope"] == "season"
    assert flat["stats_as_of"] == "2026"
