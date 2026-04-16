"""
Crawler orchestration was removed from this monorepo.

Use the external scrapers/crawler service repository for event-driven collection.
This class keeps the Railway API contract stable for legacy clients.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_EXTERNAL_MSG = (
    "In-repo crawlers removed; use the external scraper/crawler repository."
)


class CrawlerService:
    """Stub: no local `gravity.crawlers` package."""

    def __init__(self) -> None:
        self.orchestrator = None
        logger.info("CrawlerService: stub mode (%s)", _EXTERNAL_MSG)

    async def run_all_crawlers(
        self,
        athlete_id: str,
        sport: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "skipped": True,
            "message": _EXTERNAL_MSG,
            "athlete_id": athlete_id,
        }

    async def run_crawler(self, crawler_name: str, athlete_id: str) -> Dict[str, Any]:
        return {
            "success": True,
            "skipped": True,
            "crawler": crawler_name,
            "message": _EXTERNAL_MSG,
        }

    def get_crawler_status(self) -> Dict[str, Any]:
        return {
            "available": False,
            "crawlers": [],
            "message": _EXTERNAL_MSG,
        }

    def get_available_crawlers(self) -> List[str]:
        return []
