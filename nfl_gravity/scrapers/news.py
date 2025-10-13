"""Google News RSS metrics adapter."""

from __future__ import annotations

import statistics
import time
from typing import Dict, Optional
from urllib.parse import quote_plus
from xml.etree import ElementTree

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from .utils import AdapterResult, RequestManager, fields_with_values, log_request, utc_now_iso

NEWS_URL = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


def _extract_entries(xml_content: str) -> list[ElementTree.Element]:
    root = ElementTree.fromstring(xml_content)
    return root.findall(".//item")


def fetch_news_metrics(
    athlete: str,
    session: Optional[RequestManager] = None,
) -> AdapterResult:
    start = time.perf_counter()
    manager = session or RequestManager()
    url = NEWS_URL.format(query=quote_plus(athlete))
    data: Dict[str, Optional[float]] = {}
    try:
        response = manager.get(url)
        xml_text = response.text
    except Exception:
        xml_text = ""

    if xml_text:
        entries = _extract_entries(xml_text)
        analyzer = SentimentIntensityAnalyzer()
        scores = []
        for entry in entries:
            title = entry.findtext("title", default="")
            summary = entry.findtext("description", default="")
            text = f"{title} {summary}".strip()
            if not text:
                continue
            scores.append(analyzer.polarity_scores(text)["compound"])
        data["news_count"] = len(entries)
        if scores:
            data["sentiment_compound"] = statistics.mean(scores)
    timestamp = utc_now_iso()
    elapsed = (time.perf_counter() - start) * 1000
    log_request("news", athlete, url, "success" if data else "empty", elapsed, list(fields_with_values(data)))
    return AdapterResult(data=data, url=url, timestamp=timestamp)


__all__ = ["fetch_news_metrics"]
