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


def test_roster_item_to_raw_fields():
    item = {
        "id": 22854,
        "displayName": "Test Player",
        "jersey": "12",
        "position": {"abbreviation": "P"},
        "experience": {"displayValue": "Junior"},
        "height": 72,
        "weight": 190,
    }
    fields = EspnClient.roster_item_to_raw_fields(
        item, team_name="LSU Tigers", conference="SEC"
    )
    assert fields["espn_id"] == "22854"
    assert fields["player_name"] == "Test Player"
    assert fields["roster_seeded"] is True
    assert fields["position"] == "P"
    assert fields["class_year"] == "Junior"


def test_baseball_profile_uses_core_api(monkeypatch):
    client = EspnClient()

    async def fake_site(*_a, **_k):
        return {}

    async def fake_core(self, _sport, path):
        assert path == "athletes/22854"
        return {
            "id": "22854",
            "displayName": " Aberouette",
            "position": {"abbreviation": "P"},
        }

    monkeypatch.setattr(client, "_get_athlete_profile_site", fake_site)
    monkeypatch.setattr(EspnClient, "_get_core", fake_core)

    import asyncio

    profile = asyncio.run(client.get_athlete_profile("22854", "ncaa_baseball"))
    assert profile["identity"]["player_name"] == " Aberouette"
    assert profile["identity"]["position"] == "P"


def test_espn_nested_description_string_or_dict():
    assert _espn_nested_description({"description": "Out"}) == "Out"
    assert _espn_nested_description("Questionable") == "Questionable"
    assert _espn_nested_description(None) is None
