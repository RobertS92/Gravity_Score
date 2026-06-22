"""ESPN public API client — roster, stats, awards, injuries."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from gravity_api.scraper_registry.sports import SPORTS

logger = logging.getLogger(__name__)

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


def normalize_sport(sport: str) -> str:
    s = sport.lower().strip()
    if s == "mcbb":
        return "ncaab_mens"
    if s == "wcbb":
        return "ncaab_womens"
    return s


class EspnClient:
    def __init__(self, *, timeout_s: float = 30.0):
        self.timeout_s = timeout_s

    async def _get(self, url: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_s, headers=ESPN_HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code == 404:
                return {}
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, dict) else {}

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
        team_lower = (team or "").lower()
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
        # Fallback: common v3 athletes search
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

    async def get_athlete_profile(self, athlete_id: str, sport: str) -> dict[str, Any]:
        sport = normalize_sport(sport)
        league = SITE_LEAGUE_PATH.get(sport)
        if not league:
            return {}
        url = f"https://site.api.espn.com/apis/common/v3/sports/{league}/athletes/{athlete_id}"
        data = await self._get(url)
        athlete = data.get("athlete") or data
        identity: dict[str, Any] = {
            "player_name": athlete.get("displayName") or athlete.get("fullName"),
            "position": (athlete.get("position") or {}).get("abbreviation"),
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
            injuries.append(
                {
                    "type": (inj.get("type") or {}).get("description"),
                    "status": (inj.get("status") or {}).get("description"),
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

    async def get_season_stats(self, athlete_id: str, sport: str) -> dict[str, Any]:
        sport = normalize_sport(sport)
        league = SITE_LEAGUE_PATH.get(sport)
        if not league:
            return {}
        url = (
            f"https://site.api.espn.com/apis/common/v3/sports/{league}/athletes/"
            f"{athlete_id}/stats"
        )
        data = await self._get(url)
        splits = data.get("splits") or {}
        categories = splits.get("categories") or data.get("categories") or []
        season_stats: dict[str, Any] = {}
        for cat in categories:
            for stat in cat.get("stats") or []:
                key = stat.get("name") or stat.get("abbreviation")
                val = stat.get("value") or stat.get("displayValue")
                if key:
                    season_stats[str(key)] = val
        return {
            "season_stats": season_stats,
            "stats_as_of": data.get("season") or data.get("displaySeason"),
            "stats_source": "espn",
            "raw": data,
        }

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
        return {
            "college_career_found": True,
            "college_sport_scraped": college_sport,
            "college_espn_id": athlete_id,
            "college_identity": profile.get("identity") or {},
            "college_stats": stats.get("season_stats") or {},
            "college_awards": profile.get("awards") or [],
            "college_achievements_json": profile.get("awards") or [],
        }
