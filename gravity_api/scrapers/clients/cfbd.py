"""CollegeFootballData API client — CFB stats and career seasons."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Any

import httpx

from gravity_api.config import get_settings

logger = logging.getLogger(__name__)

_cfbd_request_count = 0
_cfbd_run_request_count = 0
_cfbd_cooldown_until: float = 0.0
_cfbd_request_sem: asyncio.Semaphore | None = None


def _cfbd_concurrency_limit() -> int:
    raw = (os.environ.get("CFBD_MAX_CONCURRENT_REQUESTS") or "1").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


def _get_cfbd_sem() -> asyncio.Semaphore:
    global _cfbd_request_sem
    if _cfbd_request_sem is None:
        _cfbd_request_sem = asyncio.Semaphore(_cfbd_concurrency_limit())
    return _cfbd_request_sem


def _cfbd_max_requests_per_month() -> int:
    raw = (os.environ.get("CFBD_MAX_REQUESTS_PER_MONTH") or "950").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 950


def _cfbd_max_calls_per_run() -> int | None:
    raw = (os.environ.get("CFBD_MAX_CALLS_PER_RUN") or "").strip()
    if not raw:
        return None
    try:
        return max(0, int(raw))
    except ValueError:
        return None


def _cfbd_career_depth() -> int:
    """Prior seasons to fetch in addition to current (0 = current season only)."""
    raw = (os.environ.get("CFBD_CAREER_DEPTH") or "0").strip()
    try:
        return max(0, min(5, int(raw)))
    except ValueError:
        return 0


def _cfbd_request_delay_s() -> float:
    raw = (os.environ.get("CFBD_REQUEST_DELAY_MS") or "250").strip()
    try:
        return max(0.0, int(raw) / 1000.0)
    except ValueError:
        return 0.25


def _cfbd_rate_limit_cooldown_s() -> float:
    raw = (os.environ.get("CFBD_RATE_LIMIT_COOLDOWN_SECS") or "120").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 120.0


def cfbd_requests_used_this_process() -> int:
    return _cfbd_request_count


def cfbd_is_rate_limited() -> bool:
    return time.monotonic() < _cfbd_cooldown_until


def reset_cfbd_run_counters() -> None:
    global _cfbd_run_request_count
    _cfbd_run_request_count = 0


CFBD_BASE = "https://api.collegefootballdata.com"


def _normalize_person_name(name: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9\s'-]", " ", name.lower()).split())


def _names_match(search: str, candidate: str) -> bool:
    search_n = _normalize_person_name(search)
    cand_n = _normalize_person_name(candidate)
    if not search_n or not cand_n:
        return False
    if search_n == cand_n:
        return True
    search_parts = search_n.split()
    cand_parts = cand_n.split()
    if search_parts[-1] != cand_parts[-1]:
        return search_n in cand_n
    if len(search_parts) == 1:
        return True
    return search_parts[0] == cand_parts[0] or search_parts[0][:1] == cand_parts[0][:1]


def _teams_match(team: str, candidate: str) -> bool:
    team_n = _normalize_person_name(team)
    cand_n = _normalize_person_name(candidate)
    if not team_n or not cand_n:
        return False
    return team_n == cand_n or team_n in cand_n or cand_n in team_n


def parse_cfbd_player_id(raw: Any) -> int | None:
    """Return a positive CFBD player id or None if invalid."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    if isinstance(raw, float):
        val = int(raw)
        return val if val > 0 else None
    if isinstance(raw, str):
        s = raw.strip()
        if not s.isdigit():
            return None
        val = int(s)
        return val if val > 0 else None
    return None


