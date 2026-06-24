"""Optional DB connection for scrapers that read from Postgres."""

from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg

_scrape_db: contextvars.ContextVar[asyncpg.Connection | None] = contextvars.ContextVar(
    "_scrape_db", default=None
)


def begin_scrape_db(conn: asyncpg.Connection) -> None:
    _scrape_db.set(conn)


def clear_scrape_db() -> None:
    _scrape_db.set(None)


def get_scrape_db() -> asyncpg.Connection | None:
    return _scrape_db.get()
