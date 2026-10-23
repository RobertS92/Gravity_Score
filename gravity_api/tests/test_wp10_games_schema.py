"""WP10: migration 039 SQL is parseable and names the expected tables/columns."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "039_games.sql"

EXPECTED_TABLES = (
    "games",
    "game_player_box",
    "cfb_plays",
    "cfb_play_players",
)

GAMES_COLUMNS = {
    "game_id",
    "league",
    "season_year",
    "season_type",
    "start_time",
    "home_team_id",
    "away_team_id",
    "home_score",
    "away_score",
    "neutral_site",
    "status",
    "source_url",
    "collected_at",
}

BOX_COLUMNS = {
    "game_id",
    "athlete_id",
    "espn_athlete_id",
    "team_id",
    "started",
    "minutes",
    "snaps",
    "stats",
}

CFB_PLAYS_REQUIRED = {
    "play_id",
    "game_id",
    "ppa",
    "home_wp_before",
    "home_wp_after",
}

CFB_PLAY_PLAYERS_REQUIRED = {
    "play_id",
    "athlete_id",
    "role",
}


def _strip_sql_comments(sql: str) -> str:
    no_line = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
    return re.sub(r"/\*.*?\*/", "", no_line, flags=re.DOTALL)


def _create_table_body(sql: str, table: str) -> str:
    """Return the parenthesized column list for CREATE TABLE ``table``."""
    pattern = re.compile(
        rf"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+{re.escape(table)}\s*\((.*?)\)\s*;",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(sql)
    assert match, f"CREATE TABLE for {table} not found"
    return match.group(1)


def _column_names(body: str) -> set[str]:
    names: set[str] = set()
    for line in body.splitlines():
        stripped = line.strip().rstrip(",")
        if not stripped:
            continue
        upper = stripped.upper()
        if upper.startswith(
            (
                "PRIMARY KEY",
                "UNIQUE",
                "CHECK",
                "CONSTRAINT",
                "FOREIGN KEY",
                "REFERENCES",
            )
        ):
            continue
        # first token is the column name
        token = stripped.split()[0].strip('"')
        if token.upper() in {"PRIMARY", "UNIQUE", "CHECK", "CONSTRAINT"}:
            continue
        names.add(token.lower())
    return names


@pytest.fixture(scope="module")
def migration_sql() -> str:
    assert MIGRATION.is_file(), f"missing {MIGRATION}"
    return MIGRATION.read_text(encoding="utf-8")


def test_039_migration_file_exists(migration_sql: str):
    assert "CREATE TABLE" in migration_sql.upper()
    assert len(migration_sql) > 200


def test_039_sql_is_parseable_enough(migration_sql: str):
    """Lightweight syntax sanity: balanced parens/quotes, no empty statements."""
    sql = _strip_sql_comments(migration_sql)
    assert sql.count("(") == sql.count(")"), "unbalanced parentheses"
    assert sql.count("'") % 2 == 0, "unbalanced single quotes"
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    assert statements, "no SQL statements"
    for stmt in statements:
        assert re.match(
            r"^(CREATE|ALTER|DROP|COMMENT|GRANT)\b",
            stmt,
            re.IGNORECASE,
        ), f"unexpected statement start: {stmt[:60]!r}"


def test_039_creates_expected_tables(migration_sql: str):
    sql = _strip_sql_comments(migration_sql)
    for table in EXPECTED_TABLES:
        assert re.search(
            rf"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+{table}\b",
            sql,
            re.IGNORECASE,
        ), f"missing CREATE TABLE {table}"


def test_039_games_columns(migration_sql: str):
    sql = _strip_sql_comments(migration_sql)
    cols = _column_names(_create_table_body(sql, "games"))
    missing = GAMES_COLUMNS - cols
    assert not missing, f"games missing columns: {sorted(missing)}"


def test_039_game_player_box_columns_and_pk(migration_sql: str):
    sql = _strip_sql_comments(migration_sql)
    body = _create_table_body(sql, "game_player_box")
    cols = _column_names(body)
    missing = BOX_COLUMNS - cols
    assert not missing, f"game_player_box missing columns: {sorted(missing)}"
    assert re.search(
        r"PRIMARY\s+KEY\s*\(\s*game_id\s*,\s*espn_athlete_id\s*\)",
        body,
        re.IGNORECASE,
    ), "game_player_box PK must be (game_id, espn_athlete_id)"


def test_039_cfb_plays_has_ppa_and_wp(migration_sql: str):
    sql = _strip_sql_comments(migration_sql)
    cols = _column_names(_create_table_body(sql, "cfb_plays"))
    missing = CFB_PLAYS_REQUIRED - cols
    assert not missing, f"cfb_plays missing columns: {sorted(missing)}"


def test_039_cfb_play_players_has_role(migration_sql: str):
    sql = _strip_sql_comments(migration_sql)
    cols = _column_names(_create_table_body(sql, "cfb_play_players"))
    missing = CFB_PLAY_PLAYERS_REQUIRED - cols
    assert not missing, f"cfb_play_players missing columns: {sorted(missing)}"


def test_apply_all_globs_numbered_migrations():
    """apply_all.sh uses a glob — 039 is picked up without an explicit list."""
    script = (ROOT / "migrations" / "apply_all.sh").read_text(encoding="utf-8")
    assert "[0-9][0-9][0-9]_*.sql" in script


def test_wp10_stub_modules_importable():
    from gravity_api.jobs import backfill_game_boxes
    from gravity_api.scrapers.clients.cfbd_plays import CfbdPlaysClient
    from gravity_api.scrapers.clients.espn_games import EspnGamesClient, GameSummary
    from gravity_api.services import games_store

    assert hasattr(EspnGamesClient, "fetch_game_summary")
    assert hasattr(CfbdPlaysClient, "plays")
    assert hasattr(CfbdPlaysClient, "play_stats")
    assert hasattr(CfbdPlaysClient, "metrics_wp")
    assert hasattr(CfbdPlaysClient, "ppa_players_season")
    assert callable(games_store.upsert_game)
    assert callable(games_store.upsert_box_rows)
    assert callable(backfill_game_boxes.parse_args)
    ns = backfill_game_boxes.parse_args(
        ["--league", "ncaab_mens", "--season-year", "2024", "--limit", "5", "--dry-run"]
    )
    assert ns.league == "ncaab_mens"
    assert ns.season_year == 2024
    assert ns.limit == 5
    assert ns.dry_run is True
    assert GameSummary.__dataclass_fields__  # type: ignore[attr-defined]