def player_id_from_row(row: dict[str, Any]) -> int | None:
    """Extract a positive player id from a CFBD search or stats row."""
    for key in ("playerId", "id"):
        parsed = parse_cfbd_player_id(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _map_cfbd_category_row(row: dict[str, Any]) -> dict[str, float]:
    """Map a CFBD player season row to canonical football stat keys."""
    out: dict[str, float] = {}
    category = str(row.get("category") or row.get("statType") or "").lower()

    def f(key: str) -> float | None:
        val = row.get(key)
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    if category in ("passing", "pass"):
        mapping = {
            "pass_yards": f("yards") or f("passingYards"),
            "pass_td": f("touchdowns") or f("passingTouchdowns"),
            "pass_int": f("interceptions"),
            "pass_attempts": f("attempts") or f("passingAttempts"),
            "pass_completions": f("completions"),
            "completion_pct": f("completionPct") or f("completionPercentage"),
            "passer_rating": f("rating") or f("passerRating"),
            "qbr": f("qbr"),
            "games_played_season": f("games") or f("gamesPlayed"),
        }
    elif category in ("rushing", "rush"):
        mapping = {
            "rush_yards": f("yards") or f("rushingYards"),
            "rush_td": f("touchdowns") or f("rushingTouchdowns"),
            "rush_attempts": f("attempts") or f("rushingAttempts"),
            "yards_per_carry": f("yardsPerRush") or f("average"),
            "games_played_season": f("games") or f("gamesPlayed"),
        }
    elif category in ("receiving", "rec"):
        mapping = {
            "rec_yards": f("yards") or f("receivingYards"),
            "rec_td": f("touchdowns") or f("receivingTouchdowns"),
            "receptions": f("receptions"),
            "rec_targets": f("targets"),
            "yards_per_catch": f("yardsPerReception") or f("average"),
            "games_played_season": f("games") or f("gamesPlayed"),
        }
    elif category in ("defensive", "defense"):
        mapping = {
            "tackles": f("total") or f("tackles"),
            "solo_tackles": f("solo"),
            "sacks": f("sacks"),
            "tfl": f("tfl") or f("tacklesForLoss"),
            "interceptions": f("interceptions"),
            "passes_defended": f("passesDefended") or f("pd"),
            "forced_fumbles": f("fumblesForced") or f("forcedFumbles"),
            "games_played_season": f("games") or f("gamesPlayed"),
        }
    elif category in ("kicking", "kicker"):
        mapping = {
            "fg_made": f("fieldGoals") or f("made"),
            "fg_attempts": f("attempts"),
            "fg_pct": f("pct") or f("percentage"),
            "xp_pct": f("extraPointsPct"),
            "long_fg": f("long"),
            "games_played_season": f("games") or f("gamesPlayed"),
        }
    elif category in ("punting", "punter"):
        mapping = {
            "punt_avg": f("average") or f("yardsPerPunt"),
            "punt_yards": f("yards"),
            "punt_attempts": f("attempts") or f("punts"),
            "games_played_season": f("games") or f("gamesPlayed"),
        }
    else:
        mapping = {}

    for key, val in mapping.items():
        if val is not None:
            out[key] = val
    return out


def _filter_season_rows(
    rows: list[dict[str, Any]],
    *,
    player_id: int | None = None,
    player_name: str | None = None,
) -> list[dict[str, Any]]:
    if not rows:
        return []
    if player_id is not None:
        pid = str(player_id)
        matched = [
            row
            for row in rows
            if isinstance(row, dict) and str(row.get("playerId") or "") == pid
        ]
        if matched:
            return matched
    if player_name:
        matched = [
            row
            for row in rows
            if isinstance(row, dict)
            and _names_match(player_name, str(row.get("player") or ""))
        ]
        if matched:
            return matched
    return []


class CfbdClient:
    def __init__(self, *, api_key: str | None = None, timeout_s: float = 30.0):
        settings = get_settings()
        self.api_key = (api_key or settings.cfbd_api_key or "").strip()
        self.timeout_s = timeout_s

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self.enabled:
            return []
        global _cfbd_request_count, _cfbd_run_request_count, _cfbd_cooldown_until
        if cfbd_is_rate_limited():
            logger.debug("CFBD in cooldown; skipping %s", path)
            return []
        monthly_cap = _cfbd_max_requests_per_month()
        run_cap = _cfbd_max_calls_per_run()
        if monthly_cap and _cfbd_request_count >= monthly_cap:
            logger.warning(
                "CFBD monthly request cap reached (%d/%d); skipping %s",
                _cfbd_request_count,
                monthly_cap,
                path,
            )
            return []
        if run_cap is not None and run_cap == 0:
            logger.debug("CFBD disabled for this run (CFBD_MAX_CALLS_PER_RUN=0); skipping %s", path)
            return []
        if run_cap is not None and run_cap > 0 and _cfbd_run_request_count >= run_cap:
            logger.warning(
                "CFBD per-run request cap reached (%d/%d); skipping %s",
                _cfbd_run_request_count,
                run_cap,
                path,
            )
            return []
        delay = _cfbd_request_delay_s()
        if delay:
            await asyncio.sleep(delay)
        sem = _get_cfbd_sem()
        async with sem:
            _cfbd_request_count += 1
            _cfbd_run_request_count += 1
            headers = {"Authorization": f"Bearer {self.api_key}"}
            url = f"{CFBD_BASE}/{path.lstrip('/')}"
            backoff = (2.0, 5.0)
            async with httpx.AsyncClient(timeout=self.timeout_s, headers=headers) as client:
                for attempt, wait_s in enumerate((0.0, *backoff)):
                    if wait_s:
                        await asyncio.sleep(wait_s)
                    try:
                        resp = await client.get(url, params=params or {})
                    except httpx.HTTPError as exc:
                        logger.warning("CFBD transport error on %s: %s", path, exc)
                        return []
                    if resp.status_code == 429:
                        if attempt < len(backoff):
                            logger.warning("CFBD 429 on %s; retry in %.0fs", path, backoff[attempt])
                            continue
                        cooldown = _cfbd_rate_limit_cooldown_s()
                        _cfbd_cooldown_until = time.monotonic() + cooldown
                        logger.warning(
                            "CFBD rate limited; cooling down %.0fs (path=%s)",
                            cooldown,
                            path,
                        )
                        return []
                    if resp.status_code in (401, 403, 404, 400):
                        logger.debug("CFBD %s -> %s params=%s", path, resp.status_code, params)
                        return []
                    try:
                        resp.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        logger.warning("CFBD HTTP %s on %s: %s", exc.response.status_code, path, exc)
                        return []
                    data = resp.json()
                    return data if isinstance(data, list) else data
        return []

    def _pick_search_row(
        self,
        rows: list[Any],
        *,
        name: str,
        team: str | None,
    ) -> dict[str, Any] | None:
        candidates: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if player_id_from_row(row) is None:
                continue
            display = str(row.get("name") or row.get("fullName") or "")
            row_team = str(row.get("team") or row.get("school") or "")
            if not _names_match(name, display):
                continue
            if team and not _teams_match(team, row_team):
                continue
            candidates.append(row)

        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        if team:
            strict = [
                row
                for row in candidates
                if _teams_match(team, str(row.get("team") or row.get("school") or ""))
                and _names_match(name, str(row.get("name") or row.get("fullName") or ""))
            ]
            if len(strict) == 1:
                return strict[0]
            if strict:
                candidates = strict

        candidates.sort(
            key=lambda row: (
                0 if _normalize_person_name(name) == _normalize_person_name(str(row.get("name") or "")) else 1,
                0 if team and _teams_match(team, str(row.get("team") or "")) else 1,
            )
        )
        return candidates[0]

    async def search_player(self, name: str, *, team: str | None = None) -> dict[str, Any] | None:
        params: dict[str, Any] = {"searchTerm": name}
        if team:
            params["team"] = team
        rows = await self._get("/player/search", params)
        if not isinstance(rows, list) or not rows:
            return None
        picked = self._pick_search_row(rows, name=name, team=team)
        if picked is not None:
            return picked
        if team:
            rows = await self._get("/player/search", {"searchTerm": name})
            if isinstance(rows, list) and rows:
                return self._pick_search_row(rows, name=name, team=team)
        return None

    async def player_season_stats(
        self,
        *,
        year: int,
        player_id: int | None = None,
        team: str | None = None,
        player_name: str | None = None,
    ) -> list[dict[str, Any]]:
        if player_id is not None and player_id <= 0:
            player_id = None
        params: dict[str, Any] = {"year": year, "seasonType": "regular"}
        if team:
            params["team"] = team
        rows = await self._get("/stats/player/season", params)
        if not isinstance(rows, list):
            return []
        filtered = _filter_season_rows(rows, player_id=player_id, player_name=player_name)
        return filtered

    async def player_career_stats(
        self,
        *,
        player_id: int | None,
        team: str | None,
        start_year: int,
        end_year: int,
        player_name: str | None = None,
    ) -> dict[str, dict[str, float]]:
        history: dict[str, dict[str, float]] = {}
        depth = _cfbd_career_depth()
        if depth <= 0:
            return history
        # Only fetch prior seasons; current year handled separately to avoid duplicate calls.
        prior_end = min(end_year - 1, end_year)
        prior_start = max(start_year, end_year - depth)
        if prior_start > prior_end:
            return history
        for year in range(prior_start, prior_end + 1):
            rows = await self.player_season_stats(
                year=year,
                player_id=player_id,
                team=team,
                player_name=player_name,
            )
            merged: dict[str, float] = {}
            for row in rows:
                if not isinstance(row, dict):
                    continue
                merged.update(_map_cfbd_category_row(row))
            if merged:
                history[str(year)] = merged
        return history

    async def fetch_player_stats_bundle(
        self,
        *,
        name: str,
        team: str | None,
        year: int,
    ) -> tuple[dict[str, Any] | None, dict[str, float], dict[str, dict[str, float]]]:
        """Efficient path: search + current season + optional shallow career history."""
        if cfbd_is_rate_limited():
            return None, {}, {}
        player = await self.search_player(name, team=team)
        player_id = player_id_from_row(player) if player else None
        rows = await self.player_season_stats(
            year=year,
            player_id=player_id,
            team=team,
            player_name=name,
        )
        current = self.merge_season_rows(rows)
        history = await self.player_career_stats(
            player_id=player_id,
            team=team,
            start_year=year - 5,
            end_year=year,
            player_name=name,
        )
        if current:
            history[str(year)] = {**history.get(str(year), {}), **current}
        return player, current, history

    def merge_season_rows(self, rows: list[dict[str, Any]]) -> dict[str, float]:
        merged: dict[str, float] = {}
        for row in rows:
            if isinstance(row, dict):
                merged.update(_map_cfbd_category_row(row))
        return merged


__all__ = [
    "CfbdClient",
    "_map_cfbd_category_row",
    "cfbd_is_rate_limited",
    "cfbd_requests_used_this_process",
    "parse_cfbd_player_id",
    "player_id_from_row",
    "reset_cfbd_run_counters",
]
