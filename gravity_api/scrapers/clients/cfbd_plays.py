"""CFBD play-level / metrics client (WP10).

Wraps :class:`CfbdClient` transport (rate limits, auth, backoff) and adds
play-by-play, play-stat, win-probability, and PPA endpoints needed for
``cfb_plays`` / ``cfb_play_players``.

Quota note: bulk season pulls of ``/plays`` + ``/play/stats`` + ``/metrics/wp``
are expensive against CFBD monthly caps — gate behind ``CFBD_MAX_CALLS_PER_RUN``
and prefer per-game or week-scoped pulls before full-season crawls.
"""

from __future__ import annotations

import logging
from typing import Any

from gravity_api.scrapers.clients.cfbd import CfbdClient

logger = logging.getLogger(__name__)


class CfbdPlaysClient(CfbdClient):
    """CFBD client focused on plays, play-stats, WP, and PPA."""

    async def plays(
        self,
        *,
        year: int,
        week: int | None = None,
        team: str | None = None,
        season_type: str = "regular",
        classification: str | None = "fbs",
        game_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """CFBD ``GET /plays`` — play-by-play rows for a season/week/game."""
        params: dict[str, Any] = {"year": year, "seasonType": season_type}
        if week is not None:
            params["week"] = week
        if team:
            params["team"] = team
        if classification:
            params["classification"] = classification
        if game_id is not None:
            params["gameId"] = game_id
        rows = await self._get("/plays", params)
        return rows if isinstance(rows, list) else []

    async def play_stats(
        self,
        *,
        year: int,
        week: int | None = None,
        team: str | None = None,
        game_id: int | None = None,
        athlete_id: int | None = None,
        season_type: str = "regular",
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """CFBD ``GET /play/stats`` — per-play player involvement / roles."""
        params: dict[str, Any] = {"year": year, "seasonType": season_type}
        if week is not None:
            params["week"] = week
        if team:
            params["team"] = team
        if game_id is not None:
            params["gameId"] = game_id
        if athlete_id is not None:
            params["athleteId"] = athlete_id
        if category:
            params["category"] = category
        rows = await self._get("/play/stats", params)
        return rows if isinstance(rows, list) else []

    async def metrics_wp(
        self,
        *,
        game_id: int | None = None,
        year: int | None = None,
        week: int | None = None,
        team: str | None = None,
        season_type: str = "regular",
    ) -> list[dict[str, Any]]:
        """CFBD ``GET /metrics/wp`` — win probability before/after each play."""
        params: dict[str, Any] = {"seasonType": season_type}
        if game_id is not None:
            params["gameId"] = game_id
        if year is not None:
            params["year"] = year
        if week is not None:
            params["week"] = week
        if team:
            params["team"] = team
        rows = await self._get("/metrics/wp", params)
        return rows if isinstance(rows, list) else []

    async def ppa_players_season(
        self,
        *,
        year: int,
        team: str | None = None,
        conference: str | None = None,
        position: str | None = None,
        player_id: int | None = None,
        exclude_garbage_time: bool | None = True,
        season_type: str = "regular",
    ) -> list[dict[str, Any]]:
        """CFBD ``GET /ppa/players/season`` — season-aggregated player PPA."""
        params: dict[str, Any] = {"year": year, "seasonType": season_type}
        if team:
            params["team"] = team
        if conference:
            params["conference"] = conference
        if position:
            params["position"] = position
        if player_id is not None:
            params["playerId"] = player_id
        if exclude_garbage_time is not None:
            params["excludeGarbageTime"] = str(bool(exclude_garbage_time)).lower()
        rows = await self._get("/ppa/players/season", params)
        return rows if isinstance(rows, list) else []

    async def games(
        self,
        *,
        year: int,
        week: int | None = None,
        team: str | None = None,
        season_type: str = "regular",
        classification: str | None = "fbs",
    ) -> list[dict[str, Any]]:
        """CFBD ``GET /games`` — game headers (ids for play pulls)."""
        params: dict[str, Any] = {"year": year, "seasonType": season_type}
        if week is not None:
            params["week"] = week
        if team:
            params["team"] = team
        if classification:
            params["classification"] = classification
        rows = await self._get("/games", params)
        return rows if isinstance(rows, list) else []


__all__ = ["CfbdPlaysClient"]
