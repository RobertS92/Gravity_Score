"""Tests for discovery ranking heuristics."""

from nfl_gravity.scrapers.discovery import FirecrawlDiscovery


class DummyFirecrawl:
    def map_url(self, domain, params):  # pragma: no cover - simple stub
        return {
            "urls": [
                f"{domain}/unrelated-page",
                f"{domain}/official/{params['search'].split()[0].lower().replace(' ', '-')}",
            ]
        }


def test_discovery_picks_best() -> None:
    discovery = FirecrawlDiscovery(app=DummyFirecrawl())
    url = discovery.discover("Lamar Jackson", "https://en.wikipedia.org", keyword="wikipedia")
    assert url.endswith("/official/lamar")
