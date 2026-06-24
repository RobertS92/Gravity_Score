"""Tests for ESPN stat normalization and multi-season parsing."""

from __future__ import annotations

from gravity_api.scrapers.parsers.espn_stats import (
    build_stats_bundle,
    extract_season_history,
    stats_from_espn_payload,
)
from gravity_api.scrapers.parsers.stat_catalog import all_stat_keys_for_sport
from gravity_api.scrapers.parsers.stat_normalizer import (
    merge_stat_layers,
    normalize_espn_stats,
    parse_stat_value,
)


def test_parse_stat_value_formats():
    assert parse_stat_value("3,245") == 3245.0
    assert parse_stat_value("62.5%") == 62.5
    assert parse_stat_value("—") is None
    assert parse_stat_value(42) == 42.0


def test_normalize_football_passing_stats():
    raw = {
        "passingYards": "3,512",
        "passingTouchdowns": 28,
        "interceptions": 7,
        "completionPct": "64.2",
        "QBR": 72.3,
        "gamesPlayed": 12,
    }
    out = normalize_espn_stats("cfb", raw)
    assert out["pass_yards"] == 3512.0
    assert out["pass_td"] == 28.0
    assert out["pass_int"] == 7.0
    assert out["completion_pct"] == 64.2
    assert out["qbr"] == 72.3
    assert out["games_played_season"] == 12.0


def test_normalize_basketball_stats():
    raw = {"PTS": 18.4, "AST": 6.2, "REB": 4.1, "FG%": "47.5", "GP": 32}
    out = normalize_espn_stats("nba", raw)
    assert out["pts"] == 18.4
    assert out["ast"] == 6.2
    assert out["reb"] == 4.1
    assert out["fg_pct"] == 47.5
    assert out["games_played_season"] == 32.0


def test_merge_stat_layers_flattens_current_season():
    fields = merge_stat_layers(
        "cfb",
        current={"passingYards": 3000, "passingTouchdowns": 25, "gamesPlayed": 11},
        history={"2023": {"passingYards": 2100, "gamesPlayed": 10}},
        career={"passingYards": 9100, "gamesPlayed": 36},
    )
    assert fields["pass_yards"] == 3000.0
    assert fields["pass_td"] == 25.0
    assert fields["games_played_season"] == 11
    assert "2023" in fields["season_stats_history"]
    assert fields["career_stats"]["pass_yards"] == 9100.0
    assert fields["games_played_career"] == 36.0


def test_extract_season_history_from_split_categories():
    payload = {
        "splitCategories": [
            {
                "displayName": "2024 Regular Season",
                "categories": [
                    {
                        "stats": [
                            {"name": "passingYards", "value": 2800},
                            {"name": "gamesPlayed", "value": 12},
                        ]
                    }
                ],
            },
            {
                "displayName": "2023 Regular Season",
                "categories": [
                    {
                        "stats": [
                            {"name": "passingYards", "value": 1900},
                            {"name": "gamesPlayed", "value": 10},
                        ]
                    }
                ],
            },
        ]
    }
    history = extract_season_history(payload)
    assert "2024" in history
    assert "2023" in history
    assert history["2024"]["passingYards"] == 2800


def test_build_stats_bundle_includes_history():
    bundle = build_stats_bundle(
        {
            "splitCategories": [
                {
                    "displayName": "2024 Regular Season",
                    "categories": [{"stats": [{"name": "points", "value": 20}]}],
                }
            ],
            "displaySeason": "2024-25",
        }
    )
    assert bundle["current"]["points"] == 20
    assert "2024" in bundle["history"]


def test_all_stat_keys_includes_extended_football():
    keys = all_stat_keys_for_sport("cfb")
    assert "pass_yards" in keys
    assert "epa_per_play" in keys or "snap_count" in keys or "pass_attempts" in keys


def test_stats_from_espn_payload_categories():
    data = {
        "splits": {
            "categories": [
                {
                    "stats": [
                        {"abbreviation": "ERA", "displayValue": "2.45"},
                        {"abbreviation": "IP", "displayValue": "56.1"},
                    ]
                }
            ]
        }
    }
    stats = stats_from_espn_payload(data)
    assert stats["ERA"] == "2.45"
    assert stats["IP"] == "56.1"
