"""Async PostgreSQL pool (asyncpg)."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg

from gravity_api.config import get_settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_db() -> None:
    global _pool
    if _pool is not None:
        return
    settings = get_settings()
    # Supabase's transaction-mode pooler (port 6543) is PgBouncer, which does not
    # support prepared statements. Disable asyncpg's statement cache so queries
    # don't fail with "prepared statement 'X' does not exist" errors. Safe on
    # direct-connection deployments too.
    _pool = await asyncpg.create_pool(
        dsn=settings.pg_dsn,
        min_size=1,
        max_size=10,
        command_timeout=60,
        statement_cache_size=0,
    )
    logger.info("PostgreSQL pool initialized")


async def close_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL pool closed")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized; call init_db() on startup")
    return _pool


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn
