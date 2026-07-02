"""Build full scraper registry from templates and sport catalog."""

from __future__ import annotations

from gravity_api.scraper_registry.sports import SPORTS
from gravity_api.scraper_registry.league_features import filter_feature_keys_for_league
from gravity_api.scraper_registry.templates import (
    ACHIEVEMENT_SPORTS,
    SHARED_SCRAPERS,
    SPORT_SPECIFIC,
    SPORT_TEMPLATE_GROUPS,
    TEMPLATE_GROUPS,
)
from gravity_api.scraper_registry.types import ScraperDefinition


def _expand_template(sport: str, tpl: dict) -> ScraperDefinition:
    cfg = SPORTS[sport]
    suffix = tpl["suffix"]
    feature_keys = filter_feature_keys_for_league(
        tuple(tpl["feature_keys"]),
        cfg["league_tier"],
    )
    return ScraperDefinition(
        scraper_key=f"{suffix}_{sport}",
        display_name=f"{tpl['display']} ({cfg['display_name']})",
        sport=sport,
        league_tier=cfg["league_tier"],  # type: ignore[arg-type]
        dimension=tpl["dimension"],  # type: ignore[arg-type]
        source=tpl["source"],
        source_type=tpl["source_type"],  # type: ignore[arg-type]
        description=tpl["description"],
        feature_keys=feature_keys,
        status=tpl.get("status", "planned"),  # type: ignore[arg-type]
        terminal_visible=cfg["terminal_visible"],
        required_for_scoring=bool(tpl.get("required_for_scoring", False)),
        sla_days=int(tpl.get("sla_days", 7)),
        default_confidence=float(tpl.get("default_confidence", 0.75)),
        circuit_breaker_source=tpl.get("circuit_breaker_source"),
        priority=int(tpl.get("priority", 3)),
        metadata={"espn_slug": cfg["espn_slug"], **tpl.get("metadata", {})},
    )


def _from_explicit(entry: dict) -> ScraperDefinition:
    sport = entry["sport"]
    if sport == "*":
        league_tier = "college"
        terminal_visible = True
        feature_keys = tuple(entry["feature_keys"])
    else:
        cfg = SPORTS[sport]
        league_tier = cfg["league_tier"]
        terminal_visible = cfg["terminal_visible"]
        feature_keys = filter_feature_keys_for_league(tuple(entry["feature_keys"]), league_tier)

    return ScraperDefinition(
        scraper_key=entry["scraper_key"],
        display_name=entry["display_name"],
        sport=sport,
        league_tier=league_tier,  # type: ignore[arg-type]
        dimension=entry["dimension"],  # type: ignore[arg-type]
        source=entry["source"],
        source_type=entry["source_type"],  # type: ignore[arg-type]
        description=entry["description"],
        feature_keys=feature_keys,
        status=entry.get("status", "planned"),  # type: ignore[arg-type]
        terminal_visible=terminal_visible if sport != "*" else True,
        required_for_scoring=bool(entry.get("required_for_scoring", False)),
        sla_days=int(entry.get("sla_days", 7)),
        default_confidence=float(entry.get("default_confidence", 0.75)),
        circuit_breaker_source=entry.get("circuit_breaker_source"),
        priority=int(entry.get("priority", 3)),
        metadata=dict(entry.get("metadata", {})),
    )


def build_registry() -> list[ScraperDefinition]:
    """Materialize every scraper definition (templates × sports + shared + specific)."""
    out: list[ScraperDefinition] = []
    seen: set[str] = set()

    def add(defn: ScraperDefinition) -> None:
        if defn.scraper_key in seen:
            return
        seen.add(defn.scraper_key)
        out.append(defn)

    for sport, groups in SPORT_TEMPLATE_GROUPS.items():
        for group_name in groups:
            for tpl in TEMPLATE_GROUPS[group_name]:
                if group_name == "achievements" and sport not in ACHIEVEMENT_SPORTS:
                    continue
                add(_expand_template(sport, tpl))

    for entry in SPORT_SPECIFIC:
        add(_from_explicit(entry))

    for entry in SHARED_SCRAPERS:
        add(_from_explicit(entry))

    return sorted(out, key=lambda d: (d.sport, d.priority, d.scraper_key))


def registry_by_key() -> dict[str, ScraperDefinition]:
    return {d.scraper_key: d for d in build_registry()}


def scrapers_for_event(event_type: str, sport: str = "cfb") -> list[str]:
    """Resolve scraper keys for pipeline events."""
    from gravity_api.scraper_registry.events import resolve_event_scraper_keys

    return resolve_event_scraper_keys(event_type, sport)


def scrapers_for_sport(
    sport: str,
    *,
    dimensions: list[str] | None = None,
    terminal_only: bool = False,
) -> list[ScraperDefinition]:
    reg = build_registry()
    filtered = [d for d in reg if d.sport in (sport, "*")]
    if dimensions:
        filtered = [d for d in filtered if d.dimension in dimensions]
    if terminal_only:
        filtered = [d for d in filtered if d.terminal_visible or d.sport == "*"]
    return filtered
