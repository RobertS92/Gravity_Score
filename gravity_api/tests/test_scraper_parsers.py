"""Parser unit tests."""

from gravity_api.scrapers.parsers.achievements import parse_achievements_from_text
from gravity_api.scrapers.parsers.common import extract_handles, parse_count
from gravity_api.scrapers.parsers.nil import is_suspect_nil, verify_nil_consensus
from gravity_api.scrapers.parsers.roster import parse_transfer_portal
from gravity_api.scrapers.parsers.social import merge_handle_sources


def test_extract_handles():
    text = "Follow on instagram.com/johndoe and tiktok.com/@jdoe x.com/johndoe"
    h = extract_handles(text)
    assert h.get("instagram") == "johndoe"
    assert h.get("tiktok") == "jdoe"
    assert h.get("twitter") == "johndoe"


def test_parse_count():
    assert parse_count("1.2M followers") == 1_200_000
    assert parse_count("850K subscribers") == 850_000


def test_nil_suspect_band():
    assert is_suspect_nil(250_000) is True
    assert is_suspect_nil(2_000_000) is False


def test_nil_consensus():
    out = verify_nil_consensus(
        [
            {"nil_valuation": 1_000_000, "confidence": 0.9, "source": "on3"},
            {"nil_valuation": 900_000, "confidence": 0.8, "source": "opendorse"},
        ]
    )
    assert out["nil_valuation"] > 900_000
    assert out["nil_confidence"] > 0.8


def test_transfer_portal_parse():
    text = "John Smith entered the transfer portal on 2025-01-15 and committed to Texas."
    parsed = parse_transfer_portal(text)
    assert parsed["in_transfer_portal"] is True
    assert parsed["destination_school"]


def test_achievements_parse():
    text = "2024 All-American first team\nHeisman finalist\nSEC Player of the Year"
    parsed = parse_achievements_from_text(text)
    assert parsed["all_american_count"] >= 1
    assert parsed["heisman_finalist"] is True


def test_merge_handles():
    merged = merge_handle_sources(
        {"instagram": "a", "_source": "espn"},
        {"instagram": "b", "twitter": "c", "_source": "roster"},
    )
    assert merged["instagram_handle"] == "a"
    assert merged["twitter_handle"] == "c"
    assert merged["handle_confidence"] >= 0.85
