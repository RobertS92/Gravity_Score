"""Optional live smoke tests for Wikipedia and News adapters."""

import os

import pytest

from nfl_gravity.scrapers.news import fetch_news_metrics
from nfl_gravity.scrapers.wikipedia import fetch_wikipedia_profile


LIVE = os.environ.get("GRAVITY_LIVE_TESTS") == "1"


@pytest.mark.integration
@pytest.mark.skipif(not LIVE, reason="Live tests disabled")
def test_live_wikipedia_and_news() -> None:
    wiki = fetch_wikipedia_profile("Patrick Mahomes")
    assert wiki.url
    assert isinstance(wiki.data, dict)

    news = fetch_news_metrics("Patrick Mahomes")
    assert news.url
    assert news.data.get("news_count", 0) >= 0
