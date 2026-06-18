"""Async PostgreSQL pool (asyncpg)."""

import logging
import socket
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


def _connection_error_message(*, host_hint: str, exc: Exception) -> str:
    """Turn low-level connect failures into operator-readable guidance."""
    if isinstance(exc, (socket.gaierror, OSError)) and getattr(exc, "errno", None) in (-2, 8):
        # errno -2 (EAI_NONAME) / 8 (ENOENT on some platforms): hostname does not resolve.
        return (
            f"Postgres hostname in PG_DSN does not resolve (DNS NXDOMAIN): {host_hint}. "
            "The Supabase project ref in PG_DSN is likely wrong, the project was deleted/paused, "
            "or the connection string is stale. In Supabase → Project Settings → Database, copy a "
            "fresh URI (Transaction pooler :6543 recommended for Railway) and update PG_DSN on "
            "the gravity_api service, then redeploy."
        )
    return (
        f"Could not connect to Postgres at {host_hint}. Verify PG_DSN on the gravity_api "
        f"service (credentials, sslmode=require for Supabase direct :5432, pooler port 6543). "
        f"Original error: {exc}"
    )


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
        raise RuntimeError(_connection_error_message(host_hint=host_hint, exc=exc)) from exc
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
