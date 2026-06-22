"""Wikipedia pageview API client."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx


class WikipediaClient:
    WIKI_API = "https://en.wikipedia.org/w/api.php"
    PAGEVIEWS = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user"

    async def resolve_title(self, name: str) -> str | None:
        params = {
            "action": "opensearch",
            "search": name,
            "limit": 3,
            "namespace": 0,
            "format": "json",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(self.WIKI_API, params=params)
            resp.raise_for_status()
            data = resp.json()
        if isinstance(data, list) and len(data) >= 2 and data[1]:
            return str(data[1][0])
        return None

    async def pageviews(self, title: str, *, days: int = 30) -> dict[str, Any]:
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=days)
        slug = title.replace(" ", "_")
        url = (
            f"{self.PAGEVIEWS}/{slug}/daily/"
            f"{start.strftime('%Y%m%d')}/{end.strftime('%Y%m%d')}"
        )
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers={"User-Agent": "GravityScrapers/1.0"})
            if resp.status_code == 404:
                return {"wikipedia_views_7d": 0, "wikipedia_views_30d": 0}
            resp.raise_for_status()
            data = resp.json()
        items = data.get("items") or []
        counts = [int(i.get("views") or 0) for i in items]
        total = sum(counts)
        last_7 = sum(counts[-7:]) if counts else 0
        return {
            "wikipedia_views_30d": total,
            "wikipedia_views_7d": last_7,
            "wikipedia_title": title,
        }

    async def for_athlete(self, name: str) -> dict[str, Any]:
        title = await self.resolve_title(name)
        if not title:
            return {}
        return await self.pageviews(title)
