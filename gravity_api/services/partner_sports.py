"""Partner API sport catalog and filter normalization (all Gravity sports)."""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

import asyncpg

from gravity_api.scraper_registry.sports import SPORTS

# Partner-facing codes (use in `sports=CFB,NBA` query param).
PARTNER_CODE_TO_DB_SLUGS: dict[str, list[str]] = {
    "CFB": ["cfb"],
    "NCAAB": ["ncaab_mens", "mcbb"],
    "NCAAW": ["ncaab_womens", "wcbb"],
    "NCAA_BASEBALL": ["ncaa_baseball"],
    "NCAA_VOLLEYBALL": ["ncaa_volleyball"],
    "NFL": ["nfl"],
    "NBA": ["nba"],
    "WNBA": ["wnba"],
}

_LEGACY_SLUG_ALIASES: dict[str, str] = {
    "mcbb": "ncaab_mens",
    "wcbb": "ncaab_womens",
}

_DB_SLUG_TO_PARTNER_CODE: dict[str, str] = {}
for _code, _slugs in PARTNER_CODE_TO_DB_SLUGS.items():
    for _slug in _slugs:
        _DB_SLUG_TO_PARTNER_CODE[_slug] = _code


def normalize_db_sport_slug(raw: str) -> str:
    s = raw.strip().lower()
    return _LEGACY_SLUG_ALIASES.get(s, s)


def partner_code_for_db_slug(slug: str) -> str | None:
    return _DB_SLUG_TO_PARTNER_CODE.get(slug) or _DB_SLUG_TO_PARTNER_CODE.get(
        normalize_db_sport_slug(slug)
    )


def partner_codes_to_db_slugs(values: List[str]) -> List[str]:
    """Map partner codes (`CFB`, `NBA`) or db slugs (`cfb`, `nba`) to DB slug list."""
    out: List[str] = []
    for raw in values:
        token = raw.strip()
        if not token:
            continue
        upper = token.upper()
        if upper in PARTNER_CODE_TO_DB_SLUGS:
            for slug in PARTNER_CODE_TO_DB_SLUGS[upper]:
                if slug not in out:
                    out.append(slug)
            continue
        slug = normalize_db_sport_slug(token)
        known = set(SPORTS.keys()) | set(_LEGACY_SLUG_ALIASES.keys())
        if slug in known or slug in _DB_SLUG_TO_PARTNER_CODE:
            if slug not in out:
                out.append(slug)
    return out


def resolve_sport_filters(
    sport: Optional[str],
    sports: Optional[str],
) -> Tuple[Optional[str], Optional[List[str]]]:
    """Return `(single_sport, sports_db)` for athlete search."""
    if sports and sports.strip():
        slugs = partner_codes_to_db_slugs([s.strip() for s in sports.split(",") if s.strip()])
        if slugs:
            return None, slugs
    if sport and sport.strip():
        slugs = partner_codes_to_db_slugs([sport])
        if len(slugs) == 1:
            return slugs[0], None
        if len(slugs) > 1:
            return None, slugs
    return None, None


def catalog_entry_for_slug(slug: str) -> dict[str, Any]:
    meta = SPORTS.get(slug) or SPORTS.get(normalize_db_sport_slug(slug))
    code = partner_code_for_db_slug(slug)
    if meta:
        return {
            "sport": slug,
            "code": code,
            "display_name": meta["display_name"],
            "league_tier": meta["league_tier"],
            "terminal_visible": meta["terminal_visible"],
        }
    return {
        "sport": slug,
        "code": code,
        "display_name": slug.replace("_", " ").title(),
        "league_tier": "unknown",
        "terminal_visible": False,
    }


async def fetch_partner_sport_catalog(db: asyncpg.Connection) -> dict[str, Any]:
    """All sports with live DB counts merged with platform catalog."""
    rows = await db.fetch(
        """SELECT a.sport,
                  COUNT(*)::int AS athlete_count,
                  COUNT(DISTINCT s.athlete_id)::int AS scored_athlete_count
           FROM athletes a
           LEFT JOIN (
               SELECT DISTINCT athlete_id FROM athlete_gravity_scores
           ) s ON s.athlete_id = a.id
           WHERE a.is_active IS TRUE
           GROUP BY a.sport
           ORDER BY a.sport"""
    )
    by_slug: dict[str, dict[str, Any]] = {}
    for row in rows:
        slug = str(row["sport"])
        entry = catalog_entry_for_slug(slug)
        entry["athlete_count"] = int(row["athlete_count"])
        entry["scored_athlete_count"] = int(row["scored_athlete_count"])
        by_slug[slug] = entry

    sports_out: list[dict[str, Any]] = []
    for slug in sorted(SPORTS.keys()):
        if slug in by_slug:
            sports_out.append(by_slug[slug])
        else:
            entry = catalog_entry_for_slug(slug)
            entry["athlete_count"] = 0
            entry["scored_athlete_count"] = 0
            sports_out.append(entry)

    for slug, entry in sorted(by_slug.items()):
        if slug not in SPORTS and slug not in _LEGACY_SLUG_ALIASES:
            sports_out.append(entry)

    codes = [
        {
            "code": code,
            "db_slugs": slugs,
            "display_name": catalog_entry_for_slug(slugs[0])["display_name"],
        }
        for code, slugs in sorted(PARTNER_CODE_TO_DB_SLUGS.items())
    ]

    return {
        "sports": sports_out,
        "codes": codes,
        "filter_help": {
            "sport": "Single filter: db slug (cfb, nba) or partner code (CFB, NBA)",
            "sports": "Multi filter: comma-separated codes or slugs, e.g. CFB,NBA,WNBA",
        },
    }
