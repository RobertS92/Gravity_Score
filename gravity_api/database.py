"""Async PostgreSQL pool (asyncpg)."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from urllib.parse import urlparse

import asyncpg

from gravity_api.config import get_settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

_LOCALHOST_DSN_MARKERS = ("localhost", "127.0.0.1", "::1")


def _redact_dsn_host(dsn: str) -> str:
    """Return a log-safe DSN host snippet (no credentials)."""
    try:
        parsed = urlparse(dsn)
        host = parsed.hostname or "(missing host)"
        port = parsed.port or 5432
        db = (parsed.path or "/").lstrip("/") or "?"
        return f"{host}:{port}/{db}"
    except Exception:
        return "(unparseable PG_DSN)"


def validate_pg_dsn_for_startup(*, environment: str, pg_dsn: str) -> None:
    """Fail fast with an operator-readable message when Postgres is misconfigured.

    Railway containers have no local Postgres; the default dev DSN
    ``postgresql://localhost:5432/gravity`` always crashes lifespan startup
    with an opaque asyncpg stack trace unless PG_DSN is set on the service.
    """
    cleaned = (pg_dsn or "").strip()
    if not cleaned:
        raise RuntimeError(
            "PG_DSN is empty. Set PG_DSN on the gravity_api Railway service "
            "(Supabase connection string or Postgres URL)."
        )
    host = (urlparse(cleaned).hostname or "").lower()
    if environment.strip().lower() == "production" and host in _LOCALHOST_DSN_MARKERS:
        raise RuntimeError(
            "PG_DSN still points at localhost in production. Set PG_DSN on the "
            "gravity_api service to your hosted Postgres URL before redeploying."
        )


async def init_db() -> None:
    global _pool
    if _pool is not None:
        return
    settings = get_settings()
    validate_pg_dsn_for_startup(
        environment=settings.environment,
        pg_dsn=settings.pg_dsn,
    )
    # Supabase's transaction-mode pooler (port 6543) is PgBouncer, which does not
    # support prepared statements. Disable asyncpg's statement cache so queries
    # don't fail with "prepared statement 'X' does not exist" errors. Safe on
    # direct-connection deployments too.
    try:
        _pool = await asyncpg.create_pool(
            dsn=settings.pg_dsn,
            min_size=1,
            max_size=10,
            command_timeout=60,
            statement_cache_size=0,
        )
    except Exception as exc:
        host_hint = _redact_dsn_host(settings.pg_dsn)
        logger.exception(
            "PostgreSQL pool initialization failed for %s (%s)",
            host_hint,
            type(exc).__name__,
        )
        raise RuntimeError(
            f"Could not connect to Postgres at {host_hint}. Verify PG_DSN on the "
            f"gravity_api service (credentials, SSL, pooler port 6543 vs 5432). "
            f"Original error: {exc}"
        ) from exc
    logger.info("PostgreSQL pool initialized (%s)", _redact_dsn_host(settings.pg_dsn))


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
