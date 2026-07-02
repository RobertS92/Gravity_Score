"""Tests for conference normalization and acceptance sport scope."""

from gravity_api.scraper_registry.acceptance_sports import ACCEPTANCE_SPORTS, EXCLUDED_ACCEPTANCE_SPORTS
from gravity_api.services.team_conferences import normalize_conference_display


def test_normalize_standing_conference():
    assert normalize_conference_display("12th in ACC") == "ACC"
    assert normalize_conference_display("SEC") == "SEC"


def test_acceptance_sports_exclude_deferred():
    assert "ncaa_baseball" in EXCLUDED_ACCEPTANCE_SPORTS
    assert "ncaa_volleyball" in EXCLUDED_ACCEPTANCE_SPORTS
    assert "cfb" in ACCEPTANCE_SPORTS
    assert "nba" in ACCEPTANCE_SPORTS
