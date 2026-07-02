"""Gap-fill scrape mode — run only scrapers needed for missing or low-quality fields."""

from __future__ import annotations

from typing import Any

from gravity_api.scraper_registry.build import registry_by_key
from gravity_api.scraper_registry.events import resolve_event_scraper_keys
from gravity_api.scraper_registry.types import ScraperDefinition
from gravity_api.scraper_registry.field_sufficiency import insufficient_fields, is_sufficient
from gravity_api.scrapers.types import AthleteScrapeContext

# Scraper execution order (dependencies: handles → followers → engagement → NIL → stats → awards).
SCRAPER_PRIORITY: tuple[str, ...] = (
    "social_handle_discovery",
    "espn_roster",
    "identity_consensus",
    "instagram_followers",
    "tiktok_followers",
    "twitter_followers",
    "social_engagement_instagram",
    "social_engagement_tiktok",
    "youtube_subscribers",
    "nil_deal_verified",
    "on3_nil",
    "opendorse_profile",
    "espn_stats",
    "cfbd_api_stats",
    "stats_freshness",
    "sports_ref_honors",
    "espn_awards",
    "all_american",
    "conference_honors",
    "national_awards",
    "championship_results",
    "google_trends_athlete",
    "wikipedia_pageviews",
    "news_rss",
    "social_growth_delta",
    "injury_structured",
    "ncaa_official_roster",
    "transfer_portal",
    "recruiting_247",
    "program_context",
)

# Fields prioritized for ML shipping (NIL labels, IG proxy, external quality).
ML_PRIORITY_FIELDS: tuple[str, ...] = (
    "instagram_handle",
    "instagram_followers",
    "instagram_engagement_rate",
    "nil_valuation",
    "external_quality_score",
    "all_american_count",
    "national_awards_count",
    "espn_id",
)


def _suffix_from_key(scraper_key: str, sport: str) -> str:
    suffix = f"_{sport}"
    if scraper_key.endswith(suffix):
        return scraper_key[: -len(suffix)]
    if scraper_key in SCRAPER_PRIORITY or scraper_key.startswith("news_rss"):
        return scraper_key
    parts = scraper_key.rsplit("_", 1)
    return parts[0] if len(parts) == 2 else scraper_key


def _priority_index(scraper_key: str, sport: str) -> int:
    suffix = _suffix_from_key(scraper_key, sport)
    for idx, name in enumerate(SCRAPER_PRIORITY):
        if suffix == name or suffix.startswith(name):
            return idx
    return len(SCRAPER_PRIORITY) + 1


def analyze_field_gaps(
    raw: dict[str, Any],
    *,
    fields: tuple[str, ...] | None = None,
    include_stats: bool = False,
) -> list[str]:
    """Return field names that are missing or insufficient."""
    check = fields or ML_PRIORITY_FIELDS
    gaps = insufficient_fields(raw, check)
    if is_sufficient(raw, "external_quality_score"):
        gaps = [g for g in gaps if g not in {
            "external_quality_score", "all_american_count", "national_awards_count",
        }]
    if include_stats and not is_sufficient(raw, "stats_as_of"):
        if not raw.get("season_stats") and not raw.get("json_stat_passing_yards"):
            gaps.append("season_stats")
    return gaps


def scrapers_for_gaps(
    gaps: list[str],
    sport: str,
    *,
    include_extended: bool = False,
) -> list[str]:
    """Map insufficient fields → scraper keys via registry feature_keys."""
    if not gaps:
        return []

    gap_set = set(gaps)
    keys_map = registry_by_key()
    candidates: list[str] = []

    for key, defn in keys_map.items():
        if defn.sport not in (sport, "*") and not key.endswith(f"_{sport}"):
            if defn.sport != sport and sport not in key:
                continue
        if defn.status == "stub":
            continue
        if defn.sport != sport and not (key.endswith(f"_{sport}") or key in {
            "news_rss_on3",
            "social_growth_delta",
            "program_context",
        }):
            continue
        feature_overlap = [fk for fk in defn.feature_keys if fk in gap_set]
        # Award scrapers fill quality-related gaps
        if "external_quality_score" in gap_set and defn.dimension == "achievements":
            feature_overlap.append("external_quality_score")
        if "season_stats" in gap_set and any(
            fk.startswith("json_stat_") or "stats" in fk for fk in defn.feature_keys
        ):
            feature_overlap.append("season_stats")
        if feature_overlap:
            candidates.append(key)

    # Fallback: known scrapers for common gaps
    fallback: dict[str, list[str]] = {
        "instagram_handle": [f"social_handle_discovery_{sport}"],
        "instagram_followers": [f"instagram_followers_{sport}", f"social_handle_discovery_{sport}"],
        "instagram_engagement_rate": [f"social_engagement_instagram_{sport}"],
        "nil_valuation": [f"nil_deal_verified_{sport}", f"on3_nil_{sport}", f"opendorse_profile_{sport}"],
        "external_quality_score": [
            f"espn_awards_{sport}",
            f"sports_ref_honors_{sport}",
            f"all_american_{sport}",
            f"national_awards_{sport}",
        ],
        "season_stats": [f"espn_stats_{sport}", "cfbd_api_stats_cfb"],
    }
    for gap in gaps:
        for key in fallback.get(gap, []):
            if key in keys_map and key not in candidates:
                candidates.append(key)

    if include_extended:
        for key in resolve_event_scraper_keys("scheduled_extended", sport, include_extended=True):
            if key not in candidates:
                # Only add extended scrapers if they might fill a gap
                defn = keys_map.get(key)
                if defn and any(g in defn.feature_keys or g in gap_set for g in gaps):
                    candidates.append(key)

    candidates = [k for k in candidates if k in keys_map]
    candidates.sort(key=lambda k: _priority_index(k, sport))
    return list(dict.fromkeys(candidates))


def resolve_gap_fill_scraper_keys(
    ctx: AthleteScrapeContext,
    *,
    include_extended: bool = False,
    fields: tuple[str, ...] | None = None,
) -> list[str]:
    """Return ordered scraper keys to run for this athlete's data gaps only."""
    from gravity_api.scrapers.parsers.handle_discovery import is_user_provided_instagram

    gaps = analyze_field_gaps(ctx.existing_raw, fields=fields)
    if is_user_provided_instagram(ctx.existing_raw) and ctx.existing_raw.get("instagram_handle"):
        gaps = [g for g in gaps if g not in {"instagram_handle"}]
    if not gaps:
        return []
    return scrapers_for_gaps(gaps, ctx.sport, include_extended=include_extended)


def gap_fill_summary(ctx: AthleteScrapeContext) -> dict[str, Any]:
    gaps = analyze_field_gaps(ctx.existing_raw)
    keys = scrapers_for_gaps(gaps, ctx.sport)
    return {
        "athlete_id": ctx.athlete_id,
        "sport": ctx.sport,
        "gaps": gaps,
        "scraper_keys": keys,
        "scraper_count": len(keys),
    }
