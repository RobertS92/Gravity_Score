"""WP7: backfill job includes inactive athletes and skips matched seasons."""

from __future__ import annotations

import inspect

from gravity_api.jobs import backfill_season_stats as job
from gravity_api.jobs import backfill_career_stats as career_job


def test_backfill_one_signature_supports_refresh_and_current_only():
    sig = inspect.signature(job.backfill_one)
    assert "refresh_years" in sig.parameters
    assert "current_only" in sig.parameters


def test_career_job_forwards_to_season_backfill():
    src = inspect.getsource(career_job.main)
    assert "backfill_season_stats" in src


def test_athletes_sql_includes_inactive():
    src = inspect.getsource(job._athletes)
    assert "is_active" in src
    # Must NOT require is_active TRUE as a filter.
    assert "COALESCE(is_active, TRUE)" not in src or "AND COALESCE(is_active" not in src
    assert "espn_id IS NOT NULL" in src


def test_matched_skip_query_uses_tot_regular():
    src = inspect.getsource(job._matched_years)
    assert "team_id = 'TOT'" in src
    assert "season_type = 'regular'" in src
    assert "validation_status = 'matched'" in src
