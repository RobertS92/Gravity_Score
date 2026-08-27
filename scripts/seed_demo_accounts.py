#!/usr/bin/env python3
"""Upsert demo login accounts (demo@gravity.local / demo1234, plus role variants)."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

import asyncpg

from gravity_api.services.demo_accounts import (
    DEMO_ACCOUNTS,
    demo_password,
    is_enabled,
    seed_demo_accounts,
)


async def _run(dsn: str, *, password: str, force: bool) -> None:
    env = os.environ.get("ENVIRONMENT", "development")
    if not is_enabled(environment=env) and not force:
        print(
            "Refusing to seed demo accounts in production. "
            "Pass --force or set GRAVITY_ENABLE_DEMO_ACCOUNTS=1.",
            file=sys.stderr,
        )
        sys.exit(1)
    conn = await asyncpg.connect(dsn)
    try:
        n = await seed_demo_accounts(conn, password=password)
    finally:
        await conn.close()
    print(f"Seeded {n} demo accounts. Shared password: {password}")
    for acct in DEMO_ACCOUNTS:
        print(f"  {acct.email:24}  {acct.label} ({acct.role})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Gravity demo login accounts")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow seeding when ENVIRONMENT=production",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Override GRAVITY_DEMO_PASSWORD / default demo1234",
    )
    args = parser.parse_args()
    dsn = os.environ.get("PG_DSN") or os.environ.get("DATABASE_URL")
    if not dsn:
        print("Set PG_DSN or DATABASE_URL", file=sys.stderr)
        sys.exit(1)
    asyncio.run(_run(dsn, password=args.password or demo_password(), force=args.force))


if __name__ == "__main__":
    main()
