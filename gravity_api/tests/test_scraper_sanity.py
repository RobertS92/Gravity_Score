"""Fixture-based sanity assertions for free-tier ESPN scrape correctness.

Covers: defensive sacks/TFL mapping, season vs career GP scope, stats_as_of,
and draft-departure identity (Dybantsa / Boozer).
"""

from __future__ import annotations

from gravity_api.scraper_smoke.athletes import DRAFT_DEPARTURE_FIXTURES, SMOKE_ATHLETES
from gravity_api.scrapers.parsers.espn_stats import (
    build_stats_bundle,
    infer_stats_scope,
    stats_from_espn_payload,
)
from gravity_api.scrapers.parsers.stat_normalizer import (
    merge_stat_layers,
    normalize_espn_stats,
)
from gravity_api.services.roster_retirement import (
    classify_identity_match,
    departure_status,
    meets_confidence,
)
from gravity_api.services.roster_sync import _is_college_to_pro_jump


def test_smoke_catalog_still_covers_priority_sports():
    sports = {a.sport for a in SMOKE_ATHLETES}
    for sport in ("nfl", "nba", "cfb", "ncaab_mens", "ncaab_womens"):
        assert sport in sports
    # Draft departures live under NBA, not stale college sport.
    by_name = {a.name: a for a in SMOKE_ATHLETES}
    assert by_name["AJ Dybantsa"].sport == "nba"
    assert by_name["Cameron Boozer"].sport == "nba"
    assert "76ers" in by_name["LeBron James"].team_hint.lower() or by_name[
        "LeBron James"
    ].team_hint.lower() in {"76ers", "philadelphia"}


def test_passing_sacks_do_not_clobber_defensive_sacks():
    """Will Anderson: passing category sacks=0 must lose to defensive sacks=37.5."""
    payload = {
        "splits": {
            "categories": [
                {
                    "name": "passing",
                    "stats": [
                        {"name": "sacks", "value": 0.0},
                        {"name": "gamesPlayed", "value": 0.0},
                    ],
                },
                {
                    "name": "defensive",
                    "stats": [
                        {"name": "sacks", "value": 37.5},
                        {"name": "avgSackYards", "value": 7.733},
                        {"name": "soloTackles", "value": 107.0},
                        {"name": "tacklesForLoss", "value": 0.0},
                        {"name": "stuffs", "value": 36.5},
                        {"name": "gamesPlayed", "value": 52.0},
                    ],
                },
            ]
        }
    }
    flat = stats_from_espn_payload(payload)
    assert flat.get("sacks") == 37.5
    assert flat.get("sacksTaken") == 0.0 or "sacksTaken" in flat
    # avgSackYards must NOT become sacks
    norm = normalize_espn_stats("nfl", flat)
    assert norm["sacks"] == 37.5
    assert norm.get("sacks") != 7.733


def test_sacks_positive_when_source_has_sacks():
    raw = {
        "sacks": 7.5,
        "avgSackYards": 7.733,
        "soloTackles": 16,
        "tacklesForLoss": 0,
        "stuffs": 4.5,
        "gamesPlayed": 6,
    }
    out = normalize_espn_stats("nfl", raw)
    assert out["sacks"] > 0
    assert out["sacks"] == 7.5
    # TFL reconstructed from sacks+stuffs when ESPN zeros tacklesForLoss
    assert out["tfl"] >= out["sacks"]


def test_tfl_at_least_sacks_when_both_present():
    out = normalize_espn_stats(
        "cfb",
        {"sacks": 10.5, "tacklesForLoss": 15.5, "stuffs": 16.5, "gamesPlayed": 6},
    )
    assert out["tfl"] >= out["sacks"]
    assert out["tfl"] == 15.5


def test_tfl_reconstructed_when_espn_zeros_career_tfl():
    out = normalize_espn_stats(
        "cfb",
        {
            "sacks": 31.5,
            "tacklesForLoss": 0.0,
            "stuffs": 16.5,
            "soloTackles": 71,
            "totalTackles": 116,
            "gamesPlayed": 32,
        },
    )
    assert out["tfl"] >= out["sacks"]
    assert out["tfl"] == 31.5 + 16.5


def test_season_gp_capped_for_cfb_and_ncaab():
    # Career-sized GP on flat payload with no history → career scope, no fake season GP.
    fields = merge_stat_layers(
        "cfb",
        current={"passingYards": 5427, "passingTouchdowns": 46, "gamesPlayed": 30},
        career={"passingYards": 5427, "gamesPlayed": 30},
    )
    assert fields.get("stats_scope") in {"career", "multi_season"}
    assert fields.get("games_played_career") == 30
    # Season GP must not exceed CFB cap when scope is career-only.
    if fields.get("games_played_season") is not None:
        assert fields["games_played_season"] <= 17

    hist_fields = merge_stat_layers(
        "cfb",
        current={"passingYards": 1295, "passingTouchdowns": 11, "gamesPlayed": 6},
        history={
            "2025": {"passingYards": 3163, "passingTouchdowns": 26, "gamesPlayed": 14},
            "2026": {"passingYards": 1295, "passingTouchdowns": 11, "gamesPlayed": 6},
        },
        career={"passingYards": 5427, "gamesPlayed": 30},
        stats_scope="season",
        stats_as_of="2026",
    )
    assert hist_fields["stats_scope"] == "season"
    assert hist_fields["games_played_season"] <= 17
    assert hist_fields["pass_yards"] == 1295.0
    assert hist_fields["pass_td"] == 11.0
    assert hist_fields["stats_as_of"] == "2026"

    ncaab = merge_stat_layers(
        "ncaab_mens",
        current={"points": 894, "gamesPlayed": 35},
        history={"2026": {"points": 894, "gamesPlayed": 35}},
        stats_as_of="2026",
    )
    assert ncaab["games_played_season"] <= 45
    assert ncaab["stats_as_of"] == "2026"


def test_build_stats_bundle_prefers_latest_season_not_career_totals():
    payload = {
        "categories": [
            {
                "name": "passing",
                "names": ["passingYards", "passingTouchdowns", "gamesPlayed"],
                "statistics": [
                    {
                        "season": {"year": 2025},
                        "stats": ["3163", "26", "14"],
                    },
                    {
                        "season": {"year": 2026},
                        "stats": ["1295", "11", "6"],
                    },
                ],
                "totals": ["5427", "46", "30"],
            }
        ]
    }
    bundle = build_stats_bundle(payload, sport="cfb")
    assert bundle["stats_scope"] == "season"
    assert bundle["current"]["passingYards"] in (1295, "1295", 1295.0)
    assert str(bundle["stats_as_of"]) == "2026"
    assert infer_stats_scope(
        history=bundle["history"],
        career=bundle["career"],
        current=bundle["current"],
        sport="cfb",
    ) == "season"


def test_dybantsa_boozer_same_espn_id_is_high_confidence_draft():
    for fix in DRAFT_DEPARTURE_FIXTURES:
        conf = classify_identity_match(
            {
                "espn_id": fix["espn_id"],
                "sport": fix["college_sport"],
                "position": "F",
                "class_year": "Freshman",
            },
            {
                "espn_id": fix["espn_id"],
                "sport": fix["pro_sport"],
                "position": "F",
            },
        )
        assert conf == "high", fix["name"]
        assert meets_confidence(conf, "medium")
        status, reason = departure_status("Freshman", has_pro_match=True)
        assert status == fix["expected_roster_status"]
        assert reason == "active_pro_roster_match"
        assert _is_college_to_pro_jump(fix["college_sport"], fix["pro_sport"])
