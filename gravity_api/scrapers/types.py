"""Shared types for micro-scrapers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

ScraperRunStatus = Literal["success", "partial", "failed", "skipped"]


@dataclass
class AthleteScrapeContext:
    athlete_id: str
    name: str
    sport: str
    school: str | None = None
    team: str | None = None
    position: str | None = None
    conference: str | None = None
    class_year: str | None = None
    espn_id: str | None = None
    college: str | None = None
    draft_year: int | None = None
    existing_raw: dict[str, Any] = field(default_factory=dict)
    league_tier: str = "college"

    @property
    def is_pro(self) -> bool:
        return self.sport in {"nfl", "nba", "wnba"} or self.league_tier == "pro"


@dataclass
class ScraperResult:
    scraper_key: str
    status: ScraperRunStatus
    fields: dict[str, Any] = field(default_factory=dict)
    fields_written: list[str] = field(default_factory=list)
    fields_failed: list[str] = field(default_factory=list)
    confidence: float = 0.75
    source_key: str = "espn"
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark_field(self, key: str, value: Any, *, confidence: float | None = None) -> None:
        if value is None or value == "":
            self.fields_failed.append(key)
            return
        self.fields[key] = value
        if key not in self.fields_written:
            self.fields_written.append(key)
        if confidence is not None:
            self.confidence = min(self.confidence, confidence)


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)
