"""Tests for the CSC report v3 rollout resolver."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

import pytest

from gravity_api.services.csc_report_rollout import (
    ReportRolloutState,
    load_report_rollout_state,
)


class _FakeDb:
    def __init__(
        self,
        *,
        phase: Optional[str] = None,
        override_version: Optional[str] = None,
        raise_on_phase: bool = False,
        raise_on_override: bool = False,
    ):
        self._phase = phase
        self._override = override_version
        self._raise_phase = raise_on_phase
        self._raise_override = raise_on_override

    async def fetchrow(self, query: str, *args: Any):
        if "csc_report_rollout" in query and "user_id" not in query:
            if self._raise_phase:
                raise RuntimeError("db unavailable")
            if self._phase is None:
                return None
            return {"current_phase": self._phase}
        if "csc_report_account_overrides" in query:
            if self._raise_override:
                raise RuntimeError("db unavailable")
            if self._override is None:
                return None
            return {"force_report_version": self._override}
        return None


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("CSC_REPORT_V3", raising=False)
    monkeypatch.delenv("CSC_REPORT_V3_DEFAULT", raising=False)


def test_phase1_defaults_to_v2():
    state = _run(load_report_rollout_state(_FakeDb(phase="phase1"), user_id=None))
    assert state == ReportRolloutState(phase="phase1", version="v2")


def test_phase2_promotes_to_v3():
    state = _run(load_report_rollout_state(_FakeDb(phase="phase2"), user_id=None))
    assert state == ReportRolloutState(phase="phase2", version="v3")


def test_phase3_serves_v3():
    state = _run(load_report_rollout_state(_FakeDb(phase="phase3"), user_id=None))
    assert state.version == "v3"


def test_phase4_serves_v3():
    state = _run(load_report_rollout_state(_FakeDb(phase="phase4"), user_id=None))
    assert state.version == "v3"


def test_per_user_override_wins_over_phase():
    state = _run(
        load_report_rollout_state(
            _FakeDb(phase="phase4", override_version="v2"),
            user_id="user-1",
        )
    )
    assert state == ReportRolloutState(phase="phase4", version="v2")


def test_per_user_override_can_promote():
    state = _run(
        load_report_rollout_state(
            _FakeDb(phase="phase1", override_version="v3"),
            user_id="user-1",
        )
    )
    assert state == ReportRolloutState(phase="phase1", version="v3")


def test_env_default_promotes_when_set(monkeypatch):
    monkeypatch.setenv("CSC_REPORT_V3", "1")
    state = _run(load_report_rollout_state(_FakeDb(phase="phase1"), user_id=None))
    assert state.version == "v3"


def test_db_error_falls_back_to_phase1_then_env(monkeypatch):
    monkeypatch.setenv("CSC_REPORT_V3_DEFAULT", "false")
    state = _run(
        load_report_rollout_state(
            _FakeDb(raise_on_phase=True),
            user_id=None,
        )
    )
    assert state == ReportRolloutState(phase="phase1", version="v2")


def test_override_query_error_does_not_crash():
    state = _run(
        load_report_rollout_state(
            _FakeDb(phase="phase4", raise_on_override=True),
            user_id="user-1",
        )
    )
    assert state == ReportRolloutState(phase="phase4", version="v3")


def test_missing_rollout_row_defaults_to_phase1():
    state = _run(load_report_rollout_state(_FakeDb(), user_id=None))
    assert state.phase == "phase1"
    assert state.version == "v2"
