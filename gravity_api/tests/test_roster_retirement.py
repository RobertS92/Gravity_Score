from gravity_api.services.roster_retirement import (
    classify_identity_match,
    departure_status,
    looks_graduated,
    meets_confidence,
    roster_payload_complete,
    synced_school_names,
)


def test_name_collision_ol_vs_cb_is_rejected():
    assert (
        classify_identity_match(
            {
                "sport": "cfb",
                "position": "OL",
                "height_inches": 75,
                "weight_lbs": 299,
            },
            {
                "sport": "nfl",
                "position": "CB",
                "height_inches": 72,
                "weight_lbs": 185,
            },
        )
        == "reject"
    )


def test_college_espn_id_match_is_high_confidence():
    assert (
        classify_identity_match(
            {"espn_id": "4426513", "sport": "cfb", "position": "S"},
            {"college_espn_id": "4426513", "sport": "nfl", "position": "S"},
        )
        == "high"
    )


def test_same_family_and_measurements_are_medium():
    assert (
        classify_identity_match(
            {
                "sport": "cfb",
                "position": "WR",
                "height_inches": 73,
                "weight_lbs": 205,
                "class_year": "Senior",
            },
            {
                "sport": "nfl",
                "position": "WR",
                "height_inches": 74,
                "weight_lbs": 198,
            },
        )
        == "medium"
    )


def test_underclassman_name_collision_is_not_auto_applied():
    confidence = classify_identity_match(
        {
            "sport": "cfb",
            "position": "OL",
            "height_inches": 74,
            "weight_lbs": 298,
            "class_year": "Sophomore",
        },
        {
            "sport": "nfl",
            "position": "G",
            "height_inches": 75,
            "weight_lbs": 320,
        },
    )
    assert confidence == "low"
    assert not meets_confidence(confidence, "medium")


def test_name_only_is_low_and_not_auto_applied():
    confidence = classify_identity_match(
        {"sport": "cfb", "position": None},
        {"sport": "nfl", "position": None},
    )
    assert confidence == "low"
    assert not meets_confidence(confidence, "medium")


def test_departure_status_prefers_draft_then_graduation():
    assert departure_status("Junior", has_pro_match=True) == (
        "left_for_draft",
        "active_pro_roster_match",
    )
    assert departure_status("Redshirt Senior", has_pro_match=False) == (
        "graduated",
        "absent_from_current_espn_roster",
    )
    assert departure_status("Sophomore", has_pro_match=False) == (
        "out_other",
        "absent_from_current_espn_roster",
    )


def test_freshman_is_not_graduated():
    assert looks_graduated("Freshman") is False
    assert looks_graduated("RS Senior") is True
    assert looks_graduated("Graduate Student") is True


def test_incomplete_espn_payload_does_not_unlock_retirement():
    assert roster_payload_complete({"players_seen": 12, "team_name": "Texas Longhorns"}, "cfb") is False
    assert roster_payload_complete({"players_seen": 0, "error": "empty_roster_payload"}, "cfb") is False
    assert roster_payload_complete({"players_seen": 85, "team_name": "Texas Longhorns"}, "cfb") is True


def test_synced_school_names_include_index_alias_only_for_complete_teams():
    names = synced_school_names(
        [
            {"espn_team_id": "251", "team_name": "Texas Longhorns", "players_seen": 90},
            {"espn_team_id": "61", "team_name": "Georgia Bulldogs", "players_seen": 3},
        ],
        "cfb",
        index_aliases=[
            {"espn_team_id": "251", "school_name": "Texas"},
            {"espn_team_id": "61", "school_name": "Georgia"},
        ],
    )
    assert names == ["Texas Longhorns", "Texas"]
