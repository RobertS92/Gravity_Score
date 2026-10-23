"""ESPN public API client — roster, stats, awards, injuries."""

from __future__ import annotations

import contextvars
import logging
import os
import re
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_SEASON_YEAR_IN_URL = re.compile(r"/seasons/(\d+)")
_SEASON_TYPE_IN_URL = re.compile(r"/types/(\d+)/")
_TEAM_ID_IN_URL = re.compile(r"/teams/(\d+)")
_ESPN_TYPE_TO_SEASON = {2: "regular", 3: "postseason"}
TOT_TEAM_ID = "TOT"

_espn_get_cache: contextvars.ContextVar[dict[str, dict[str, Any]] | None] = (
    contextvars.ContextVar("_espn_get_cache", default=None)
)


def begin_espn_cache() -> None:
    """Start in-memory GET dedup for the current athlete scrape run."""
    _espn_get_cache.set({})


def clear_espn_cache() -> None:
    _espn_get_cache.set(None)


def _espn_nested_description(value: Any) -> str | None:
    if isinstance(value, dict):
        desc = value.get("description") or value.get("name") or value.get("displayName")
        return str(desc) if desc else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


ESPN_HEADERS = {
    "User-Agent": "GravityScrapers/1.0",
    "Accept": "application/json",
}

# site.api.espn.com currently 403s from this environment; site.web.api serves
# the same site/v2 roster payloads.
ESPN_SITE_HOST = os.getenv("ESPN_SITE_API_HOST", "site.web.api.espn.com").strip() or "site.web.api.espn.com"

def site_v2_url(path: str) -> str:
    """Build a site/v2 URL on the host that currently serves ESPN public JSON."""
    return f"https://{ESPN_SITE_HOST}/apis/site/v2/{path.lstrip('/')}"


# site.api.espn.com league path segments
SITE_LEAGUE_PATH: dict[str, str] = {
    "cfb": "football/college-football",
    "ncaab_mens": "basketball/mens-college-basketball",
    "mcbb": "basketball/mens-college-basketball",
    "ncaab_womens": "basketball/womens-college-basketball",
    "wcbb": "basketball/womens-college-basketball",
    "ncaa_baseball": "baseball/college-baseball",
    "ncaa_volleyball": "volleyball/womens-college-volleyball",
    "nfl": "football/nfl",
    "nba": "basketball/nba",
    "wnba": "basketball/wnba",
}

CORE_LEAGUE_PATH: dict[str, str] = {
    "cfb": "football/leagues/college-football",
    "ncaab_mens": "basketball/leagues/mens-college-basketball",
    "mcbb": "basketball/leagues/mens-college-basketball",
    "ncaab_womens": "basketball/leagues/womens-college-basketball",
    "wcbb": "basketball/leagues/womens-college-basketball",
    "ncaa_baseball": "baseball/leagues/college-baseball",
    "ncaa_volleyball": "volleyball/leagues/womens-college-volleyball",
    "nfl": "football/leagues/nfl",
    "nba": "basketball/leagues/nba",
    "wnba": "basketball/leagues/wnba",
}

# common v3 athlete endpoints often 500 for these sports — prefer core API first.
CORE_PROFILE_FIRST_SPORTS = frozenset({"ncaa_baseball", "ncaa_volleyball"})


def normalize_sport(sport: str) -> str:
    s = sport.lower().strip()
    aliases = {
        "mcbb": "ncaab_mens",
        "wcbb": "ncaab_womens",
        "ncaab": "ncaab_mens",
        "ncaaf": "cfb",
    }
    return aliases.get(s, s)


def _team_ref_url(team_field: Any) -> str | None:
    if isinstance(team_field, dict):
        ref = team_field.get("$ref") or team_field.get("href")
        if ref:
            return str(ref).replace("http://", "https://")
        name = team_field.get("displayName") or team_field.get("name")
        return None if name is None else None
    return None


def _profile_from_core_athlete(athlete: dict[str, Any], athlete_id: str) -> dict[str, Any]:
    pos = athlete.get("position") or {}
    team_field = athlete.get("team")
    team_name = None
    if isinstance(team_field, dict):
        team_name = team_field.get("displayName") or team_field.get("name")
    identity: dict[str, Any] = {
        "player_name": athlete.get("displayName") or athlete.get("fullName"),
        "position": pos.get("abbreviation") if isinstance(pos, dict) else pos,
        "jersey_number": athlete.get("jersey"),
        "team": team_name,
        "college": None,
        "headshot_url": (athlete.get("headshot") or {}).get("href")
        if isinstance(athlete.get("headshot"), dict)
        else athlete.get("headshot"),
        "espn_id": athlete_id,
    }
    if isinstance(team_field, dict) and team_field.get("$ref") and not team_name:
        identity["_team_ref"] = str(team_field["$ref"]).replace("http://", "https://")
    exp = athlete.get("experience")
    if isinstance(exp, dict):
        identity["class_year"] = exp.get("displayValue")
    elif isinstance(exp, str):
        identity["class_year"] = exp
    if athlete.get("height") is not None:
        identity["height_inches"] = athlete.get("height")
    if athlete.get("weight") is not None:
        identity["weight_lbs"] = athlete.get("weight")
    return identity


