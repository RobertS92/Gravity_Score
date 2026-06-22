"""ESPN client helpers."""

from gravity_api.scrapers.clients.espn import EspnClient, _espn_nested_description


def test_flatten_roster_players_nfl_grouped_buckets():
    payload = {
        "athletes": [
            {
                "position": "offense",
                "items": [
                    {"id": "1", "displayName": "Player One"},
                    {"id": "2", "displayName": "Player Two"},
                ],
            }
        ]
    }
    players = EspnClient.flatten_roster_players(payload)
    assert len(players) == 2
    assert players[0]["id"] == "1"


def test_flatten_roster_players_basketball_flat_list():
    payload = {
        "athletes": [
            {"id": "101", "displayName": "Guard A"},
            {"id": "102", "fullName": "Forward B"},
        ]
    }
    players = EspnClient.flatten_roster_players(payload)
    assert len(players) == 2
    assert players[0]["displayName"] == "Guard A"


def test_espn_nested_description_string_or_dict():
    assert _espn_nested_description({"description": "Out"}) == "Out"
    assert _espn_nested_description("Questionable") == "Questionable"
    assert _espn_nested_description(None) is None
