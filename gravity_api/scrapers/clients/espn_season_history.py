"""Fetch per-season ESPN history rows for athlete_season_stats backfill.

Primary source: site.web common/v3 ``/athletes/{id}/stats`` (team splits + TOT).
Enrichment: core ``seasons/{year}/types/2/.../statistics`` (TFL / sacks).
Team identity: season-scoped ``seasons/{year}/athletes/{id}`` when needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from gravity_api.scrapers.clients.espn import (
    CORE_LEAGUE_PATH,
    ESPN_SITE_HOST,
    SITE_LEAGUE_PATH,
    EspnClient,
    normalize_sport,
)
from gravity_api.scrapers.parsers.espn_season_year import (
    espn_season_year,
    is_current_espn_season,
    season_label_for_espn_year,
)
from gravity_api.scrapers.parsers.espn_stats import (
    _merge_stat_dicts,
    _remap_category_keys,
    stats_from_espn_payload,
)
from gravity_api.scrapers.parsers.stat_normalizer import normalize_espn_stats

logger = logging.getLogger(__name__)

SEASON_TYPE_REGULAR = "regular"
SEASON_TYPE_POSTSEASON = "postseason"
_ESPN_TYPE_TO_SCOPE = {2: SEASON_TYPE_REGULAR, 3: SEASON_TYPE_POSTSEASON}
TOT_TEAM_ID = "TOT"


@dataclass
class SeasonStatRow:
    """One per-season (or mid-season team / TOT) row ready for persistence."""

    league: str
    sport: str
    espn_id: str
    season_label: str
    espn_season_year: int
    season_type: str
    team_id: str
    team_abbr: str | None
    games_played: int | None
    stats: dict[str, float]
    is_complete: bool
    is_total: bool
    stats_as_of: datetime
    source: str
    source_url: str
    collection_errors: list[str] = field(default_factory=list)
    raw_team_slug: str | None = None

    def counting_stats(self) -> dict[str, float]:
        """Return raw counts only (drop rate / average keys)."""
        out: dict[str, float] = {}
        rate_tokens = (
            "avg",
            "pct",
            "percent",
            "rate",
            "per_game",
            "pergame",
            "per_attempt",
            "per_carry",
            "per_catch",
            "yards_per",
            "passer_rating",
            "rating",
            "long",  # season-long max — not summable
        )
        for key, val in self.stats.items():
            kl = key.lower()
            if any(tok in kl for tok in rate_tokens):
                continue
            out[key] = val
        return out


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _parse_v3_row_stats(
    names: list[Any], values: list[Any], cat_name: str
) -> dict[str, Any]:
    if not names or not values or len(names) != len(values):
        return {}
    row = {str(names[i]): values[i] for i in range(len(names))}
    return _remap_category_keys(cat_name, row)


def _is_tot_row(team_id: Any, team_slug: str | None) -> bool:
    if team_id in (None, "", "null"):
        return True
    slug = (team_slug or "").lower()
    return "total" in slug or slug == "tot"


class EspnSeasonHistoryClient:
    """Build per-season rows for one athlete in one league."""

    def __init__(self, espn: EspnClient | None = None):
        self.espn = espn or EspnClient()

    async def fetch_season_rows(
        self,
        espn_id: str,
        sport: str,
        *,
        season_type: str = SEASON_TYPE_REGULAR,
        include_postseason: bool = False,
    ) -> list[SeasonStatRow]:
        sport = normalize_sport(sport)
        site = SITE_LEAGUE_PATH.get(sport)
        if not site:
            return []

        v3_url = (
            f"https://{ESPN_SITE_HOST}/apis/common/v3/sports/{site}/athletes/"
            f"{espn_id}/stats"
        )
        # Regular season is seasontype=2; postseason=3.
        type_code = 2 if season_type == SEASON_TYPE_REGULAR else 3
        data = await self.espn._get(f"{v3_url}?seasontype={type_code}")
        if not data:
            data = await self.espn._get(v3_url)
        if not data:
            return []

        rows = self._rows_from_v3(
            data,
            espn_id=espn_id,
            sport=sport,
            season_type=season_type,
            source_url=v3_url,
        )

        # Enrich each non-TOT row from core season stats (TFL / sacks).
        enriched: list[SeasonStatRow] = []
        for row in rows:
            if row.is_total:
                enriched.append(row)
                continue
            try:
                enriched.append(await self._enrich_from_core(row))
            except Exception as exc:  # noqa: BLE001 — provenance per row
                row.collection_errors.append(f"core_enrich:{exc}")
                enriched.append(row)

        if include_postseason and season_type == SEASON_TYPE_REGULAR:
            post = await self.fetch_season_rows(
                espn_id, sport, season_type=SEASON_TYPE_POSTSEASON
            )
            enriched.extend(post)

        return enriched

    def _rows_from_v3(
        self,
        data: dict[str, Any],
        *,
        espn_id: str,
        sport: str,
        season_type: str,
        source_url: str,
    ) -> list[SeasonStatRow]:
        teams_map = data.get("teams") if isinstance(data.get("teams"), dict) else {}
        # Merge all non-average categories (passing/rushing/defensive/totals…).
        # Averages alone lack counting GP on some sports; skip when anything else exists.
        categories = [
            c for c in (data.get("categories") or []) if isinstance(c, dict)
        ]
        non_avg = [
            c
            for c in categories
            if "average" not in str(c.get("name") or "").lower()
            and "average" not in str(c.get("displayName") or "").lower()
        ]
        cats = non_avg or categories

        # Keyed by (year, team_id_or_TOT, season_type)
        merged: dict[tuple[int, str, str], dict[str, Any]] = {}
        meta: dict[tuple[int, str, str], dict[str, Any]] = {}

        for cat in cats:
            cat_name = str(cat.get("name") or cat.get("displayName") or "")
            if (
                non_avg
                and "average" in cat_name.lower()
            ):
                continue
            names = cat.get("names") or cat.get("labels") or []
            if not isinstance(names, list):
                continue
            for srow in cat.get("statistics") or []:
                if not isinstance(srow, dict):
                    continue
                season = srow.get("season") or {}
                if not isinstance(season, dict):
                    continue
                display = str(season.get("displayName") or season.get("year") or "")
                year = espn_season_year(
                    season.get("year") or display, sport, fallback=None
                )
                try:
                    year = int(year)
                except (TypeError, ValueError):
                    continue
                team_id_raw = srow.get("teamId")
                slug = srow.get("teamSlug")
                is_total = _is_tot_row(team_id_raw, str(slug) if slug else None)
                team_id = TOT_TEAM_ID if is_total else str(team_id_raw)
                key = (year, team_id, season_type)
                raw_stats = _parse_v3_row_stats(
                    names, srow.get("stats") or [], cat_name
                )
                merged[key] = _merge_stat_dicts(merged.get(key, {}), raw_stats)
                team_abbr = None
                if not is_total and isinstance(slug, str) and slug in teams_map:
                    t = teams_map[slug]
                    if isinstance(t, dict):
                        team_abbr = t.get("abbreviation") or t.get("shortDisplayName")
                elif not is_total:
                    for t in teams_map.values():
                        if isinstance(t, dict) and str(t.get("id")) == team_id:
                            team_abbr = t.get("abbreviation")
                            break
                meta[key] = {
                    "season_label": display
                    or season_label_for_espn_year(year, sport),
                    "team_abbr": team_abbr,
                    "is_total": is_total,
                    "slug": slug,
                }

        now = _utcnow()
        out: list[SeasonStatRow] = []
        for (year, team_id, stype), raw in merged.items():
            info = meta.get((year, team_id, stype)) or {}
            normalized = normalize_espn_stats(sport, raw)
            gp = normalized.get("games_played_season") or normalized.get("gp")
            try:
                gp_i = int(gp) if gp is not None else None
            except (TypeError, ValueError):
                gp_i = None
            label = str(info.get("season_label") or season_label_for_espn_year(year, sport))
            complete = not is_current_espn_season(year, sport)
            out.append(
                SeasonStatRow(
                    league=sport,
                    sport=sport,
                    espn_id=str(espn_id),
                    season_label=label,
                    espn_season_year=year,
                    season_type=stype,
                    team_id=team_id,
                    team_abbr=info.get("team_abbr"),
                    games_played=gp_i,
                    stats={k: float(v) for k, v in normalized.items()},
                    is_complete=complete,
                    is_total=bool(info.get("is_total")),
                    stats_as_of=now,
                    source="espn_v3",
                    source_url=source_url,
                    raw_team_slug=str(info.get("slug") or "") or None,
                )
            )
        out.sort(key=lambda r: (r.espn_season_year, r.is_total, r.team_id))
        return out

    async def _enrich_from_core(self, row: SeasonStatRow) -> SeasonStatRow:
        sport = row.sport
        year = row.espn_season_year
        type_code = 2 if row.season_type == SEASON_TYPE_REGULAR else 3
        if row.team_id and row.team_id != TOT_TEAM_ID:
            path = (
                f"seasons/{year}/types/{type_code}/teams/{row.team_id}/"
                f"athletes/{row.espn_id}/statistics"
            )
        else:
            path = (
                f"seasons/{year}/types/{type_code}/athletes/{row.espn_id}/statistics/0"
            )
        data = await self.espn._get_core(sport, path)
        if not data:
            return row
        flat = stats_from_espn_payload(data)
        if not flat:
            return row
        normalized = normalize_espn_stats(sport, flat)
        merged = dict(row.stats)
        for key, val in normalized.items():
            cur = merged.get(key)
            if cur is None or cur == 0.0 and val != 0.0:
                merged[key] = float(val)
        gp = merged.get("games_played_season") or merged.get("gp") or row.games_played
        try:
            gp_i = int(gp) if gp is not None else row.games_played
        except (TypeError, ValueError):
            gp_i = row.games_played
        core_path = CORE_LEAGUE_PATH.get(sport, "")
        source_url = (
            f"https://sports.core.api.espn.com/v2/sports/{core_path}/{path}"
        )
        return SeasonStatRow(
            league=row.league,
            sport=row.sport,
            espn_id=row.espn_id,
            season_label=row.season_label,
            espn_season_year=row.espn_season_year,
            season_type=row.season_type,
            team_id=row.team_id,
            team_abbr=row.team_abbr,
            games_played=gp_i,
            stats=merged,
            is_complete=row.is_complete,
            is_total=row.is_total,
            stats_as_of=_utcnow(),
            source="espn_v3+core",
            source_url=source_url,
            collection_errors=list(row.collection_errors),
            raw_team_slug=row.raw_team_slug,
        )

    async def resolve_season_team(
        self, espn_id: str, sport: str, espn_year: int
    ) -> tuple[str | None, str | None]:
        """Return (team_id, team_abbr) from season-scoped athlete."""
        sport = normalize_sport(sport)
        athlete = await self.espn._get_core(
            sport, f"seasons/{int(espn_year)}/athletes/{espn_id}"
        )
        if not athlete:
            return None, None
        team = athlete.get("team") or {}
        ref = team.get("$ref") if isinstance(team, dict) else None
        if not ref:
            return None, team.get("abbreviation") if isinstance(team, dict) else None
        team_data = await self.espn._get(ref)
        if not team_data:
            tid = ref.split("/teams/")[-1].split("?")[0] if "/teams/" in ref else None
            return tid, None
        return (
            str(team_data.get("id")) if team_data.get("id") is not None else None,
            team_data.get("abbreviation") or team_data.get("shortDisplayName"),
        )


def derive_career_from_seasons(
    rows: list[SeasonStatRow],
) -> dict[str, float]:
    """SUM counting stats across non-total regular-season rows."""
    totals: dict[str, float] = {}
    for row in rows:
        if row.is_total:
            continue
        if row.season_type != SEASON_TYPE_REGULAR:
            continue
        for key, val in row.counting_stats().items():
            totals[key] = totals.get(key, 0.0) + float(val)
        if row.games_played:
            totals["games_played_career"] = totals.get("games_played_career", 0.0) + float(
                row.games_played
            )
    return totals


__all__ = [
    "EspnSeasonHistoryClient",
    "SEASON_TYPE_POSTSEASON",
    "SEASON_TYPE_REGULAR",
    "SeasonStatRow",
    "TOT_TEAM_ID",
    "derive_career_from_seasons",
]
