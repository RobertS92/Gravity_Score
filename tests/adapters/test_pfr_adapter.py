"""Adapter-level tests for the PFR scraper."""

from nfl_gravity.scrapers.pfr import fetch_pfr_career
from nfl_gravity.scrapers.utils import RequestManager


class DummyDiscovery:
    def __init__(self, url: str):  # pragma: no cover - trivial
        self._url = url

    def discover(self, *args, **kwargs):  # pragma: no cover - trivial
        return self._url


def test_fetch_pfr_career_handles_response(requests_mock) -> None:
    discovery = DummyDiscovery("https://www.pro-football-reference.com/players/J/JackLa00.htm")
    requests_mock.get(
        "https://www.pro-football-reference.com/robots.txt",
        text="User-agent: *\nAllow: /",
    )
    requests_mock.get(
        "https://www.pro-football-reference.com/players/J/JackLa00.htm",
        text="""
        <table id='passing'>
            <tr id='Career'>
                <td data-stat='pass_yds'>1000</td>
                <td data-stat='pass_td'>10</td>
            </tr>
        </table>
        """,
    )
    result = fetch_pfr_career("Lamar Jackson", discovery=discovery, session=RequestManager())
    assert result.data["career_yards"] == 1000
