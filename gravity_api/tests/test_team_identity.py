from gravity_api.services.team_identity import (
    canonical_team_sport,
    index_teams_by_school_sport,
    lookup_team_id,
    school_key,
    team_sport_slugs_for,
)


def test_canonical_team_sport_aliases():
    assert canonical_team_sport("mcbb") == "ncaab_mens"
    assert canonical_team_sport("CFB") == "cfb"
    assert canonical_team_sport("wcbb") == "ncaab_womens"


def test_school_key_strips_punctuation():
    assert school_key("Texas A&M") == school_key("Texas AM")
    assert school_key("  St. John's  ") == "stjohns"


def test_index_and_lookup_by_school_sport():
    teams = index_teams_by_school_sport(
        [
            {"id": "t1", "school_name": "State U", "sport": "ncaab_mens"},
            {"id": "t2", "school_name": "State U.", "sport": "cfb"},
        ]
    )
    assert lookup_team_id(teams, "State U", "mcbb") == "t1"
    assert lookup_team_id(teams, "State U", "cfb") == "t2"
    assert lookup_team_id(teams, "Missing U", "cfb") is None


def test_team_sport_slugs_for():
    assert team_sport_slugs_for("mcbb") == ["ncaab_mens"]
    assert team_sport_slugs_for("") == []
