"""Tests for scraper acceptance criteria."""

from gravity_api.scraper_registry.acceptance import evaluate_athlete_acceptance


def test_college_athlete_passes_required_with_stats():
    raw = {
        "espn_id": "123",
        "position": "QB",
        "team": "Alabama",
        "stats_as_of": "2025-09-01",
        "games_played_season": 12,
        "season_stats": {"pass_yards": 3200, "pass_td": 28, "passer_rating": 165.2},
    }
    acc = evaluate_athlete_acceptance(
        athlete_id="a1",
        name="Test QB",
        sport="cfb",
        raw=raw,
        conference="SEC",
    )
    assert acc.required_passed


def test_instagram_optional_does_not_block_required():
    raw = {
        "espn_id": "123",
        "position": "QB",
        "team": "Alabama",
        "stats_as_of": "2025-09-01",
        "games_played_season": 12,
        "season_stats": {"pass_yards": 3200, "pass_td": 28, "passer_rating": 165.2},
        "instagram_followers": 2500,
    }
    acc = evaluate_athlete_acceptance(
        athlete_id="a1",
        name="Test QB",
        sport="cfb",
        raw=raw,
        conference="SEC",
    )
    ig = next(c for c in acc.checks if c.name == "instagram_followers")
    assert not ig.passed
    assert ig.optional
    assert acc.required_passed


def test_pro_contract_value_signal():
    raw = {
        "espn_id": "99",
        "position": "QB",
        "team": "Chiefs",
        "stats_as_of": "2025-09-01",
        "games_played_season": 17,
        "season_stats": {"pass_yards": 4500, "pass_td": 35, "passer_rating": 110.0},
        "contract_aav_usd": 45_000_000,
    }
    acc = evaluate_athlete_acceptance(
        athlete_id="p1",
        name="Pro QB",
        sport="nfl",
        raw=raw,
        conference="AFC West",
    )
    assert acc.required_passed
    assert acc.value_signal_passed