def _stats_from_core_payload(data: dict[str, Any]) -> dict[str, Any]:
    from gravity_api.scrapers.parsers.espn_stats import stats_from_espn_payload

    return stats_from_espn_payload(data)


def _https_ref(url: str | None) -> str | None:
    if not url:
        return None
    return str(url).replace("http://", "https://")


def _strip_capture(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not isinstance(data, dict):
        return {}, None
    capture = data.get("_capture")
    if isinstance(capture, dict):
        clean = {k: v for k, v in data.items() if k != "_capture"}
        return clean, capture
    return data, None


def _parse_http_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_espn_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return _parse_http_date(text)


class EspnClient:
    def __init__(self, *, timeout_s: float = 30.0):
        self.timeout_s = timeout_s
        self._last_fetch_meta: dict[str, Any] = {}

    def _record_fetch_meta(
        self,
        url: str,
        *,
        date_header: str | None = None,
        last_modified: str | None = None,
        capture: dict[str, Any] | None = None,
        fetched_at: datetime | None = None,
    ) -> None:
        cap = capture or {}
        self._last_fetch_meta = {
            "url": url,
            "date": date_header or cap.get("date"),
            "last_modified": last_modified or cap.get("last-modified") or cap.get("last_modified"),
            "fetched_at": fetched_at or datetime.now(tz=timezone.utc),
        }

    async def _get(self, url: str, *, allow_empty: bool = True) -> dict[str, Any]:
        cache = _espn_get_cache.get()
        if cache is not None and url in cache:
            cached = dict(cache[url])
            clean, capture = _strip_capture(cached)
            self._record_fetch_meta(url, capture=capture)
            return clean

        async with httpx.AsyncClient(timeout=self.timeout_s, headers=ESPN_HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code in (400, 403, 404, 500, 502, 503):
                # Do not cache empty error bodies — a transient 5xx would poison
                # parallel roster/stats/awards scrapers for the whole athlete run.
                logger.debug("ESPN GET %s returned %s (not cached)", url, resp.status_code)
                self._record_fetch_meta(
                    url,
                    date_header=resp.headers.get("Date"),
                    last_modified=resp.headers.get("Last-Modified"),
                )
                return {}
            resp.raise_for_status()
            raw = resp.json()
            data = raw if isinstance(raw, dict) else {}
            clean, capture = _strip_capture(data)
            self._record_fetch_meta(
                url,
                date_header=resp.headers.get("Date"),
                last_modified=resp.headers.get("Last-Modified"),
                capture=capture,
            )

        if cache is not None and clean:
            cache[url] = dict(clean)
        return clean

    async def _get_core(self, sport: str, path: str) -> dict[str, Any]:
        sport = normalize_sport(sport)
        league = CORE_LEAGUE_PATH.get(sport)
        if not league:
            return {}
        url = f"https://sports.core.api.espn.com/v2/sports/{league}/{path.lstrip('/')}"
        data = await self._get(url)
        if data.get("error"):
            return {}
        return data

    async def search_athlete(
        self, name: str, sport: str, *, team: str | None = None
    ) -> str | None:
        sport = normalize_sport(sport)
        league = SITE_LEAGUE_PATH.get(sport)
        if not league:
            return None
        q = name.replace(" ", "+")
        # site.api.espn.com 403s from many cloud egress IPs; use ESPN_SITE_HOST.
        url = (
            f"https://{ESPN_SITE_HOST}/apis/common/v3/search"
            f"?query={q}&limit=10&type=player"
        )
        data = await self._get(url)
        items = data.get("results") or []
        name_lower = name.lower()
        for bucket in items:
            for entry in bucket.get("contents") or []:
                if entry.get("type") != "player":
                    continue
                display = str(entry.get("displayName") or entry.get("name") or "")
                if name_lower not in display.lower():
                    continue
                uid = str(entry.get("uid") or "")
                if "~" in uid:
                    return uid.split("~")[-1]
                link = str(entry.get("link") or entry.get("href") or "")
                if "/id/" in link:
                    return link.split("/id/")[-1].split("/")[0]
        search_url = (
            f"https://{ESPN_SITE_HOST}/apis/common/v3/sports/{league}/athletes"
            f"?search={q}&limit=5"
        )
        alt = await self._get(search_url)
        for item in alt.get("items") or alt.get("athletes") or []:
            display = str(item.get("displayName") or item.get("fullName") or "")
            if name_lower in display.lower():
                return str(item.get("id") or "")
        return None

    async def _get_athlete_profile_site(
        self, athlete_id: str, sport: str
    ) -> dict[str, Any]:
        sport = normalize_sport(sport)
        league = SITE_LEAGUE_PATH.get(sport)
        if not league:
            return {}
        url = (
            f"https://{ESPN_SITE_HOST}/apis/common/v3/sports/{league}/athletes/"
            f"{athlete_id}"
        )
        data = await self._get(url)
        athlete = data.get("athlete") or data
        if not athlete or not isinstance(athlete, dict):
            return {}
        identity: dict[str, Any] = {
            "player_name": athlete.get("displayName") or athlete.get("fullName"),
            "position": (athlete.get("position") or {}).get("abbreviation")
            if isinstance(athlete.get("position"), dict)
            else athlete.get("position"),
            "jersey_number": athlete.get("jersey"),
            "team": (athlete.get("team") or {}).get("displayName"),
            "college": (athlete.get("college") or {}).get("name")
            or (athlete.get("team") or {}).get("displayName"),
            "headshot_url": (athlete.get("headshot") or {}).get("href"),
            "espn_id": athlete_id,
        }
        exp = athlete.get("experience")
        if isinstance(exp, dict):
            identity["class_year"] = exp.get("displayValue")
        links = athlete.get("links") or []
        for link in links:
            href = str(link.get("href") or "")
            rel = str(link.get("rel") or link.get("text") or "").lower()
            if "instagram" in href or "instagram" in rel:
                identity["instagram_profile_url"] = href
            if "twitter" in href or "x.com" in href:
                identity["twitter_profile_url"] = href
            if "tiktok" in href:
                identity["tiktok_profile_url"] = href
        injuries = []
        for inj in athlete.get("injuries") or []:
            if not isinstance(inj, dict):
                continue
            injuries.append(
                {
                    "type": _espn_nested_description(inj.get("type")),
                    "status": _espn_nested_description(inj.get("status")),
                    "date": inj.get("date"),
                }
            )
        awards = []
        for aw in athlete.get("awards") or []:
            awards.append(
                {
                    "name": aw.get("name") or aw.get("displayName"),
                    "season": aw.get("season"),
                    "type": aw.get("type"),
                }
            )
        return {
            "identity": identity,
            "injuries": injuries,
            "awards": awards,
            "raw": athlete,
        }

    async def _resolve_team_display_name(self, team_ref: str) -> str | None:
        data = await self._get(team_ref)
        if not data:
            return None
        return (
            data.get("displayName")
            or data.get("name")
            or data.get("shortDisplayName")
        )

    async def _get_athlete_profile_core(
        self, athlete_id: str, sport: str
    ) -> dict[str, Any]:
        athlete = await self._get_core(sport, f"athletes/{athlete_id}")
        if not athlete:
            return {}
        identity = _profile_from_core_athlete(athlete, athlete_id)
        team_ref = identity.pop("_team_ref", None)
        if team_ref and not identity.get("team"):
            team_name = await self._resolve_team_display_name(team_ref)
            if team_name:
                identity["team"] = team_name
                if not identity.get("college"):
                    identity["college"] = team_name
        return {
            "identity": identity,
            "injuries": [],
            "awards": [],
            "raw": athlete,
        }

    async def get_athlete_profile(self, athlete_id: str, sport: str) -> dict[str, Any]:
        sport = normalize_sport(sport)
        # Prefer site.web profile — it embeds team.displayName; core only has $ref.
        if sport in CORE_PROFILE_FIRST_SPORTS:
            profile = await self._get_athlete_profile_core(athlete_id, sport)
            if profile.get("identity", {}).get("player_name"):
                if not profile["identity"].get("team"):
                    site = await self._get_athlete_profile_site(athlete_id, sport)
                    if site.get("identity", {}).get("team"):
                        profile["identity"]["team"] = site["identity"]["team"]
                        profile["identity"].setdefault(
                            "college", site["identity"].get("college")
                        )
                return profile
            site = await self._get_athlete_profile_site(athlete_id, sport)
            return site if site else profile

        profile = await self._get_athlete_profile_site(athlete_id, sport)
        if profile.get("identity", {}).get("player_name"):
            return profile
        return await self._get_athlete_profile_core(athlete_id, sport)

    def _pack_stats_response(
        self, data: dict[str, Any], *, stats_source: str, sport: str | None = None
    ) -> dict[str, Any]:
        from gravity_api.scrapers.parsers.espn_stats import build_stats_bundle

        if not data:
            return {}
        bundle = build_stats_bundle(data, sport=sport)
        current = bundle.get("current") or {}
        if not current and not bundle.get("history"):
            return {}
        return {
            "season_stats": current,
            "season_stats_history": bundle.get("history") or {},
            "career_stats": bundle.get("career") or {},
            "stats_as_of": bundle.get("stats_as_of"),
            "stats_scope": bundle.get("stats_scope"),
            "stats_source": stats_source,
            "raw": data,
        }

    async def _get_season_stats_site(self, athlete_id: str, sport: str) -> dict[str, Any]:
        sport = normalize_sport(sport)
        league = SITE_LEAGUE_PATH.get(sport)
        if not league:
            return {}
        url = (
            f"https://{ESPN_SITE_HOST}/apis/common/v3/sports/{league}/athletes/"
            f"{athlete_id}/stats"
        )
        data = await self._get(url)
        return self._pack_stats_response(data, stats_source="espn", sport=sport)

    async def _get_career_stats_unscoped(
        self, athlete_id: str, sport: str
    ) -> dict[str, Any]:
        """Unscoped core ``athletes/{id}/statistics`` — career cross-check only (B1)."""
        data = await self._get_core(sport, f"athletes/{athlete_id}/statistics")
        if not data:
            return {}
        from gravity_api.scrapers.parsers.espn_stats import stats_from_espn_payload

        return {
            "career_stats": stats_from_espn_payload(data),
            "stats_source": "espn_core_career",
            "raw": data,
        }

    async def _get_season_stats_core_year(
        self, athlete_id: str, sport: str, year: str | int, *, season_type: int = 2
    ) -> dict[str, Any]:
        """Per-season core statistics (includes TFL that career aggregates zero out)."""
        data = await self._fetch_core_season_statistics(
            athlete_id, sport, int(year), season_type=int(season_type)
        )
        packed = self._pack_stats_response(
            data, stats_source="espn_core_season", sport=sport
        )
        if packed.get("season_stats"):
            packed["stats_scope"] = "season"
            packed["stats_as_of"] = await self.resolve_stats_as_of(
                sport, int(year), fetch_meta=self._last_fetch_meta
            )
        return packed

    @staticmethod
    def _merge_prefer_nonzero(
        base: dict[str, Any], overlay: dict[str, Any]
    ) -> dict[str, Any]:
        out = dict(base or {})
        for key, val in (overlay or {}).items():
            if val is None or val == "" or val == "-":
                continue
            cur = out.get(key)
            try:
                cur_empty = cur is None or float(cur) == 0.0
            except (TypeError, ValueError):
                cur_empty = cur in (None, "", "-")
            try:
                val_empty = float(val) == 0.0
            except (TypeError, ValueError):
                val_empty = False
            if key not in out or (cur_empty and not val_empty):
                out[key] = val
        return out

    async def get_season_stats(self, athlete_id: str, sport: str) -> dict[str, Any]:
        """Legacy packed stats for current pipeline callers.

        Never promotes unscoped core aggregates into ``season_stats`` (B1).
        Prefer ``get_season_stat_lines`` for season-correct history.
        """
        sport = normalize_sport(sport)

        # Prefer site common/v3 — per-season history. site.api 403s; site.web works.
        stats = await self._get_season_stats_site(athlete_id, sport)
        if not stats:
            stats = {
                "season_stats": {},
                "season_stats_history": {},
                "career_stats": {},
                "stats_as_of": None,
                "stats_scope": None,
                "stats_source": "espn",
                "raw": {},
            }

        # Enrich latest season from core year endpoint (TFL etc. missing on site CFB).
        history = stats.get("season_stats_history") or {}
        year_keys = sorted(
            (y for y in history.keys() if str(y).isdigit()),
            key=lambda y: int(y),
        )
        if year_keys and sport in {"cfb", "nfl", "ncaa_baseball", "ncaa_volleyball"}:
            latest_year = year_keys[-1]
            core_year = await self._get_season_stats_core_year(
                athlete_id, sport, latest_year
            )
            core_cur = core_year.get("season_stats") or {}
            if core_cur:
                stats["season_stats"] = self._merge_prefer_nonzero(
                    stats.get("season_stats") or {}, core_cur
                )
                hist_row = dict(history.get(latest_year) or {})
                history[latest_year] = self._merge_prefer_nonzero(hist_row, core_cur)
                stats["season_stats_history"] = history
                stats["stats_as_of"] = core_year.get("stats_as_of")
                stats["stats_scope"] = "season"
        elif stats.get("season_stats") and not stats.get("stats_scope"):
            from gravity_api.scrapers.parsers.espn_stats import infer_stats_scope

            stats["stats_scope"] = infer_stats_scope(
                history=stats.get("season_stats_history"),
                career=stats.get("career_stats"),
                current=stats.get("season_stats"),
                sport=sport,
            )
        return stats

    # --- WP3: season-scoped SeasonStatLine API ---------------------------------

    @staticmethod
    def _season_type_from_espn_code(code: int | str) -> str | None:
        try:
            return _ESPN_TYPE_TO_SEASON.get(int(code))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _year_from_espn_ref(ref: str) -> int | None:
        m = _SEASON_YEAR_IN_URL.search(ref or "")
        return int(m.group(1)) if m else None

    @staticmethod
    def _stype_from_espn_ref(ref: str) -> str | None:
        m = _SEASON_TYPE_IN_URL.search(ref or "")
        if not m:
            return None
        return EspnClient._season_type_from_espn_code(m.group(1))

    @staticmethod
    def _team_id_from_espn_ref(ref: str) -> str | None:
        m = _TEAM_ID_IN_URL.search(ref or "")
        return m.group(1) if m else None

    async def list_stat_seasons(
        self, athlete_id: str, league: str
    ) -> list[tuple[int, str, str]]:
        """Enumerate ``(season_year, season_type, stats_ref)`` from statisticslog.

        Prefers ``type=total`` refs when both total and team blocks exist for the
        same (year, season_type).
        """
        league = normalize_sport(league)
        data = await self._get_core(league, f"athletes/{athlete_id}/statisticslog")
        entries = data.get("entries") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            return []

        chosen: dict[tuple[int, str], tuple[str, int]] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            season_obj = entry.get("season") or {}
            season_ref = ""
            if isinstance(season_obj, dict):
                season_ref = str(season_obj.get("$ref") or "")
            year = self._year_from_espn_ref(season_ref)
            for block in entry.get("statistics") or []:
                if not isinstance(block, dict):
                    continue
                stats_obj = block.get("statistics") or {}
                stats_ref = ""
                if isinstance(stats_obj, dict):
                    stats_ref = _https_ref(str(stats_obj.get("$ref") or "")) or ""
                if not stats_ref:
                    continue
                block_year = self._year_from_espn_ref(stats_ref) or year
                season_type = self._stype_from_espn_ref(stats_ref)
                if block_year is None or season_type is None:
                    continue
                # Prefer total over team for the index entry.
                priority = 0 if str(block.get("type") or "").lower() == "total" else 1
                key = (int(block_year), season_type)
                prev = chosen.get(key)
                if prev is None or priority < prev[1]:
                    chosen[key] = (stats_ref, priority)

        out = [
            (year, stype, ref)
            for (year, stype), (ref, _) in chosen.items()
        ]
        out.sort(key=lambda row: (row[0], 0 if row[1] == "regular" else 1, row[2]))
        return out

    async def resolve_stats_as_of(
        self,
        league: str,
        season_year: int,
        *,
        on: date | None = None,
        fetch_meta: dict[str, Any] | None = None,
    ) -> datetime:
        """Timestamp provenance for a season row (never a season label).

        Completed seasons → league ``seasons/{y}.endDate`` (or window end).
        In-progress / future → HTTP Date / Last-Modified / fetch time.
        """
        from gravity_api.scrapers.season_calendar import season_status, season_window

        league = normalize_sport(league)
        on_d = on or date.today()
        status = season_status(league, int(season_year), on_d)
        if status == "complete":
            season_doc = await self._get_core(league, f"seasons/{int(season_year)}")
            end = _parse_espn_timestamp(
                (season_doc or {}).get("endDate")
                or ((season_doc or {}).get("type") or {}).get("endDate")
            )
            if end is not None:
                return end
            _, end_d = season_window(league, int(season_year))
            return datetime(end_d.year, end_d.month, end_d.day, tzinfo=timezone.utc)

        meta = fetch_meta if fetch_meta is not None else self._last_fetch_meta
        for key in ("last_modified", "date"):
            parsed = _parse_http_date(str(meta.get(key) or "") or None)
            if parsed is not None:
                return parsed
        fetched = meta.get("fetched_at")
        if isinstance(fetched, datetime):
            return fetched if fetched.tzinfo else fetched.replace(tzinfo=timezone.utc)
        return datetime.now(tz=timezone.utc)

    async def _fetch_v3_stats(
        self, athlete_id: str, league: str, *, season_type_code: int | None = None
    ) -> tuple[dict[str, Any], str]:
        league = normalize_sport(league)
        site = SITE_LEAGUE_PATH.get(league)
        if not site:
            return {}, ""
        base = (
            f"https://{ESPN_SITE_HOST}/apis/common/v3/sports/{site}/athletes/"
            f"{athlete_id}/stats"
        )
        if season_type_code is not None:
            data = await self._get(f"{base}?seasontype={int(season_type_code)}")
            if data:
                return data, base
        data = await self._get(base)
        return data or {}, base

    async def _fetch_core_season_statistics(
        self,
        athlete_id: str,
        league: str,
        season_year: int,
        *,
        season_type: int = 2,
        team_id: str | None = None,
    ) -> dict[str, Any]:
        league = normalize_sport(league)
        y, t = int(season_year), int(season_type)
        paths: list[str] = []
        if team_id and team_id != TOT_TEAM_ID:
            paths.append(
                f"seasons/{y}/types/{t}/teams/{team_id}/athletes/{athlete_id}/statistics"
            )
            paths.append(
                f"seasons/{y}/types/{t}/teams/{team_id}/athletes/{athlete_id}/statistics/0"
            )
        paths.extend(
            [
                f"seasons/{y}/types/{t}/athletes/{athlete_id}/statistics",
                f"seasons/{y}/types/{t}/athletes/{athlete_id}/statistics/0",
            ]
        )
        for path in paths:
            data = await self._get_core(league, path)
            if data and (
                data.get("splits") or data.get("categories") or data.get("season")
            ):
                return data
        return {}

    def _core_statistics_url(
        self,
        league: str,
        athlete_id: str,
        season_year: int,
        *,
        season_type: int = 2,
        team_id: str | None = None,
    ) -> str:
        league = normalize_sport(league)
        core = CORE_LEAGUE_PATH.get(league, "")
        y, t = int(season_year), int(season_type)
        if team_id and team_id != TOT_TEAM_ID:
            path = (
                f"seasons/{y}/types/{t}/teams/{team_id}/athletes/{athlete_id}/statistics"
            )
        else:
            path = f"seasons/{y}/types/{t}/athletes/{athlete_id}/statistics/0"
        return f"https://sports.core.api.espn.com/v2/sports/{core}/{path}"

    async def resolve_season_team(
        self, athlete_id: str, league: str, season_year: int
    ) -> tuple[str | None, str | None]:
        """Return ``(team_id, team_name)`` from season-scoped athlete record."""
        league = normalize_sport(league)
        athlete = await self._get_core(
            league, f"seasons/{int(season_year)}/athletes/{athlete_id}"
        )
        if not athlete:
            return None, None
        team = athlete.get("team") or {}
        if not isinstance(team, dict):
            return None, None
        ref = _https_ref(str(team.get("$ref") or ""))
        team_id = self._team_id_from_espn_ref(ref or "") if ref else None
        if isinstance(team.get("id"), (str, int)):
            team_id = str(team.get("id"))
        team_name = team.get("displayName") or team.get("abbreviation") or team.get("name")
        if ref and (not team_name or not team_id):
            team_data = await self._get(ref)
            if team_data:
                team_id = (
                    str(team_data.get("id"))
                    if team_data.get("id") is not None
                    else team_id or self._team_id_from_espn_ref(ref)
                )
                team_name = (
                    team_data.get("abbreviation")
                    or team_data.get("shortDisplayName")
                    or team_data.get("displayName")
                    or team_name
                )
        return team_id, str(team_name) if team_name else None

    async def get_season_stat_lines(
        self,
        athlete_id: str,
        league: str,
        season_year: int,
        season_type: str,
    ) -> list["SeasonStatLine"]:
        """Season-scoped ``SeasonStatLine`` rows for one (year, type).

        Uses core season endpoints; resolves team; for mid-season trades uses
        common/v3 per-team rows (BKN+PHX+TOT). ``stats_as_of`` is never a label.
        """
        from gravity_api.scrapers.parsers.espn_stats import (
            parse_core_season_statistics,
            parse_v3_season_stat_lines,
        )
        from gravity_api.scrapers.types import SeasonStatLine

        league = normalize_sport(league)
        if season_type not in {"regular", "postseason"}:
            raise ValueError(
                f"season_type must be 'regular' or 'postseason', got {season_type!r}"
            )
        type_code = 2 if season_type == "regular" else 3
        year = int(season_year)

        v3_data, v3_url = await self._fetch_v3_stats(
            athlete_id, league, season_type_code=type_code
        )
        as_of = await self.resolve_stats_as_of(
            league, year, fetch_meta=self._last_fetch_meta
        )
        v3_lines = parse_v3_season_stat_lines(
            v3_data,
            league=league,
            season_year=year,
            season_type=season_type,
            source_url=v3_url or f"espn:v3:{league}:{athlete_id}",
            stats_as_of=as_of,
        )

        team_lines = [ln for ln in v3_lines if not ln.is_total]
        tot_lines = [ln for ln in v3_lines if ln.is_total]

        # Mid-season trade / multi-team: trust v3 splits (Durant 2023).
        if len(team_lines) >= 2:
            return sorted(
                team_lines + tot_lines,
                key=lambda ln: (0 if ln.is_total else 1, ln.team_id),
            )

        # Single-team (or unknown): prefer season-scoped core statistics.
        core = await self._fetch_core_season_statistics(
            athlete_id, league, year, season_type=type_code
        )
        core_url = self._core_statistics_url(
            league, athlete_id, year, season_type=type_code
        )
        as_of = await self.resolve_stats_as_of(
            league, year, fetch_meta=self._last_fetch_meta
        )

        team_id, team_name = await self.resolve_season_team(athlete_id, league, year)
        if team_id is None and team_lines:
            team_id = team_lines[0].team_id
            team_name = team_lines[0].team_name

        if core:
            return [
                parse_core_season_statistics(
                    core,
                    league=league,
                    season_year=year,
                    season_type=season_type,
                    team_id=TOT_TEAM_ID,
                    team_name=team_name,
                    is_total=True,
                    source_url=core_url,
                    stats_as_of=as_of,
                )
            ]

        if v3_lines:
            # Refresh timestamps after core/team fetches may have updated meta.
            return [
                SeasonStatLine(
                    league=ln.league,
                    season_year=ln.season_year,
                    season_type=ln.season_type,
                    team_id=ln.team_id,
                    team_name=ln.team_name,
                    is_total=ln.is_total,
                    stats=ln.stats,
                    source_key=ln.source_key,
                    source_url=ln.source_url,
                    stats_as_of=as_of,
                )
                for ln in v3_lines
            ]

        return []

    async def get_college_career_for_pro(
        self, name: str, college: str | None, pro_sport: str
    ) -> dict[str, Any]:
        """Fetch college ESPN profile for a pro athlete (predictive modeling inputs)."""
        college_sport = "cfb" if pro_sport == "nfl" else "ncaab_mens"
        if pro_sport == "wnba":
            college_sport = "ncaab_womens"
        athlete_id = await self.search_athlete(name, college_sport, team=college)
        if not athlete_id:
            return {"college_career_found": False}
        profile = await self.get_athlete_profile(athlete_id, college_sport)
        stats = await self.get_season_stats(athlete_id, college_sport)
        from gravity_api.scrapers.parsers.stat_normalizer import merge_stat_layers

        college_layers = merge_stat_layers(
            college_sport,
            current=stats.get("season_stats"),
            history=stats.get("season_stats_history"),
            career=stats.get("career_stats"),
        )
        return {
            "college_career_found": True,
            "college_sport_scraped": college_sport,
            "college_espn_id": athlete_id,
            "college_identity": profile.get("identity") or {},
            "college_stats": college_layers.get("season_stats") or stats.get("season_stats") or {},
            "college_stats_history": college_layers.get("season_stats_history")
            or stats.get("season_stats_history")
            or {},
            "college_career_stats": college_layers.get("career_stats")
            or stats.get("career_stats")
            or {},
            "college_stats_json": college_layers.get("season_stats") or {},
            "college_awards": profile.get("awards") or [],
            "college_achievements_json": profile.get("awards") or [],
        }

    def roster_url(self, sport: str, espn_team_id: str) -> str:
        sport = normalize_sport(sport)
        league = SITE_LEAGUE_PATH.get(sport)
        if not league:
            raise ValueError(f"Unsupported sport for roster: {sport}")
        return f"https://{ESPN_SITE_HOST}/apis/site/v2/sports/{league}/teams/{espn_team_id}/roster"

    def team_detail_url(self, sport: str, espn_team_id: str) -> str:
        sport = normalize_sport(sport)
        league = SITE_LEAGUE_PATH.get(sport)
        if not league:
            raise ValueError(f"Unsupported sport for team detail: {sport}")
        return f"https://{ESPN_SITE_HOST}/apis/site/v2/sports/{league}/teams/{espn_team_id}"

    async def fetch_roster_payload(self, sport: str, espn_team_id: str) -> dict[str, Any]:
        return await self._get(self.roster_url(sport, espn_team_id))

    async def fetch_team_detail(self, sport: str, espn_team_id: str) -> dict[str, Any]:
        return await self._get(self.team_detail_url(sport, espn_team_id))

    @staticmethod
    def flatten_roster_players(payload: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for bucket in payload.get("athletes") or []:
            if not isinstance(bucket, dict):
                continue
            items = bucket.get("items")
            if items is not None:
                for item in items:
                    if isinstance(item, dict):
                        out.append(item)
                continue
            if (
                bucket.get("id") is not None
                or bucket.get("displayName")
                or bucket.get("fullName")
            ):
                out.append(bucket)
        return out

    @staticmethod
    def roster_item_to_raw_fields(
        item: dict[str, Any],
        *,
        team_name: str,
        conference: str | None,
    ) -> dict[str, Any]:
        """Baseline scrape fields from ESPN roster payload (no profile API needed)."""
        display = item.get("fullName") or item.get("displayName") or ""
        pos = EspnClient.position_str(item)
        exp = item.get("experience") or {}
        class_year = str(exp.get("displayValue") or "") or None if isinstance(exp, dict) else None
        fields: dict[str, Any] = {
            "player_name": str(display).strip() or None,
            "espn_id": str(item.get("id")) if item.get("id") is not None else None,
            "position": pos or None,
            "team": team_name,
            "college": team_name,
            "conference": conference,
            "jersey_number": EspnClient.jersey_str(item),
            "class_year": class_year,
            "roster_seeded": True,
            "stats_source": "espn_roster",
            "is_on_roster": True,
        }
        if item.get("height") is not None:
            fields["height_inches"] = item.get("height")
        if item.get("weight") is not None:
            fields["weight_lbs"] = item.get("weight")
        bp = item.get("birthPlace") or {}
        if isinstance(bp, dict):
            city = bp.get("city")
            st = bp.get("state")
            if city or st:
                fields["hometown"] = ", ".join(p for p in (city, st) if p)
            if st:
                fields["home_state"] = str(st)
        return {k: v for k, v in fields.items() if v is not None and v != ""}

    @staticmethod
    def position_str(item: dict[str, Any]) -> str:
        pos = item.get("position")
        if isinstance(pos, dict):
            return str(pos.get("abbreviation") or pos.get("name") or "") or ""
        if isinstance(pos, str):
            return pos
        return ""

    @staticmethod
    def jersey_str(item: dict[str, Any]) -> str | None:
        jersey = item.get("jersey")
        if jersey is None:
            return None
        return str(jersey)

    @staticmethod
    def parse_team_conference(payload: dict[str, Any]) -> str | None:
        team = payload.get("team") or {}
        groups = team.get("groups") or {}
        if isinstance(groups, dict):
            parent = groups.get("parent") or {}
            if parent.get("name"):
                return str(parent["name"])
        standalone = team.get("standingSummary") or team.get("conference")
        if isinstance(standalone, str) and standalone.strip():
            return standalone.strip()
        return None

    async def resolve_team_id(self, sport: str, team_name: str) -> str | None:
        """Map a team display name to ESPN team id via the league teams list."""
        sport = normalize_sport(sport)
        league = SITE_LEAGUE_PATH.get(sport)
        if not league or not team_name:
            return None
        needle = " ".join(str(team_name).lower().split())
        url = f"https://{ESPN_SITE_HOST}/apis/site/v2/sports/{league}/teams?limit=100"
        data = await self._get(url)
        best: tuple[int, str] | None = None
        for block in data.get("sports") or []:
            for league_obj in block.get("leagues") or []:
                for wrap in league_obj.get("teams") or []:
                    team = wrap.get("team") or wrap
                    tid = str(team.get("id") or "").strip()
                    if not tid:
                        continue
                    candidates = [
                        str(team.get("displayName") or ""),
                        str(team.get("name") or ""),
                        str(team.get("shortDisplayName") or ""),
                        str(team.get("abbreviation") or ""),
                        str(team.get("nickname") or ""),
                        str(team.get("location") or ""),
                    ]
                    for cand in candidates:
                        norm = " ".join(cand.lower().split())
                        if not norm:
                            continue
                        if needle == norm:
                            return tid
                        if needle in norm or norm in needle:
                            score = min(len(needle), len(norm))
                            if best is None or score > best[0]:
                                best = (score, tid)
        return best[1] if best else None

    async def fetch_team_season_record(
        self,
        sport: str,
        *,
        season_year: int,
        team_name: str | None = None,
        espn_team_id: str | None = None,
        season_type: int | None = None,
    ) -> dict[str, Any] | None:
        """Fetch overall W-L from ESPN core team record endpoint.

        Returns ``{wins, losses, ties, win_pct, espn_team_id, summary}`` or None.
        """
        sport = normalize_sport(sport)
        league = CORE_LEAGUE_PATH.get(sport)
        if not league:
            return None
        tid = str(espn_team_id or "").strip() or None
        if not tid and team_name:
            tid = await self.resolve_team_id(sport, team_name)
        if not tid:
            return None

        # Prefer regular season. Football=2, basketball=2; try 2 then 3.
        type_candidates = [season_type] if season_type is not None else [2, 3]
        for stype in type_candidates:
            if stype is None:
                continue
            path = f"seasons/{int(season_year)}/types/{int(stype)}/teams/{tid}/record"
            data = await self._get_core(sport, path)
            items = data.get("items") if isinstance(data, dict) else None
            if not items:
                continue
            overall = None
            for item in items:
                if not isinstance(item, dict):
                    continue
                if str(item.get("name") or "").lower() == "overall" or str(
                    item.get("type") or ""
                ).lower() in {"total", "overall"}:
                    overall = item
                    break
            overall = overall or (items[0] if isinstance(items[0], dict) else None)
            if not overall:
                continue
            stats = {
                str(s.get("name")): s.get("value")
                for s in (overall.get("stats") or [])
                if isinstance(s, dict) and s.get("name")
            }
            wins = stats.get("wins")
            losses = stats.get("losses")
            ties = stats.get("ties") or stats.get("OTTies") or 0
            win_pct = stats.get("winPercent") or overall.get("value")
            if wins is None and losses is None:
                summary = str(overall.get("summary") or overall.get("displayValue") or "")
                if "-" in summary:
                    parts = summary.replace("–", "-").split("-")
                    try:
                        wins = float(parts[0])
                        losses = float(parts[1])
                    except (TypeError, ValueError, IndexError):
                        continue
            if wins is None or losses is None:
                continue
            w_i, l_i = int(float(wins)), int(float(losses))
            t_i = int(float(ties or 0))
            total = w_i + l_i + t_i
            pct = float(win_pct) if win_pct is not None else (w_i / total if total else None)
            return {
                "wins": w_i,
                "losses": l_i,
                "ties": t_i,
                "win_pct": round(pct, 4) if pct is not None else None,
                "espn_team_id": tid,
                "summary": str(overall.get("summary") or f"{w_i}-{l_i}"),
                "season_type": int(stype),
                "season_year": int(season_year),
            }
        return None
