"""Parser unit tests."""

from gravity_api.scrapers.parsers.achievements import parse_achievements_from_text
from gravity_api.scrapers.parsers.common import extract_handles, parse_count
from gravity_api.scrapers.parsers.nil import is_suspect_nil, verify_nil_consensus
from gravity_api.scrapers.parsers.opendorse import parse_opendorse_profile
from gravity_api.scrapers.parsers.recruiting import parse_247_recruiting_profile
from gravity_api.scrapers.parsers.roster import parse_transfer_portal
from gravity_api.scrapers.parsers.social import merge_handle_sources
from gravity_api.scrapers.parsers.sports_reference import parse_sports_ref_honors, ref_domain_for_sport


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


def test_247_recruiting_parse():
    text = (
        "5-star recruit National Rank #42 Position Rank #3 State Rank #1 "
        "https://247sports.com/player/john-smith-123456/"
    )
    out = parse_247_recruiting_profile(text)
    assert out["recruiting_stars"] == 5.0
    assert out["recruiting_rank_national"] == 42.0
    assert out["recruiting_rank_position"] == 3.0
    assert out["external_id_247"] == "123456"


def test_opendorse_parse():
    text = (
        "https://opendorse.com/athletes/jane-doe NIL valuation $850,000 "
        "engagement rate 4.2% followers 120K"
    )
    out = parse_opendorse_profile(text)
    assert out["marketplace_listing"] is True
    assert out["nil_valuation"] == 850_000.0
    assert out["engagement_rate"] == 4.2


def test_sports_ref_honors_parse():
    text = "2023 All-Pro first team\n2022 All-Star\n2021 Pro Bowl\nNBA MVP 2023"
    out = parse_sports_ref_honors(text)
    assert out["all_pro_count"] >= 1.0
    assert out["all_star_count"] >= 1.0
    assert out["major_awards_json"]


def test_ref_domain_mapping():
    assert ref_domain_for_sport("nfl") == "pro-football-reference.com"
    assert ref_domain_for_sport("cfb") == "sports-reference.com/cfb"
