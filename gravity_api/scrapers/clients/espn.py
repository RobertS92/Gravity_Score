"""ESPN public API client — roster, stats, awards, injuries."""

from __future__ import annotations

import contextvars
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

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
    if s == "mcbb":
        return "ncaab_mens"
    if s == "wcbb":
        return "ncaab_womens"
    return s


def _profile_from_core_athlete(athlete: dict[str, Any], athlete_id: str) -> dict[str, Any]:
    pos = athlete.get("position") or {}
    identity: dict[str, Any] = {
        "player_name": athlete.get("displayName") or athlete.get("fullName"),
        "position": pos.get("abbreviation") if isinstance(pos, dict) else pos,
        "jersey_number": athlete.get("jersey"),
        "team": None,
        "college": None,
        "headshot_url": (athlete.get("headshot") or {}).get("href")
        if isinstance(athlete.get("headshot"), dict)
        else athlete.get("headshot"),
        "espn_id": athlete_id,
    }
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


class EspnClient:
    def __init__(self, *, timeout_s: float = 30.0):
        self.timeout_s = timeout_s

    async def _get(self, url: str, *, allow_empty: bool = True) -> dict[str, Any]:
        cache = _espn_get_cache.get()
        if cache is not None and url in cache:
            return dict(cache[url])

        async with httpx.AsyncClient(timeout=self.timeout_s, headers=ESPN_HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code in (400, 404, 500, 502, 503):
                data: dict[str, Any] = {}
            else:
                resp.raise_for_status()
                raw = resp.json()
                data = raw if isinstance(raw, dict) else {}

        if cache is not None:
            cache[url] = data
        return data

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
        url = f"https://site.api.espn.com/apis/common/v3/search?query={q}&limit=10&type=player"
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
            f"https://site.api.espn.com/apis/common/v3/sports/{league}/athletes"
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
        url = f"https://site.api.espn.com/apis/common/v3/sports/{league}/athletes/{athlete_id}"
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

    async def _get_athlete_profile_core(
        self, athlete_id: str, sport: str
    ) -> dict[str, Any]:
        athlete = await self._get_core(sport, f"athletes/{athlete_id}")
        if not athlete:
            return {}
        identity = _profile_from_core_athlete(athlete, athlete_id)
        return {
            "identity": identity,
            "injuries": [],
            "awards": [],
            "raw": athlete,
        }

    async def get_athlete_profile(self, athlete_id: str, sport: str) -> dict[str, Any]:
        sport = normalize_sport(sport)
        if sport in CORE_PROFILE_FIRST_SPORTS:
            profile = await self._get_athlete_profile_core(athlete_id, sport)
            if profile.get("identity", {}).get("player_name"):
                return profile
            site = await self._get_athlete_profile_site(athlete_id, sport)
            return site if site else profile

        profile = await self._get_athlete_profile_site(athlete_id, sport)
        if profile.get("identity", {}).get("player_name"):
            return profile
        return await self._get_athlete_profile_core(athlete_id, sport)

    def _pack_stats_response(
        self, data: dict[str, Any], *, stats_source: str
    ) -> dict[str, Any]:
        from gravity_api.scrapers.parsers.espn_stats import build_stats_bundle

        if not data:
            return {}
        bundle = build_stats_bundle(data)
        current = bundle.get("current") or {}
        if not current and not bundle.get("history"):
            return {}
        return {
            "season_stats": current,
            "season_stats_history": bundle.get("history") or {},
            "career_stats": bundle.get("career") or {},
            "stats_as_of": bundle.get("stats_as_of"),
            "stats_source": stats_source,
            "raw": data,
        }

    async def _get_season_stats_site(self, athlete_id: str, sport: str) -> dict[str, Any]:
        sport = normalize_sport(sport)
        league = SITE_LEAGUE_PATH.get(sport)
        if not league:
            return {}
        url = (
            f"https://site.api.espn.com/apis/common/v3/sports/{league}/athletes/"
            f"{athlete_id}/stats"
        )
        data = await self._get(url)
        return self._pack_stats_response(data, stats_source="espn")

    async def _get_season_stats_core(self, athlete_id: str, sport: str) -> dict[str, Any]:
        data = await self._get_core(sport, f"athletes/{athlete_id}/statistics")
        return self._pack_stats_response(data, stats_source="espn_core")

    async def get_season_stats(self, athlete_id: str, sport: str) -> dict[str, Any]:
        sport = normalize_sport(sport)
        if sport in CORE_PROFILE_FIRST_SPORTS:
            stats = await self._get_season_stats_core(athlete_id, sport)
            if stats.get("season_stats"):
                return stats
            site = await self._get_season_stats_site(athlete_id, sport)
            return site if site.get("season_stats") else stats

        stats = await self._get_season_stats_site(athlete_id, sport)
        if stats.get("season_stats"):
            return stats
        return await self._get_season_stats_core(athlete_id, sport)

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
        return f"https://site.api.espn.com/apis/site/v2/sports/{league}/teams/{espn_team_id}/roster"

    def team_detail_url(self, sport: str, espn_team_id: str) -> str:
        sport = normalize_sport(sport)
        league = SITE_LEAGUE_PATH.get(sport)
        if not league:
            raise ValueError(f"Unsupported sport for team detail: {sport}")
        return f"https://site.api.espn.com/apis/site/v2/sports/{league}/teams/{espn_team_id}"

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
        url = f"https://site.api.espn.com/apis/site/v2/sports/{league}/teams?limit=100"
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
