"""Partner sport filter normalization."""

from gravity_api.services.partner_sports import (
    partner_codes_to_db_slugs,
    resolve_sport_filters,
)


def test_partner_codes_all_sports():
    slugs = partner_codes_to_db_slugs(
        ["CFB", "NCAAB", "NCAAW", "NCAA_BASEBALL", "NCAA_VOLLEYBALL", "NFL", "NBA", "WNBA"]
    )
    assert "cfb" in slugs
    assert "ncaab_mens" in slugs
    assert "ncaab_womens" in slugs
    assert "ncaa_baseball" in slugs
    assert "ncaa_volleyball" in slugs
    assert "nfl" in slugs
    assert "nba" in slugs
    assert "wnba" in slugs


def test_db_slug_filter():
    assert partner_codes_to_db_slugs(["nba", "wnba"]) == ["nba", "wnba"]


def test_ncaab_maps_multiple_slugs():
    single, multi = resolve_sport_filters("NCAAB", None)
    assert single is None
    assert "ncaab_mens" in multi
    assert "mcbb" in multi


def test_single_cfb():
    single, multi = resolve_sport_filters("cfb", None)
    assert single == "cfb"
    assert multi is None


def test_sports_param_multi():
    single, multi = resolve_sport_filters(None, "NBA,WNBA")
    assert single is None
    assert multi == ["nba", "wnba"]
