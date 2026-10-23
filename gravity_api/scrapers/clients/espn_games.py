"""ESPN game summary / box-score client (WP10).

Fetches site/v2 scoreboard listings, athlete eventlogs, and per-game summary
payloads used to populate ``games`` and ``game_player_box``. Smoke and the
backfill job share this client for live fetch/validate (no DB required for
parse checks).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from gravity_api.scrapers.clients.espn import (
    CORE_LEAGUE_PATH,
    ESPN_HEADERS,
    SITE_LEAGUE_PATH,
    normalize_sport,
    site_v2_url,
)

_EVENT_ID_RE = re.compile(r"/events/(\d+)")

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GameBoxPlayer:
    """One player's box line for a single game."""

    espn_athlete_id: str
    team_id: str | None
    started: bool | None = None
    minutes: float | None = None
    snaps: int | None = None
    stats: dict[str, Any] = field(default_factory=dict)
    display_name: str | None = None


@dataclass(frozen=True)
class GameSummary:
    """Normalized game header + optional player box rows."""

    game_id: str
    league: str
    season_year: int | None
    season_type: str
    start_time: datetime | None
    home_team_id: str | None
    away_team_id: str | None
    home_score: int | None
    away_score: int | None
    neutral_site: bool | None
    status: str | None
    source_url: str
    players: tuple[GameBoxPlayer, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)


