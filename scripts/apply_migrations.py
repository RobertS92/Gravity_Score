#!/usr/bin/env python3
"""Apply pending SQL migrations from migrations/ directory in sorted order."""

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


async def apply(dsn: str, *, dry_run: bool = False) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                 filename TEXT PRIMARY KEY,
                 applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
               )"""
        )
        root = Path(__file__).resolve().parents[1] / "migrations"
        files = sorted(p.name for p in root.glob("*.sql"))
        for filename in files:
            applied = await conn.fetchval(
                "SELECT 1 FROM schema_migrations WHERE filename = $1", filename
            )
            if applied:
                print(f"skip  {filename}")
                continue
            path = root / filename
            sql = path.read_text(encoding="utf-8")
            print(f"apply {filename} ...")
            if dry_run:
                continue
            try:
                async with conn.transaction():
                    await conn.execute(sql)
                    await conn.execute(
                        "INSERT INTO schema_migrations (filename) VALUES ($1)", filename
                    )
                print(f"done  {filename}")
            except Exception as exc:
                print(f"FAIL  {filename}: {exc}", file=sys.stderr)
                raise
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Gravity SQL migrations")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    dsn = os.environ.get("PG_DSN") or os.environ.get("DATABASE_URL")
    if not dsn:
        print("Set PG_DSN or DATABASE_URL", file=sys.stderr)
        sys.exit(1)
    asyncio.run(apply(dsn, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
