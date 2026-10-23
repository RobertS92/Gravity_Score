"""Live WP10 games + season-history collectors for scraper smoke (no DB).

Exercises:
- ``EspnClient.list_stat_seasons`` / ``get_season_stat_lines`` (per-season
  ``SeasonStatLine`` with ``stats_as_of``, season labels, team-for-season)
- ``EspnGamesClient`` eventlog → summary → ``game_player_box``-shaped rows
  (fetch/validate on the free ESPN path; persist still needs ``PG_DSN``)
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from gravity_api.scraper_smoke.athletes import SmokeAthlete
from gravity_api.scrapers.clients.espn import EspnClient
from gravity_api.scrapers.clients.espn_games import EspnGamesClient, GameSummary
from gravity_api.scrapers.parsers.stat_normalizer import normalize_namespaced_stats
from gravity_api.scrapers.season_calendar import (
    current_season_year,
    season_label as calendar_season_label,
    season_status,
)
from gravity_api.scrapers.types import SeasonStatLine
from gravity_api.services.games_store import box_score_reconciliation

# Basketball leagues where SUM(player pts) vs header score is meaningful.
_BOX_RECONCILE_LEAGUES = frozenset(
    {"nba", "wnba", "ncaab_mens", "ncaab_womens", "mcbb", "wcbb"}
)


@dataclass
class SeasonHistorySmoke:
    ok: bool
    n_seasons_log: int = 0
    n_lines_fetched: int = 0
    n_with_stats_as_of: int = 0
    n_with_team: int = 0
    season_years: list[int] = field(default_factory=list)
    season_labels: list[str] = field(default_factory=list)
    team_names: list[str] = field(default_factory=list)
    lines: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Wp10GamesSmoke:
    ok: bool
    season_year_used: int | None = None
    games_fetched: int = 0
    games_with_athlete_box: int = 0
    box_reconcile_ok: bool | None = None
    game_ids: list[str] = field(default_factory=list)
    games: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    detail: str = ""
    skipped_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _line_to_history_blob(line: SeasonStatLine, sport: str) -> dict[str, Any]:
    """Shape a ``SeasonStatLine`` into smoke/export season_stats_history blob."""
    canonical = normalize_namespaced_stats(sport, line.stats)
    if not canonical and line.stats:
        # Flat keys already (rare); keep numeric values.
        canonical = {
            str(k): float(v)
            for k, v in line.stats.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        }
    gp = (
        canonical.get("games_played_season")
        or canonical.get("gp")
        or canonical.get("games_played")
    )
    as_of = line.stats_as_of
    if isinstance(as_of, datetime):
        as_of_s = as_of.astimezone(timezone.utc).isoformat()
    else:
        as_of_s = str(as_of) if as_of else None
    try:
        label = calendar_season_label(sport, int(line.season_year))
    except (TypeError, ValueError):
        label = str(line.season_year)
    try:
        complete = (
            season_status(sport, int(line.season_year), date.today()) == "complete"
        )
    except (TypeError, ValueError):
        complete = None
    blob: dict[str, Any] = {
        **canonical,
        "season_year": line.season_year,
        "season_label": label,
        "season_type": line.season_type,
        "team_id": line.team_id,
        "team_name": line.team_name,
        "is_total": line.is_total,
        "is_complete": complete,
        "stats_as_of": as_of_s,
        "source_key": line.source_key,
        "source_url": line.source_url,
        "validation_status": "unvalidated",
    }
    if gp is not None:
        blob["games_played_season"] = gp
        blob["gp"] = gp
    return blob


async def collect_season_history(
    athlete: SmokeAthlete,
    client: EspnClient | None = None,
    *,
    max_seasons: int | None = None,
    include_postseason: bool = False,
    concurrency: int = 4,
) -> SeasonHistorySmoke:
    """Live fetch per-season ``SeasonStatLine`` rows for one smoke athlete."""
    client = client or EspnClient()
    sport = athlete.sport
    try:
        seasons = await client.list_stat_seasons(athlete.espn_id, sport)
    except Exception as exc:  # noqa: BLE001
        return SeasonHistorySmoke(ok=False, error=str(exc), detail="list_stat_seasons failed")

    years = sorted({int(y) for y, _st, _ref in seasons})
    if max_seasons is not None and len(years) > int(max_seasons):
        # Prefer oldest + most recent seasons when capping.
        keep = max(1, int(max_seasons))
        if keep == 1:
            years = [years[-1]]
        else:
            years = sorted({years[0], *years[-(keep - 1) :]})

    if not years:
        # Rookies / empty log — soft pass (identity covered elsewhere).
        return SeasonHistorySmoke(
            ok=True,
            n_seasons_log=0,
            detail="no seasons in statisticslog (rookie/empty)",
        )

    sem = asyncio.Semaphore(max(1, concurrency))

    async def _one(year: int, stype: str) -> list[SeasonStatLine]:
        async with sem:
            try:
                return await client.get_season_stat_lines(
                    athlete.espn_id, sport, year, stype
                )
            except Exception:  # noqa: BLE001
                return []

    tasks: list[asyncio.Task[list[SeasonStatLine]]] = []
    for year in years:
        types = {st for y, st, _ in seasons if y == year} or {"regular"}
        types.add("regular")
        if not include_postseason:
            types = {"regular"}
        for stype in sorted(types, key=lambda s: 0 if s == "regular" else 1):
            tasks.append(asyncio.create_task(_one(year, stype)))

    fetched: list[SeasonStatLine] = []
    for result in await asyncio.gather(*tasks):
        fetched.extend(result)

    # Prefer TOT regular lines for history blobs; keep team splits as extras.
    tot_regular = [
        ln
        for ln in fetched
        if ln.season_type == "regular" and ln.is_total
    ]
    if not tot_regular:
        tot_regular = [ln for ln in fetched if ln.season_type == "regular"]

    lines_out = [_line_to_history_blob(ln, sport) for ln in tot_regular]
    # Stable order by season_year.
    lines_out.sort(key=lambda b: (int(b.get("season_year") or 0), str(b.get("team_id"))))

    n_as_of = sum(1 for b in lines_out if b.get("stats_as_of"))
    n_team = sum(
        1
        for b in lines_out
        if (b.get("team_name") or (b.get("team_id") and b.get("team_id") != "TOT"))
    )
    labels = [str(b.get("season_label") or b.get("season_year")) for b in lines_out]
    teams = [
        str(b.get("team_name") or b.get("team_id") or "")
        for b in lines_out
        if b.get("team_name") or b.get("team_id")
    ]

    # Pass when we got at least one line with real timestamp provenance.
    # Empty-log soft-pass already handled; fetch failure on known years → fail.
    ok = bool(lines_out) and n_as_of == len(lines_out)
    detail = (
        f"log_years={len(years)} lines={len(lines_out)} "
        f"stats_as_of={n_as_of}/{len(lines_out)} teams={n_team}"
    )
    return SeasonHistorySmoke(
        ok=ok,
        n_seasons_log=len(years),
        n_lines_fetched=len(lines_out),
        n_with_stats_as_of=n_as_of,
        n_with_team=n_team,
        season_years=[int(b["season_year"]) for b in lines_out if b.get("season_year") is not None],
        season_labels=labels,
        team_names=teams,
        lines=lines_out,
        detail=detail,
        error=None if ok else "season history missing lines or stats_as_of",
    )


def _candidate_game_years(sport: str, today: date | None = None) -> list[int]:
    """Current season year, then prior (college sports often empty early season)."""
    on = today or date.today()
    current = current_season_year(sport, on)
    years = [current]
    if current - 1 not in years:
        years.append(current - 1)
    return years


async def collect_wp10_games(
    athlete: SmokeAthlete,
    *,
    espn_client: EspnClient | None = None,
    games_client: EspnGamesClient | None = None,
    max_games: int = 2,
) -> Wp10GamesSmoke:
    """Live fetch games + box rows for one smoke athlete (ESPN free path)."""
    espn_client = espn_client or EspnClient()
    games_client = games_client or EspnGamesClient()
    sport = athlete.sport
    max_games = max(1, int(max_games))

    game_ids: list[str] = []
    year_used: int | None = None
    try:
        for year in _candidate_game_years(sport):
            ids = await games_client.list_athlete_game_ids(
                sport,
                athlete.espn_id,
                year,
                played_only=True,
                limit=max_games,
            )
            if not ids:
                # Some eventlogs mark played=false until stats attach — allow any.
                ids = await games_client.list_athlete_game_ids(
                    sport,
                    athlete.espn_id,
                    year,
                    played_only=False,
                    limit=max_games,
                )
            if ids:
                game_ids = ids
                year_used = year
                break
    except Exception as exc:  # noqa: BLE001
        return Wp10GamesSmoke(
            ok=False,
            error=str(exc),
            detail="eventlog fetch failed",
        )

    if not game_ids:
        # Soft-pass: rookie / preseason / no games published yet.
        return Wp10GamesSmoke(
            ok=True,
            season_year_used=year_used,
            skipped_reason="no eventlog games on free ESPN path",
            detail="no games to fetch (acceptable for pre-debut / offseason)",
        )

    games_out: list[dict[str, Any]] = []
    with_box = 0
    reconcile_results: list[bool] = []

    for gid in game_ids[:max_games]:
        try:
            summary: GameSummary = await games_client.fetch_parsed_game(sport, gid)
        except Exception as exc:  # noqa: BLE001
            games_out.append(
                {
                    "game_id": gid,
                    "ok": False,
                    "error": str(exc),
                }
            )
            continue

        athlete_rows = [
            p for p in summary.players if str(p.espn_athlete_id) == str(athlete.espn_id)
        ]
        if athlete_rows:
            with_box += 1

        reconcile: dict[str, Any] | None = None
        if sport in _BOX_RECONCILE_LEAGUES and summary.players:
            players = [
                {
                    "team_id": p.team_id,
                    "espn_athlete_id": p.espn_athlete_id,
                    "stats": p.stats,
                }
                for p in summary.players
            ]
            reconcile = box_score_reconciliation(
                home_team_id=summary.home_team_id,
                away_team_id=summary.away_team_id,
                home_score=summary.home_score,
                away_score=summary.away_score,
                players=players,
            )
            reconcile_results.append(bool(reconcile.get("matched")))

        games_out.append(
            {
                "game_id": summary.game_id,
                "ok": True,
                "league": summary.league,
                "season_year": summary.season_year,
                "season_type": summary.season_type,
                "status": summary.status,
                "home_team_id": summary.home_team_id,
                "away_team_id": summary.away_team_id,
                "home_score": summary.home_score,
                "away_score": summary.away_score,
                "n_box_players": len(summary.players),
                "athlete_box_rows": len(athlete_rows),
                "athlete_team_id": athlete_rows[0].team_id if athlete_rows else None,
                "athlete_stats_keys": sorted(athlete_rows[0].stats.keys())[:12]
                if athlete_rows
                else [],
                "source_url": summary.source_url,
                "box_reconcile_matched": (
                    reconcile.get("matched") if reconcile is not None else None
                ),
            }
        )

    fetched_ok = sum(1 for g in games_out if g.get("ok"))
    box_ok = (
        all(reconcile_results)
        if reconcile_results
        else None
    )
    # Pass: at least one game summary fetched with header scores; prefer athlete box.
    ok = fetched_ok > 0 and (
        with_box > 0
        or all(
            g.get("home_score") is not None and g.get("away_score") is not None
            for g in games_out
            if g.get("ok")
        )
    )
    # If basketball reconcile ran and failed, fail the check.
    if box_ok is False:
        ok = False

    detail = (
        f"year={year_used} fetched={fetched_ok}/{len(game_ids)} "
        f"athlete_box={with_box} box_reconcile={box_ok}"
    )
    return Wp10GamesSmoke(
        ok=ok,
        season_year_used=year_used,
        games_fetched=fetched_ok,
        games_with_athlete_box=with_box,
        box_reconcile_ok=box_ok,
        game_ids=[str(g.get("game_id")) for g in games_out if g.get("game_id")],
        games=games_out,
        detail=detail,
        error=None if ok else "WP10 live games fetch/validate failed",
    )


__all__ = [
    "SeasonHistorySmoke",
    "Wp10GamesSmoke",
    "collect_season_history",
    "collect_wp10_games",
]
