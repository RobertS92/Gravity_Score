"""Base class for micro-scrapers."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import ClassVar

from gravity_api.scrapers.types import AthleteScrapeContext, ScraperResult


class BaseMicroScraper(ABC):
    KEY_SUFFIX: ClassVar[str] = ""
    SOURCE_KEY: ClassVar[str] = "espn"

    @classmethod
    def scraper_key(cls, sport: str) -> str:
        return f"{cls.KEY_SUFFIX}_{sport}"

    @classmethod
    def matches_key(cls, scraper_key: str) -> bool:
        return bool(cls.KEY_SUFFIX and scraper_key.startswith(f"{cls.KEY_SUFFIX}_"))

    @classmethod
    def sport_from_key(cls, scraper_key: str) -> str | None:
        if not cls.matches_key(scraper_key):
            return None
        return scraper_key[len(cls.KEY_SUFFIX) + 1 :]

    @abstractmethod
    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        raise NotImplementedError

    def _result(
        self,
        scraper_key: str,
        *,
        status: str = "success",
        fields: dict | None = None,
        confidence: float = 0.75,
        error: str | None = None,
    ) -> ScraperResult:
        fields = fields or {}
        written = [k for k, v in fields.items() if v is not None and v != ""]
        failed = [k for k in fields if k not in written]
        if error and not written:
            status = "failed"
        elif error and written:
            status = "partial"
        elif not written:
            status = "skipped"
        return ScraperResult(
            scraper_key=scraper_key,
            status=status,  # type: ignore[arg-type]
            fields=fields,
            fields_written=written,
            fields_failed=failed,
            confidence=confidence,
            source_key=self.SOURCE_KEY,
            error_message=error,
        )


def sport_from_any_key(scraper_key: str) -> str:
    """Extract sport suffix from keys like foo_bar_cfb or spotrac_contract_nfl."""
    known = (
        "ncaab_mens",
        "ncaab_womens",
        "ncaa_baseball",
        "ncaa_volleyball",
        "cfb",
        "nfl",
        "nba",
        "wnba",
        "mcbb",
        "wcbb",
    )
    for s in known:
        if scraper_key.endswith(f"_{s}"):
            return s
    parts = scraper_key.rsplit("_", 1)
    return parts[-1] if len(parts) == 2 else "*"
