"""M3/M4/M5 — formula / self-score training paths cannot silently promote."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from gravity_ml.train.promotion_gate import PromotionRefused, assert_label_source_allowed
from gravity_ml.train.train_champion import (
    BANNED_SELF_TRAIN_TARGETS,
    FORMULA_SELF_TRAIN_ENV,
    _formula_self_train_allowed,
    fetch_training_rows,
)


ROOT = Path(__file__).resolve().parents[2]


def test_formula_self_train_env_off_by_default(monkeypatch):
    monkeypatch.delenv(FORMULA_SELF_TRAIN_ENV, raising=False)
    assert _formula_self_train_allowed(False) is False
    assert "target_impact_score" in BANNED_SELF_TRAIN_TARGETS


def test_fetch_training_rows_refuses_without_flag(monkeypatch):
    import asyncio

    monkeypatch.delenv(FORMULA_SELF_TRAIN_ENV, raising=False)

    async def _run():
        with pytest.raises(PromotionRefused, match="M3/M4"):
            await fetch_training_rows("athlete", "cfb", "nil_valuation_usd")

    asyncio.run(_run())


def test_train_cfb_impact_v1_refuses_by_default():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "train_cfb_impact_v1.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 2
    assert "formula-label" in (proc.stderr + proc.stdout).lower() or "M4" in (
        proc.stderr + proc.stdout
    )


def test_train_impact_module_requires_fixture_or_csv():
    proc = subprocess.run(
        [sys.executable, "-m", "gravity_ml.impact.train_impact", "--league", "ncaab_mens"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 1
    combined = proc.stderr + proc.stdout
    assert "WP10" in combined or "blocked" in combined.lower()


def test_train_impact_fixture_smoke(tmp_path):
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "gravity_ml.impact.train_impact",
            "--league",
            "ncaab_mens",
            "--fixture",
            "--out",
            str(tmp_path),
            "--version",
            "0.0.1-ci",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    bundle = tmp_path / "gravity_athlete_ncaab_mens_impact_v2" / "0.0.1-ci"
    assert (bundle / "apm_betas.csv").exists()
    assert (bundle / "metrics.json").exists()


def test_banned_sources_list_covers_m3_m4_m5():
    for src in (
        "athlete_gravity_scores",
        "raw_composite_score",
        "component_proxy_raw",
        "compute_win_impact_score_v0",
        "compute_target_impact_score",
    ):
        with pytest.raises(PromotionRefused):
            assert_label_source_allowed(src)
