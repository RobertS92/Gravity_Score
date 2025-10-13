"""Unit tests for Spotrac parsing."""

from nfl_gravity.scrapers.spotrac import parse_career_earnings


def test_parse_career_earnings_extracts_amount() -> None:
    text = "Player Contract\nCareer Earnings: $123,456,789"
    assert parse_career_earnings(text) == 123456789


def test_parse_career_earnings_missing_returns_none() -> None:
    assert parse_career_earnings("No earnings here") is None
