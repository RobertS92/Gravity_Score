"""Tests for scraper registry manifest."""

from __future__ import annotations

from gravity_api.scraper_registry import (
    build_registry,
    registry_by_key,
    resolve_event_scraper_keys,
)
from gravity_api.scraper_registry.events import COLLECTOR_MAP
from gravity_api.services.scraper_registry_service import manifest_summary


def test_registry_has_expected_sports():
    reg = build_registry()
    sports = {d.sport for d in reg}
    assert "cfb" in sports
    assert "ncaa_baseball" in sports
    assert "ncaa_volleyball" in sports
    assert "nfl" in sports
    assert "nba" in sports


def test_college_vs_pro_terminal_visibility():
    reg = build_registry()
    nfl = [d for d in reg if d.sport == "nfl"]
    cfb = [d for d in reg if d.sport == "cfb"]
    assert nfl and all(not d.terminal_visible for d in nfl)
    assert cfb and all(d.terminal_visible for d in cfb)


def test_achievements_scrapers_present():
    reg = build_registry()
    ach = [d for d in reg if d.dimension == "achievements"]
    assert len(ach) >= 40
    keys = {d.scraper_key for d in ach}
    assert "espn_awards_cfb" in keys
    assert "national_awards_cfb" in keys
    assert "avca_all_american_volleyball" in keys


def test_quality_boosters_present():
    keys = registry_by_key()
    assert "social_handle_discovery_cfb" in keys
    assert "nil_deal_verified_cfb" in keys
    assert "ncaa_official_roster_cfb" in keys
    assert "injury_structured_cfb" in keys


def test_resolve_scheduled_full_cfb():
    keys = resolve_event_scraper_keys("scheduled_full", "cfb")
    assert "espn_roster_cfb" in keys
    assert "espn_awards_cfb" in keys
    assert "social_handle_discovery_cfb" in keys
    assert "cfbd_api_stats_cfb" in keys


def test_resolve_achievements_event_volleyball():
    keys = resolve_event_scraper_keys("achievements_update", "ncaa_volleyball")
    assert "espn_awards_ncaa_volleyball" in keys
    assert "avca_all_american_volleyball" in keys


def test_collector_map_includes_achievements():
    assert "achievements" in COLLECTOR_MAP["scheduled_full"]
    assert COLLECTOR_MAP["achievements_update"] == ["achievements", "proof"]


def test_manifest_summary_counts():
    summary = manifest_summary()
    assert summary["total"] >= 200
    assert summary["achievements_scrapers"] >= 40
    assert summary["required_for_scoring"] >= 20
    assert summary["by_league_tier"]["college"] > summary["by_league_tier"]["pro"]


def test_unique_scraper_keys():
    reg = build_registry()
    keys = [d.scraper_key for d in reg]
    assert len(keys) == len(set(keys))
