"""Fixed demo login accounts for local/staging walkthroughs.

Enabled by default whenever ENVIRONMENT is not production. Override with
GRAVITY_ENABLE_DEMO_ACCOUNTS=1/0. Shared password defaults to demo1234
(GRAVITY_DEMO_PASSWORD). Never seeded in production unless explicitly enabled.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

import bcrypt
import asyncpg

from gravity_api.services.onboarding_defaults import (
    default_athletes_sort_for_org_type,
    default_dashboard_tab_for_org_type,
)

DEFAULT_DEMO_PASSWORD = "demo1234"
DEV_ORG_ID = uuid.UUID("00000000-0000-4000-8000-0000000000aa")
DEV_ORG_NAME = "Gravity Dev School"
DEV_ORG_SLUG = "gravity-dev-school"


@dataclass(frozen=True)
class DemoAccount:
    id: uuid.UUID
    email: str
    label: str
    role: str
    org_type: str
    display_name: str
    sport_preferences: tuple[str, ...]
    org_member_role: str | None = None
    org_member_sport: str | None = None
    team_or_athlete_seed: str | None = None


DEMO_ACCOUNTS: tuple[DemoAccount, ...] = (
    DemoAccount(
        id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
        email="demo@gravity.local",
        label="School admin",
        role="school_admin",
        org_type="school",
        display_name="Demo School Admin",
        sport_preferences=("CFB", "NCAAB"),
        org_member_role="school_admin",
        team_or_athlete_seed="Ohio State",
    ),
    DemoAccount(
        id=uuid.UUID("00000000-0000-4000-8000-000000000005"),
        email="coach@gravity.local",
        label="CFB coach",
        role="school_coach",
        org_type="school",
        display_name="Demo CFB Coach",
        sport_preferences=("CFB",),
        org_member_role="school_coach",
        org_member_sport="CFB",
        team_or_athlete_seed="Ohio State",
    ),
    DemoAccount(
        id=uuid.UUID("00000000-0000-4000-8000-000000000002"),
        email="agent@gravity.local",
        label="Agent",
        role="agent",
        org_type="law_firm_agent",
        display_name="Demo Agent",
        sport_preferences=("CFB", "NCAAB"),
        team_or_athlete_seed="Caleb Downs",
    ),
    DemoAccount(
        id=uuid.UUID("00000000-0000-4000-8000-000000000003"),
        email="brand@gravity.local",
        label="Brand",
        role="brand",
        org_type="brand_agency",
        display_name="Demo Brand Manager",
        sport_preferences=("CFB", "NCAAB"),
        team_or_athlete_seed="Nike",
    ),
    DemoAccount(
        id=uuid.UUID("00000000-0000-4000-8000-000000000004"),
        email="admin@gravity.local",
        label="Platform admin",
        role="admin",
        org_type="media_research",
        display_name="Demo Platform Admin",
        sport_preferences=("CFB", "NCAAB", "NCAAW"),
    ),
)


def demo_password() -> str:
    raw = (os.environ.get("GRAVITY_DEMO_PASSWORD") or "").strip()
    return raw or DEFAULT_DEMO_PASSWORD


def is_enabled(*, environment: str, flag: str | None = None) -> bool:
    """Demo accounts are on in non-production unless explicitly disabled."""
    raw = (flag if flag is not None else os.environ.get("GRAVITY_ENABLE_DEMO_ACCOUNTS") or "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return environment.strip().lower() != "production"


def public_catalog(*, password: str | None = None) -> dict:
    pw = password if password is not None else demo_password()
    return {
        "password": pw,
        "accounts": [
            {
                "email": acct.email,
                "label": acct.label,
                "role": acct.role,
                "org_type": acct.org_type,
            }
            for acct in DEMO_ACCOUNTS
        ],
    }


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


async def seed_demo_accounts(
    conn: asyncpg.Connection,
    *,
    password: str | None = None,
) -> int:
    """Upsert demo users so login with the shared password always works."""
    pw = password if password is not None else demo_password()
    if len(pw) < 8:
        raise ValueError("Demo password must be at least 8 characters")
    pw_hash = hash_password(pw)

    await conn.execute(
        """INSERT INTO organizations (id, name, slug)
           VALUES ($1, $2, $3)
           ON CONFLICT (id) DO UPDATE SET
             name = EXCLUDED.name,
             slug = EXCLUDED.slug""",
        DEV_ORG_ID,
        DEV_ORG_NAME,
        DEV_ORG_SLUG,
    )

    seeded = 0
    for acct in DEMO_ACCOUNTS:
        uid = await _upsert_user(conn, acct, pw_hash)
        if acct.org_member_role:
            await _ensure_org_membership(conn, uid, acct)
        await _ensure_watchlist_seed(conn, uid, acct.team_or_athlete_seed)
        seeded += 1
    return seeded


async def _upsert_user(
    conn: asyncpg.Connection,
    acct: DemoAccount,
    pw_hash: str,
) -> uuid.UUID:
    existing = await conn.fetchrow(
        "SELECT id FROM user_accounts WHERE lower(email) = lower($1)",
        acct.email,
    )
    tab = default_dashboard_tab_for_org_type(acct.org_type)
    sort_hint = default_athletes_sort_for_org_type(acct.org_type)
    sports = list(acct.sport_preferences)
    org_id = DEV_ORG_ID if acct.org_member_role else None
    org_name = DEV_ORG_NAME if acct.org_member_role else acct.display_name

    if existing:
        uid = existing["id"]
        await conn.execute(
            """UPDATE user_accounts SET
                 password_hash = $2,
                 role = $3,
                 display_name = $4,
                 org_type = $5,
                 sport_preferences = $6::text[],
                 org_name = $7,
                 team_or_athlete_seed = $8,
                 default_dashboard_tab = $9,
                 athletes_default_sort = $10,
                 onboarding_completed_at = COALESCE(onboarding_completed_at, NOW()),
                 organization = COALESCE($7, organization),
                 organization_id = COALESCE($11, organization_id)
               WHERE id = $1""",
            uid,
            pw_hash,
            acct.role,
            acct.display_name,
            acct.org_type,
            sports,
            org_name,
            acct.team_or_athlete_seed,
            tab,
            sort_hint,
            org_id,
        )
        return uid

    id_taken = await conn.fetchval(
        "SELECT 1 FROM user_accounts WHERE id = $1",
        acct.id,
    )
    new_id = uuid.uuid4() if id_taken else acct.id
    await conn.execute(
        """INSERT INTO user_accounts (
             id, email, role, organization, organization_id, password_hash, display_name,
             org_type, sport_preferences, org_name, team_or_athlete_seed,
             default_dashboard_tab, athletes_default_sort, onboarding_completed_at
           ) VALUES (
             $1, $2, $3, $4, $5, $6, $7,
             $8, $9::text[], $10, $11,
             $12, $13, NOW()
           )""",
        new_id,
        acct.email,
        acct.role,
        org_name or "",
        org_id,
        pw_hash,
        acct.display_name,
        acct.org_type,
        sports,
        org_name,
        acct.team_or_athlete_seed,
        tab,
        sort_hint,
    )
    return new_id


async def _ensure_org_membership(
    conn: asyncpg.Connection,
    user_id: uuid.UUID,
    acct: DemoAccount,
) -> None:
    await conn.execute(
        """INSERT INTO organization_members (user_id, org_id, role, sport)
           SELECT $1, $2, $3, $4
           WHERE NOT EXISTS (
             SELECT 1 FROM organization_members om
             WHERE om.user_id = $1
               AND om.org_id = $2
               AND om.role = $3
               AND COALESCE(om.sport, '') = COALESCE($4, '')
           )""",
        user_id,
        DEV_ORG_ID,
        acct.org_member_role,
        acct.org_member_sport,
    )


async def _ensure_watchlist_seed(
    conn: asyncpg.Connection,
    user_id: uuid.UUID,
    seed: str | None,
) -> None:
    """Populate an empty demo watchlist from the account's team/athlete seed.

    Alert Center only surfaces watchlist-scoped signals, so a seeded login with
    no players would otherwise open a dead feed.
    """
    q = (seed or "").strip()
    if not q:
        return
    already = await conn.fetchval(
        "SELECT 1 FROM watchlists WHERE user_id = $1 LIMIT 1",
        user_id,
    )
    if already:
        return
    rows = await conn.fetch(
        """SELECT id
             FROM athletes
            WHERE COALESCE(is_active, TRUE) = TRUE
              AND (name ILIKE $1 OR school ILIKE $1)
            ORDER BY name
            LIMIT 12""",
        f"%{q}%",
    )
    for row in rows:
        await conn.execute(
            """INSERT INTO watchlists (user_id, athlete_id)
               VALUES ($1, $2)
               ON CONFLICT DO NOTHING""",
            user_id,
            row["id"],
        )
