"""Adapter-level tests for Wikipedia scraping."""

from nfl_gravity.scrapers.wikipedia import fetch_wikipedia_profile
from nfl_gravity.scrapers.utils import RequestManager


class DummyDiscovery:
    def __init__(self, url: str):  # pragma: no cover - trivial
        self._url = url

    def discover(self, *args, **kwargs):  # pragma: no cover - trivial
        return self._url


def test_fetch_wikipedia_profile(requests_mock) -> None:
    discovery = DummyDiscovery("https://en.wikipedia.org/wiki/Lamar_Jackson")
    requests_mock.get(
        "https://en.wikipedia.org/robots.txt",
        text="User-agent: *\nAllow: /",
    )
    requests_mock.get(
        "https://en.wikipedia.org/wiki/Lamar_Jackson",
        text="""
        <table class='infobox'>
            <tr><th>Position</th><td>Quarterback</td></tr>
            <tr><th>Born</th><td>1997 (age 27)</td></tr>
        </table>
        """,
    )

    result = fetch_wikipedia_profile("Lamar Jackson", discovery=discovery, session=RequestManager())
    assert result.url.endswith("Lamar_Jackson")
    assert result.data["position"] == "Quarterback"
