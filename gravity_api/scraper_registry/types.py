"""Scraper registry types — canonical manifest for gravity-scrapers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

LeagueTier = Literal["college", "pro"]
ScraperDimension = Literal["identity", "brand", "proof", "proximity", "velocity", "risk", "achievements"]
ScraperStatus = Literal["active", "legacy", "stub", "planned"]
SourceType = Literal["official", "licensed", "public_api", "scrape", "manual", "derived"]


@dataclass(frozen=True)
class ScraperDefinition:
    scraper_key: str
    display_name: str
    sport: str
    league_tier: LeagueTier
    dimension: ScraperDimension
    source: str
    source_type: SourceType
    description: str
    feature_keys: tuple[str, ...]
    status: ScraperStatus = "planned"
    terminal_visible: bool = True
    required_for_scoring: bool = False
    sla_days: int = 7
    default_confidence: float = 0.75
    circuit_breaker_source: str | None = None
    priority: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["feature_keys"] = list(self.feature_keys)
        return d
