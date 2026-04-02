"""Power 5 CFB / MCBB roster ingestion via ESPN site API."""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

POWER_5_CFB_TEAMS = {
    "SEC": [
        "alabama",
        "georgia",
        "lsu",
        "tennessee",
        "texas",
        "oklahoma",
        "florida",
        "auburn",
        "arkansas",
        "mississippi-state",
        "ole-miss",
        "south-carolina",
        "vanderbilt",
        "kentucky",
        "missouri",
        "texas-am",
    ],
    "Big Ten": [
        "michigan",
        "ohio-state",
        "penn-state",
        "iowa",
        "minnesota",
        "wisconsin",
        "indiana",
        "illinois",
        "maryland",
        "michigan-state",
        "nebraska",
        "northwestern",
        "purdue",
        "rutgers",
        "ucla",
        "usc",
        "washington",
        "oregon",
    ],
    "Big 12": [
        "kansas-state",
        "texas-tech",
        "baylor",
        "tcu",
        "iowa-state",
        "west-virginia",
        "cincinnati",
        "houston",
        "byu",
        "ucf",
        "colorado",
        "arizona",
        "arizona-state",
        "utah",
    ],
    "ACC": [
        "clemson",
        "florida-state",
        "miami",
        "north-carolina",
        "duke",
        "nc-state",
        "virginia",
        "virginia-tech",
        "wake-forest",
        "georgia-tech",
        "pitt",
        "boston-college",
        "louisville",
        "syracuse",
    ],
}

POWER_5_MCBB_TEAMS = {
    "SEC": [
        "kentucky",
        "alabama",
        "tennessee",
        "arkansas",
        "florida",
        "auburn",
        "lsu",
        "mississippi-state",
        "georgia",
        "texas",
        "oklahoma",
        "texas-am",
        "south-carolina",
        "vanderbilt",
        "ole-miss",
        "missouri",
    ],
    "Big Ten": [
        "michigan-state",
        "indiana",
        "illinois",
        "purdue",
        "michigan",
        "ohio-state",
        "iowa",
        "minnesota",
        "northwestern",
        "nebraska",
        "penn-state",
        "rutgers",
        "wisconsin",
        "maryland",
        "ucla",
        "usc",
        "washington",
        "oregon",
    ],
    "Big 12": [
        "kansas",
        "baylor",
        "tcu",
        "texas-tech",
        "iowa-state",
        "west-virginia",
        "cincinnati",
        "houston",
        "byu",
        "ucf",
        "colorado",
        "arizona",
        "arizona-state",
        "utah",
    ],
    "ACC": [
        "duke",
        "north-carolina",
        "virginia",
        "clemson",
        "florida-state",
        "miami",
        "nc-state",
        "virginia-tech",
        "wake-forest",
        "georgia-tech",
        "pitt",
        "boston-college",
        "louisville",
        "syracuse",
    ],
}


def _roster_url(school_slug: str, sport_key: str) -> str:
    if sport_key == "cfb":
        return (
            "https://site.api.espn.com/apis/site/v2/sports/football/"
            f"college-football/teams/{school_slug}/roster"
        )
    return (
        "https://site.api.espn.com/apis/site/v2/sports/basketball/"
        f"mens-college-basketball/teams/{school_slug}/roster"
    )


async def fetch_espn_roster(
    school_slug: str,
    sport_key: str,
    client: httpx.AsyncClient,
) -> List[Dict[str, Any]]:
    url = _roster_url(school_slug, sport_key)
    try:
        resp = await client.get(url, timeout=15.0)
        if resp.status_code != 200:
            logger.warning("ESPN %s (%s): status %s", school_slug, sport_key, resp.status_code)
            return []
        data = resp.json()
        athletes: List[Dict[str, Any]] = []
        for group in data.get("athletes", []) or []:
            for player in group.get("items", []) or []:
                pos = player.get("position") or {}
                abbrev = pos.get("abbreviation") if isinstance(pos, dict) else None
                athletes.append(
                    {
                        "name": player.get("fullName", ""),
                        "position": abbrev,
                        "jersey_number": str(player.get("jersey") or "")
                        if player.get("jersey") is not None
                        else None,
                        "height_inches": _parse_height(player.get("displayHeight")),
                        "weight_lbs": player.get("weight"),
                        "year": player.get("experience", {}).get("years")
                        if isinstance(player.get("experience"), dict)
                        else player.get("year"),
                        "espn_id": str(player.get("id", "")),
                        "photo_url": (player.get("headshot") or {}).get("href")
                        if isinstance(player.get("headshot"), dict)
                        else None,
                    }
                )
        return athletes
    except Exception as e:
        logger.error("ESPN fetch failed for %s: %s", school_slug, e)
        return []


