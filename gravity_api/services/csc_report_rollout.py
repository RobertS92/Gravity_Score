"""CSC report v3 rollout resolver.

Mirrors the tier rollout helper in :mod:`csc_report_builder` so the choice
of report version (v2 legacy vs. v3 spec) can be moved independently from
the tier methodology.

Phases (matches migrations/024_csc_report_v3_rollout.sql seed):
  phase1 — dual write v2/v3, default render = v2.
  phase2 — v3 default for new reports; per-account overrides allowed.
  phase3 — v3 only for new reports.
  phase4 — v2 deprecated.

Environment override: ``CSC_REPORT_V3_DEFAULT`` (true/false) forces the
default version when the DB-driven phase row is absent or unreadable.

The settings layer also exposes ``CSC_REPORT_V3=1`` as an emergency kill
switch.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Literal, Optional

import asyncpg

logger = logging.getLogger(__name__)

ReportVersion = Literal["v2", "v3"]


@dataclass(frozen=True)
class ReportRolloutState:
    phase: str
    version: ReportVersion


def _env_default_version() -> ReportVersion:
    """Reads CSC_REPORT_V3 / CSC_REPORT_V3_DEFAULT from env.

    Returns v3 when either env var is set to a truthy value.
    """
    for key in ("CSC_REPORT_V3", "CSC_REPORT_V3_DEFAULT"):
        raw = os.getenv(key)
        if raw is None:
            continue
        if raw.strip().lower() in {"1", "true", "yes", "on"}:
            return "v3"
        if raw.strip().lower() in {"0", "false", "no", "off"}:
            return "v2"
    return "v2"


def _version_from_phase(phase: str) -> ReportVersion:
    if phase in {"phase1"}:
        return "v2"
    return "v3"


async def load_report_rollout_state(
    db: asyncpg.Connection, user_id: Optional[str]
) -> ReportRolloutState:
    """Resolve the report version to serve for this user.

    Resolution order:
      1. Per-user override row (always wins).
      2. DB-driven rollout phase.
      3. Environment default (CSC_REPORT_V3 / CSC_REPORT_V3_DEFAULT).
      4. v2 fallback.
    """
    phase = "phase1"
    try:
        row = await db.fetchrow(
            "SELECT current_phase FROM csc_report_rollout ORDER BY id ASC LIMIT 1"
        )
        if row and row.get("current_phase"):
            phase = str(row["current_phase"])
    except Exception:  # noqa: BLE001 — DB may be unavailable in tests / cold env
        logger.debug("csc_report_rollout query failed; falling back to env default")
        phase = "phase1"

    if user_id:
        try:
            override = await db.fetchrow(
                """SELECT force_report_version
                   FROM csc_report_account_overrides
                   WHERE user_id = $1""",
                user_id,
            )
            if override and override.get("force_report_version") in {"v2", "v3"}:
                return ReportRolloutState(
                    phase=phase, version=str(override["force_report_version"])  # type: ignore[arg-type]
                )
        except Exception:  # noqa: BLE001
            logger.debug("csc_report_account_overrides query failed", exc_info=True)

    # If env default is explicitly set, it acts as a phase-independent
    # advance/rollback lever.
    env_default = _env_default_version()
    if env_default == "v3":
        return ReportRolloutState(phase=phase, version="v3")
    return ReportRolloutState(phase=phase, version=_version_from_phase(phase))