def _parse_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _minutes_from_display(raw: Any) -> float | None:
    """Parse ESPN minute displays like ``32`` or ``32:15`` into decimal minutes."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    text = str(raw).strip()
    if not text or text in {"-", "--", "DNP"}:
        return None
    if ":" in text:
        parts = text.split(":", 1)
        try:
            return int(parts[0]) + int(parts[1]) / 60.0
        except (TypeError, ValueError):
            return None
    return _parse_float(text)


class EspnGamesClient:
    """HTTP client for ESPN game scoreboard + summary endpoints."""

    def __init__(self, *, timeout_s: float = 30.0):
        self.timeout_s = timeout_s

    def summary_url(self, league: str, game_id: str) -> str:
        sport = normalize_sport(league)
        path = SITE_LEAGUE_PATH.get(sport)
        if not path:
            raise ValueError(f"Unsupported league for ESPN games: {league}")
        return site_v2_url(f"sports/{path}/summary?event={game_id}")

    def scoreboard_url(
        self,
        league: str,
        *,
        dates: str | None = None,
        seasontype: int | None = None,
        week: int | None = None,
    ) -> str:
        sport = normalize_sport(league)
        path = SITE_LEAGUE_PATH.get(sport)
        if not path:
            raise ValueError(f"Unsupported league for ESPN games: {league}")
        params: list[str] = []
        if dates:
            params.append(f"dates={dates}")
        if seasontype is not None:
            params.append(f"seasontype={int(seasontype)}")
        if week is not None:
            params.append(f"week={int(week)}")
        qs = f"?{'&'.join(params)}" if params else ""
        return site_v2_url(f"sports/{path}/scoreboard{qs}")

    async def _get_json(self, url: str) -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=self.timeout_s,
            headers=ESPN_HEADERS,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, dict) else {}

    async def fetch_scoreboard(
        self,
        league: str,
        *,
        dates: str | None = None,
        seasontype: int | None = None,
        week: int | None = None,
    ) -> dict[str, Any]:
        """Fetch a scoreboard page (event list). Stub-friendly raw JSON."""
        url = self.scoreboard_url(
            league, dates=dates, seasontype=seasontype, week=week
        )
        return await self._get_json(url)

    async def fetch_game_summary(
        self,
        league: str,
        game_id: str,
    ) -> dict[str, Any]:
        """Fetch raw ESPN game summary JSON for ``game_id``."""
        url = self.summary_url(league, game_id)
        return await self._get_json(url)

    def parse_game_summary(
        self,
        league: str,
        game_id: str,
        payload: dict[str, Any],
        *,
        source_url: str | None = None,
    ) -> GameSummary:
        """Shape a summary payload into ``GameSummary`` (+ box rows when present).

        Box extraction covers the common basketball ``boxscore.players`` shape.
        Football snaps and fuller multi-category stats remain TODO for WP10
        completion once live fixtures are captured.
        """
        sport = normalize_sport(league)
        url = source_url or self.summary_url(sport, game_id)

        header = payload.get("header") if isinstance(payload.get("header"), dict) else {}
        competitions = header.get("competitions") if isinstance(header, dict) else None
        competition = (
            competitions[0]
            if isinstance(competitions, list) and competitions and isinstance(competitions[0], dict)
            else {}
        )
        competitors = competition.get("competitors") if isinstance(competition, dict) else None
        if not isinstance(competitors, list):
            competitors = []

        home_team_id = away_team_id = None
        home_score = away_score = None
        for comp in competitors:
            if not isinstance(comp, dict):
                continue
            team = comp.get("team") if isinstance(comp.get("team"), dict) else {}
            tid = str(team.get("id") or comp.get("id") or "") or None
            score = _parse_int(comp.get("score"))
            home_away = str(comp.get("homeAway") or "").lower()
            if home_away == "home":
                home_team_id, home_score = tid, score
            elif home_away == "away":
                away_team_id, away_score = tid, score

        status_block = competition.get("status") if isinstance(competition, dict) else {}
        status_type = (
            status_block.get("type") if isinstance(status_block, dict) else None
        )
        status = None
        if isinstance(status_type, dict):
            status = str(status_type.get("name") or status_type.get("state") or "") or None

        season_block = header.get("season") if isinstance(header.get("season"), dict) else {}
        season_year = _parse_int(season_block.get("year"))
        season_type_num = _parse_int(season_block.get("type"))
        season_type = "postseason" if season_type_num == 3 else "regular"

        start_raw = competition.get("date") or header.get("date")
        start_time: datetime | None = None
        if isinstance(start_raw, str) and start_raw.strip():
            try:
                start_time = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            except ValueError:
                start_time = None

        neutral = competition.get("neutralSite") if isinstance(competition, dict) else None
        if not isinstance(neutral, bool):
            neutral = None

        players = tuple(self._extract_box_players(payload))
        return GameSummary(
            game_id=str(game_id),
            league=sport,
            season_year=season_year,
            season_type=season_type,
            start_time=start_time,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            home_score=home_score,
            away_score=away_score,
            neutral_site=neutral,
            status=status,
            source_url=url,
            players=players,
            raw=payload,
        )

    def _extract_box_players(self, payload: dict[str, Any]) -> list[GameBoxPlayer]:
        box = payload.get("boxscore")
        if not isinstance(box, dict):
            return []
        players_block = box.get("players")
        if not isinstance(players_block, list):
            return []

        out: list[GameBoxPlayer] = []
        for team_block in players_block:
            if not isinstance(team_block, dict):
                continue
            team = team_block.get("team") if isinstance(team_block.get("team"), dict) else {}
            team_id = str(team.get("id") or "") or None
            statistics = team_block.get("statistics")
            if not isinstance(statistics, list):
                continue
            for stat_group in statistics:
                if not isinstance(stat_group, dict):
                    continue
                keys = [
                    str(k).lower()
                    for k in (stat_group.get("keys") or stat_group.get("names") or [])
                ]
                athletes = stat_group.get("athletes")
                if not isinstance(athletes, list):
                    continue
                for row in athletes:
                    if not isinstance(row, dict):
                        continue
                    athlete = row.get("athlete") if isinstance(row.get("athlete"), dict) else {}
                    espn_id = str(athlete.get("id") or row.get("id") or "")
                    if not espn_id:
                        continue
                    values = row.get("stats") if isinstance(row.get("stats"), list) else []
                    stats: dict[str, Any] = {}
                    for i, key in enumerate(keys):
                        if i < len(values):
                            stats[key] = values[i]
                    started = row.get("starter")
                    if not isinstance(started, bool):
                        started = None
                    minutes = None
                    for mk in ("min", "minutes", "minutesplayed"):
                        if mk in stats:
                            minutes = _minutes_from_display(stats.get(mk))
                            break
                    snaps = None
                    for sk in ("snaps", "defensive_snaps", "offensive_snaps"):
                        if sk in stats:
                            snaps = _parse_int(stats.get(sk))
                            break
                    out.append(
                        GameBoxPlayer(
                            espn_athlete_id=espn_id,
                            team_id=team_id,
                            started=started,
                            minutes=minutes,
                            snaps=snaps,
                            stats=stats,
                            display_name=str(
                                athlete.get("displayName") or athlete.get("shortName") or ""
                            )
                            or None,
                        )
                    )
        return out

    async def fetch_parsed_game(
        self,
        league: str,
        game_id: str,
    ) -> GameSummary:
        """Fetch + parse a single game summary into ``GameSummary``."""
        url = self.summary_url(league, game_id)
        payload = await self.fetch_game_summary(league, game_id)
        return self.parse_game_summary(league, game_id, payload, source_url=url)

    def eventlog_url(self, league: str, athlete_id: str, season_year: int) -> str:
        sport = normalize_sport(league)
        core = CORE_LEAGUE_PATH.get(sport)
        if not core:
            raise ValueError(f"Unsupported league for ESPN eventlog: {league}")
        return (
            f"https://sports.core.api.espn.com/v2/sports/{core}/"
            f"seasons/{int(season_year)}/athletes/{athlete_id}/eventlog"
        )

    async def fetch_athlete_eventlog(
        self,
        league: str,
        athlete_id: str,
        season_year: int,
    ) -> dict[str, Any]:
        """Fetch core athlete eventlog for one season (game id source for smoke)."""
        url = self.eventlog_url(league, athlete_id, season_year)
        return await self._get_json(url)

    @staticmethod
    def parse_eventlog_game_ids(
        payload: dict[str, Any],
        *,
        played_only: bool = True,
        limit: int | None = None,
    ) -> list[str]:
        """Extract ESPN event ids from an athlete eventlog payload."""
        events = payload.get("events") if isinstance(payload, dict) else None
        items: list[Any] = []
        if isinstance(events, dict):
            raw_items = events.get("items")
            if isinstance(raw_items, list):
                items = raw_items
        elif isinstance(events, list):
            items = events

        out: list[str] = []
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            played = item.get("played")
            if played_only and played is False and "statistics" not in item:
                continue
            if played_only and played is False:
                continue
            event = item.get("event") if isinstance(item.get("event"), dict) else {}
            ref = str(event.get("$ref") or item.get("$ref") or "")
            match = _EVENT_ID_RE.search(ref)
            if not match:
                continue
            gid = match.group(1)
            if gid in seen:
                continue
            seen.add(gid)
            out.append(gid)
            if limit is not None and len(out) >= int(limit):
                break
        return out

    async def list_athlete_game_ids(
        self,
        league: str,
        athlete_id: str,
        season_year: int,
        *,
        played_only: bool = True,
        limit: int | None = 5,
    ) -> list[str]:
        """Fetch eventlog and return up to ``limit`` game ids."""
        payload = await self.fetch_athlete_eventlog(league, athlete_id, season_year)
        return self.parse_eventlog_game_ids(
            payload, played_only=played_only, limit=limit
        )


__all__ = [
    "EspnGamesClient",
    "GameBoxPlayer",
    "GameSummary",
]
