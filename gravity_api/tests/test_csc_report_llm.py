"""Validation tests for the CSC report LLM prose service."""

from __future__ import annotations

import asyncio

from gravity_api.services.csc_report_llm import (
    LlmResult,
    generate_prose,
    validate_prose,
)


def test_validate_prose_accepts_clean_short_prose():
    ok, reason = validate_prose(
        "Rocco Becht's brand strength outpaces conference peers. Recent deal activity is sparse.",
        surface="executive_summary",
        min_sentences=1,
        max_sentences=6,
    )
    assert ok is True
    assert reason is None


def test_validate_prose_rejects_forbidden_term():
    ok, reason = validate_prose(
        "Rocco Becht's BPXVR model shows strong brand.",
        surface="executive_summary",
        min_sentences=1,
        max_sentences=4,
    )
    assert ok is False
    assert reason and reason.startswith("forbidden_term")


def test_validate_prose_rejects_decimal_score_leak():
    ok, reason = validate_prose(
        "Brand score of 81.2 leads.",
        surface="driver",
        min_sentences=1,
        max_sentences=2,
    )
    assert ok is False
    assert reason == "decimal_score_leak"


def test_validate_prose_rejects_empty():
    ok, reason = validate_prose("", surface="driver")
    assert ok is False
    assert reason == "empty"


def test_validate_prose_rejects_too_many_sentences():
    text = ". ".join(["A"] * 8) + "."
    ok, reason = validate_prose(text, surface="exec_summary", max_sentences=4)
    assert ok is False
    assert reason and reason.startswith("too_many_sentences")


def test_validate_prose_rejects_brace_leak():
    ok, reason = validate_prose(
        "Output prose with stray { brace.",
        surface="driver",
        max_sentences=4,
    )
    assert ok is False
    # Either bucket is acceptable; both fire for brace leakage.
    assert reason in {"json_brace_leak", "forbidden_term:{", "forbidden_term:}"}


def test_validate_prose_enforces_max_words():
    long_text = " ".join(["word"] * 50)
    ok, reason = validate_prose(
        long_text + ".",
        surface="confidence_rationale",
        min_sentences=1,
        max_sentences=1,
        max_words=25,
    )
    assert ok is False
    assert reason and reason.startswith("too_many_words")


def test_generate_prose_falls_back_when_llm_disabled(monkeypatch):
    monkeypatch.setenv("CSC_REPORT_LLM_ENABLED", "0")
    result = asyncio.run(
        generate_prose(
            surface="driver",
            prompt_inputs={
                "driver_label": "Brand Strength",
                "signal_level": "High",
                "athlete_name": "Rocco Becht",
                "position_group": "QB",
                "cohort_label": "Big 12 QBs",
            },
            fallback="Brand Strength is High relative to Big 12 QBs.",
        )
    )
    assert isinstance(result, LlmResult)
    assert result.source == "template"
    assert result.text == "Brand Strength is High relative to Big 12 QBs."


def test_generate_prose_falls_back_on_unknown_surface(monkeypatch):
    monkeypatch.setenv("CSC_REPORT_LLM_ENABLED", "1")
    result = asyncio.run(
        generate_prose(
            surface="nonexistent_surface",
            prompt_inputs={},
            fallback="deterministic copy",
        )
    )
    assert result.source == "template"
    assert result.text == "deterministic copy"
