"""Per-sport scraper acceptance criteria for sample QA runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gravity_api.scraper_registry.field_sufficiency import is_sufficient
from gravity_api.scraper_registry.sports import SPORTS
from gravity_api.services.team_conferences import normalize_conference_display
from gravity_api.scrapers.parsers.stat_catalog import all_stat_keys_for_sport

# Instagram is optional — users may upload handles/followers manually.
OPTIONAL_FIELDS = frozenset(
    {
        "instagram_handle",
        "instagram_followers",
        "instagram_engagement_rate",
        "tiktok_handle",
        "tiktok_followers",
        "twitter_handle",
        "twitter_followers",
        "youtube_subscribers",
    }
)

SHARED_REQUIRED = (
    "espn_id",
    "position",
    "stats_as_of",
)

COLLEGE_REQUIRED = SHARED_REQUIRED + (
    "team",
    "games_played_season",
)

PRO_REQUIRED = SHARED_REQUIRED + (
    "team",
    "games_played_season",
)

# At least one market-value signal should be present when publicly available (not 100% coverage).
COLLEGE_VALUE_ANY = (
    "nil_valuation",
    "nil_deals",
    "nil_deal_count",
)

PRO_VALUE_ANY = (
    "contract_aav_usd",
    "contract_guaranteed_usd",
    "contract_total_usd",
    "endorsement_value_usd",
)


@dataclass
class FieldCheck:
    name: str
    passed: bool
    optional: bool
    detail: str = ""


@dataclass
class AthleteAcceptance:
    athlete_id: str
    name: str
    sport: str
    checks: list[FieldCheck] = field(default_factory=list)
    scraper_success: int = 0
    scraper_total: int = 0
    scraper_errors: list[str] = field(default_factory=list)

    @property
    def required_passed(self) -> bool:
        req = [c for c in self.checks if not c.optional]
        return bool(req) and all(c.passed for c in req)

    @property
    def value_signal_passed(self) -> bool:
        value_checks = [c for c in self.checks if c.name.startswith("value:")]
        return any(c.passed for c in value_checks) if value_checks else True


def _present(raw: dict[str, Any], key: str) -> bool:
    val = raw.get(key)
    if val is None or val == "":
        return False
    if isinstance(val, (list, dict)):
        return len(val) > 0
    if isinstance(val, (int, float)):
        return val > 0
    return bool(str(val).strip())


def _check_field(
    raw: dict[str, Any], key: str, *, sport: str = "", optional: bool = False
) -> FieldCheck:
    if key == "nil_deals":
        ok = _present(raw, "nil_deals") or _present(raw, "brand_deals")
        return FieldCheck(key, ok, optional, "deal list in raw" if ok else "no deals array")
    if key == "espn_id":
        ok = _present(raw, "espn_id") or _present(raw, "external_id_espn")
        return FieldCheck(key, ok, optional, "" if ok else "missing espn id")
    if key == "team":
        ok = _present(raw, "team") or _present(raw, "player_name")
        return FieldCheck(key, ok, optional, "" if ok else "missing team")
    if key == "games_played_season":
        season = raw.get("season_stats") or {}
        ok = (
            _present(raw, "games_played_season")
            or _present(raw, "gp")
            or (isinstance(season, dict) and (_present(season, "games_played_season") or _present(season, "gp")))
        )
        if not ok and isinstance(season, dict) and sport:
            stat_keys = all_stat_keys_for_sport(sport) - {"games_played_season", "gp"}
            ok = sum(1 for k in stat_keys if _as_positive(season.get(k))) >= 1
        return FieldCheck(key, ok, optional, "" if ok else "missing games_played_season")
    if key in ("instagram_handle", "instagram_followers", "nil_valuation"):
        ok = is_sufficient(raw, key) if key != "nil_deals" else _present(raw, key)
        return FieldCheck(key, ok, optional, "" if ok else f"insufficient {key}")
    if key.startswith("contract_") or key == "endorsement_value_usd":
        ok = _as_positive(raw.get(key)) or _as_positive(raw.get(key.replace("_usd", "")))
        return FieldCheck(key, ok, optional, "" if ok else f"missing {key}")
    ok = _present(raw, key)
    return FieldCheck(key, ok, optional, "" if ok else f"missing {key}")


def _as_positive(val: Any) -> bool:
    try:
        return float(val) > 0
    except (TypeError, ValueError):
        return False


_STAT_COUNT_SKIP = frozenset({"gp", "games_played", "games_played_season", "stats_as_of"})


def _positive_season_stat_count(season: dict[str, Any]) -> int:
    return sum(
        1
        for k, v in season.items()
        if k not in _STAT_COUNT_SKIP and _as_positive(v)
    )


def _position_stat_count(raw: dict[str, Any], sport: str) -> int:
    keys = all_stat_keys_for_sport(sport)
    season = raw.get("season_stats") or {}
    if isinstance(season, dict):
        catalog_n = sum(
            1 for k in keys if _as_positive(season.get(k)) or _as_positive(raw.get(k))
        )
        return max(catalog_n, _positive_season_stat_count(season))
    return sum(1 for k in keys if _as_positive(raw.get(k)))


def evaluate_athlete_acceptance(
    *,
    athlete_id: str,
    name: str,
    sport: str,
    raw: dict[str, Any],
    conference: str | None = None,
    scrape_summary: dict[str, Any] | None = None,
    min_position_stats: int | None = None,
) -> AthleteAcceptance:
    league = SPORTS.get(sport, {}).get("league_tier", "college")
    required = COLLEGE_REQUIRED if league == "college" else PRO_REQUIRED
    value_any = COLLEGE_VALUE_ANY if league == "college" else PRO_VALUE_ANY
    if min_position_stats is None:
        min_position_stats = 2 if sport == "nfl" else 3

    out = AthleteAcceptance( athlete_id=athlete_id, name=name, sport=sport)

    for key in required:
        out.checks.append(_check_field(raw, key, sport=sport, optional=False))

    conf_norm = normalize_conference_display(conference)
    conf_ok = bool(conf_norm and conf_norm.strip().lower() not in {"", "conference"})
    out.checks.append(
        FieldCheck(
            "conference",
            conf_ok,
            optional=False,
            detail="" if conf_ok else "missing or placeholder conference",
        )
    )

    stat_n = _position_stat_count(raw, sport)
    out.checks.append(
        FieldCheck(
            "position_stats_min",
            stat_n >= min_position_stats,
            optional=False,
            detail=f"{stat_n} stats (>={min_position_stats})",
        )
    )

    for key in OPTIONAL_FIELDS:
        out.checks.append(_check_field(raw, key, sport=sport, optional=True))

    value_hits = []
    for key in value_any:
        chk = _check_field(raw, key, sport=sport, optional=True)
        chk.name = f"value:{key}"
        out.checks.append(chk)
        if chk.passed:
            value_hits.append(key)
    if not value_hits:
        out.checks.append(
            FieldCheck(
                "value:any_market_signal",
                False,
                optional=True,
                detail="no NIL/contract/endorsement signal (may be normal for depth players)",
            )
        )
    else:
        out.checks.append(
            FieldCheck(
                "value:any_market_signal",
                True,
                optional=True,
                detail=f"via {','.join(value_hits)}",
            )
        )

    if scrape_summary:
        results = scrape_summary.get("results") or []
        out.scraper_total = len(results)
        out.scraper_success = sum(
            1 for r in results if r.get("status") in ("success", "partial", "skipped")
        )
        for r in results:
            if r.get("status") not in ("success", "skipped", "partial"):
                err = r.get("error") or r.get("error_message") or r.get("status")
                out.scraper_errors.append(f"{r.get('scraper_key')}: {err}")

    return out


def sport_pass_thresholds(league_tier: str) -> dict[str, float]:
    return {
        "required_field_rate": 0.90,
        "optional_ig_rate": 0.0,  # informational only
        "value_signal_rate": 0.10 if league_tier == "college" else 0.15,
        "scraper_success_rate": 0.70,
    }


# Scrapers that affect required acceptance fields (excludes CFBD, tiktok, extended Firecrawl).
ACCEPTANCE_SCRAPER_SUFFIXES: tuple[str, ...] = (
    "espn_roster",
    "espn_stats",
    "stats_freshness",
    "identity_consensus",
    "injury_structured",
    "social_handle_discovery",
    "instagram_followers",
    "espn_awards",
    "all_american",
    "conference_honors",
    "national_awards",
)


# Pro contract scrapers for value-signal coverage in acceptance.
PRO_ACCEPTANCE_EXTRA_SUFFIXES: tuple[str, ...] = (
    "spotrac_contract",
    "forbes_earnings",
)

COLLEGE_ACCEPTANCE_EXTRA_SUFFIXES: tuple[str, ...] = (
    "on3_nil",
    "nil_deal_verified",
)


def resolve_acceptance_scraper_keys(sport: str) -> list[str]:
    """Minimal scraper set for Phase A gates — avoids optional-platform failures."""
    from gravity_api.scraper_registry.build import registry_by_key

    keys_map = registry_by_key()
    league = SPORTS.get(sport, {}).get("league_tier", "college")
    out: list[str] = []
    suffixes = list(ACCEPTANCE_SCRAPER_SUFFIXES)
    if sport in {"nfl", "nba", "wnba"}:
        suffixes.extend(PRO_ACCEPTANCE_EXTRA_SUFFIXES)
    elif league == "college":
        suffixes.extend(COLLEGE_ACCEPTANCE_EXTRA_SUFFIXES)
    for suffix in suffixes:
        key = f"{suffix}_{sport}"
        if key in keys_map:
            out.append(key)
    return out