def _parse_height(display: Optional[str]) -> int:
    if not display:
        return 0
    try:
        cleaned = display.replace('"', "").replace("'", "-")
        if "-" in cleaned:
            parts = cleaned.split("-")
            ft = int(re.sub(r"[^\d]", "", parts[0]) or 0)
            inches = int(re.sub(r"[^\d]", "", parts[1]) or 0)
            return ft * 12 + inches
    except Exception:
        pass
    return 0


def _eligibility_year(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    s = str(raw).strip().lower()
    m = re.search(r"(\d+)", s)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    year_map = {
        "fr": 1,
        "freshman": 1,
        "so": 2,
        "sophomore": 2,
        "jr": 3,
        "junior": 3,
        "sr": 4,
        "senior": 4,
    }
    return year_map.get(s[:2]) or year_map.get(s)


def _get_position_group(position: Optional[str], sport: str) -> str:
    if sport == "cfb":
        groups = {
            "QB": "skill",
            "RB": "skill",
            "WR": "skill",
            "TE": "skill",
            "OL": "offensive_line",
            "OT": "offensive_line",
            "OG": "offensive_line",
            "C": "offensive_line",
            "DL": "defensive_line",
            "DE": "defensive_line",
            "DT": "defensive_line",
            "LB": "linebacker",
            "ILB": "linebacker",
            "OLB": "linebacker",
            "CB": "defensive_back",
            "S": "defensive_back",
            "FS": "defensive_back",
            "SS": "defensive_back",
            "K": "specialist",
            "P": "specialist",
        }
    else:
        groups = {
            "PG": "guard",
            "SG": "guard",
            "SF": "forward",
            "PF": "forward",
            "C": "center",
        }
    return groups.get(position or "", "other")


async def ingest_power5_rosters(db: Any, sport: str = "cfb") -> None:
    """Ingest all Power 5 rosters for CFB or MCBB."""
    teams_by_conf = POWER_5_CFB_TEAMS if sport == "cfb" else POWER_5_MCBB_TEAMS
    sport_key = "cfb" if sport == "cfb" else "mcbb"

    async with httpx.AsyncClient(headers={"User-Agent": "GravityNIL/1.0"}) as client:
        for conference, teams in teams_by_conf.items():
            for school_slug in teams:
                logger.info("Fetching %s roster: %s", sport, school_slug)
                players = await fetch_espn_roster(school_slug, sport_key, client)
                display_school = school_slug.replace("-", " ").title()

                for player in players:
                    if not player.get("name"):
                        continue
                    elig = _eligibility_year(player.get("year"))
                    await db.execute(
                        """
                        INSERT INTO athletes
                          (name, sport, school, conference, position,
                           position_group, eligibility_year,
                           height_inches, weight_lbs, jersey_number,
                           espn_id, photo_url)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                        ON CONFLICT (name, school, sport)
                        DO UPDATE SET
                          position = EXCLUDED.position,
                          position_group = EXCLUDED.position_group,
                          height_inches = EXCLUDED.height_inches,
                          weight_lbs = EXCLUDED.weight_lbs,
                          jersey_number = EXCLUDED.jersey_number,
                          espn_id = EXCLUDED.espn_id,
                          photo_url = EXCLUDED.photo_url,
                          updated_at = NOW()
                        """,
                        player["name"],
                        sport_key,
                        display_school,
                        conference,
                        player.get("position"),
                        _get_position_group(player.get("position"), sport_key),
                        elig,
                        player.get("height_inches") or 0,
                        player.get("weight_lbs"),
                        player.get("jersey_number"),
                        player.get("espn_id"),
                        player.get("photo_url"),
                    )

                await asyncio.sleep(0.5)

    logger.info("Power 5 %s roster ingestion complete", sport)
