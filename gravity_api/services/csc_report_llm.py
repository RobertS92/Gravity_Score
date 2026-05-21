"""Anthropic-backed prose generator for CSC report sections.

Each generator returns a tuple of (text, source):
  - `source = "llm"` when Claude produced and validated copy.
  - `source = "template"` when we fell back to the caller-supplied
    deterministic template (LLM unavailable, validation failed, or env flag
    disabled the integration).

All callers MUST provide a deterministic fallback. The builder never ships
empty prose — a failed LLM call simply yields the fallback unchanged.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

try:
    from anthropic import AsyncAnthropic
except ImportError:  # pragma: no cover - exercised in dev envs without the SDK
    AsyncAnthropic = None  # type: ignore[assignment]

from gravity_api.config import get_settings
from gravity_api.services.csc_report_prompts import FORBIDDEN_PROSE_TERMS, get_prompt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LlmResult:
    text: str
    source: str  # "llm" | "template"


_DECIMAL_LEAK_PATTERN = re.compile(r"\b\d+\.\d+\b")
_BRACE_LEAK_PATTERN = re.compile(r"[\{\}]")


def _llm_enabled() -> bool:
    raw = (os.environ.get("CSC_REPORT_LLM_ENABLED") or "").strip().lower()
    if raw in ("0", "false", "off", "no"):
        return False
    # Default ON when an Anthropic key is configured. Off otherwise.
    settings = get_settings()
    return bool(settings.anthropic_api_key) and AsyncAnthropic is not None


def validate_prose(
    text: str,
    *,
    surface: str,
    min_sentences: int = 1,
    max_sentences: int = 6,
    max_words: int | None = None,
) -> tuple[bool, Optional[str]]:
    """Return (ok, reason).

    Enforces the forbidden-terms list, basic length bounds, no JSON braces,
    no decimal-score leaks. The validator returns a reason on failure so the
    caller can log it.
    """
    stripped = (text or "").strip()
    if not stripped:
        return False, "empty"
    lowered = stripped.lower()
    for term in FORBIDDEN_PROSE_TERMS:
        if term.lower() in lowered:
            return False, f"forbidden_term:{term}"
    if _DECIMAL_LEAK_PATTERN.search(stripped):
        return False, "decimal_score_leak"
    if _BRACE_LEAK_PATTERN.search(stripped):
        return False, "json_brace_leak"
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", stripped) if s.strip()]
    if len(sentences) < min_sentences:
        return False, f"too_few_sentences:{len(sentences)}<{min_sentences}"
    if len(sentences) > max_sentences:
        return False, f"too_many_sentences:{len(sentences)}>{max_sentences}"
    if max_words is not None:
        word_count = len(stripped.split())
        if word_count > max_words:
            return False, f"too_many_words:{word_count}>{max_words}"
    return True, None


async def _call_anthropic(
    *,
    prompt: str,
    max_tokens: int = 600,
    temperature: float = 0.2,
    timeout_s: float = 12.0,
    retries: int = 1,
) -> Optional[str]:
    """Call Claude and return the message text. None on error.

    Retries the call once with a tight timeout; never raises so the caller
    can fall back to deterministic templates transparently.
    """
    settings = get_settings()
    if not settings.anthropic_api_key or AsyncAnthropic is None:
        return None
    client = AsyncAnthropic(
        api_key=settings.anthropic_api_key, timeout=timeout_s
    )
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            chunks = []
            for block in response.content or []:
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    chunks.append(text)
            return "".join(chunks).strip() or None
        except Exception as exc:  # pragma: no cover - external service
            last_error = exc
            logger.warning(
                "Anthropic call failed (attempt %d/%d): %s",
                attempt + 1,
                retries + 1,
                exc,
            )
            await asyncio.sleep(0.4)
    logger.error("Anthropic call exhausted retries: %s", last_error)
    return None


async def generate_prose(
    *,
    surface: str,
    prompt_inputs: dict[str, Any],
    fallback: str,
    min_sentences: int = 1,
    max_sentences: int = 6,
    max_words: int | None = None,
) -> LlmResult:
    """Generate prose for a single surface; fall back to template on failure."""
    if not _llm_enabled():
        return LlmResult(text=fallback, source="template")
    try:
        template = get_prompt(surface)
    except KeyError:
        logger.error("Unknown prose surface: %s", surface)
        return LlmResult(text=fallback, source="template")
    # `inputs_json` is the canonical key for the executive_summary prompt;
    # other prompts use named placeholders.
    safe_inputs = {**prompt_inputs}
    if "inputs_json" not in safe_inputs and surface == "executive_summary":
        safe_inputs["inputs_json"] = json.dumps(prompt_inputs, default=str, indent=2)
    try:
        prompt = template.format(**safe_inputs)
    except KeyError as exc:
        logger.error("Prompt missing variable %s for surface=%s", exc, surface)
        return LlmResult(text=fallback, source="template")

    text = await _call_anthropic(prompt=prompt)
    if not text:
        return LlmResult(text=fallback, source="template")
    ok, reason = validate_prose(
        text,
        surface=surface,
        min_sentences=min_sentences,
        max_sentences=max_sentences,
        max_words=max_words,
    )
    if not ok:
        logger.warning("Generated prose failed validation: surface=%s reason=%s", surface, reason)
        return LlmResult(text=fallback, source="template")
    return LlmResult(text=text, source="llm")


async def generate_executive_summary(
    *,
    athlete_name: str,
    benchmark_text: str,
    range_text: str,
    cohort_label: str,
    tier_tag: str,
    confidence_tag: str,
    dominant_driver: str,
    uncertainty_note: str,
    fallback: str,
) -> LlmResult:
    return await generate_prose(
        surface="executive_summary",
        prompt_inputs={
            "athlete_name": athlete_name,
            "benchmark_text": benchmark_text,
            "range_text": range_text,
            "cohort_label": cohort_label,
            "tier_tag": tier_tag,
            "confidence_tag": confidence_tag,
            "dominant_driver": dominant_driver,
            "uncertainty_note": uncertainty_note,
        },
        fallback=fallback,
        min_sentences=3,
        max_sentences=6,
    )


async def generate_driver_explanation(
    *,
    athlete_name: str,
    driver_label: str,
    signal_level: str,
    position_group: str,
    cohort_label: str,
    fallback: str,
) -> LlmResult:
    return await generate_prose(
        surface="driver",
        prompt_inputs={
            "athlete_name": athlete_name,
            "driver_label": driver_label,
            "signal_level": signal_level,
            "position_group": position_group,
            "cohort_label": cohort_label,
        },
        fallback=fallback,
        min_sentences=1,
        max_sentences=2,
    )


async def generate_value_interpretation(
    *,
    athlete_name: str,
    market_context: str,
    comparables_summary: str,
    benchmark_text: str,
    percentile_text: str,
    fallback: str,
) -> LlmResult:
    return await generate_prose(
        surface="value_interpretation",
        prompt_inputs={
            "athlete_name": athlete_name,
            "market_context": market_context,
            "comparables_summary": comparables_summary,
            "benchmark_text": benchmark_text,
            "percentile_text": percentile_text,
        },
        fallback=fallback,
        min_sentences=1,
        max_sentences=2,
    )


async def generate_confidence_rationale(
    *,
    athlete_name: str,
    confidence_level: str,
    causes: str,
    fallback: str,
) -> LlmResult:
    return await generate_prose(
        surface="confidence_rationale",
        prompt_inputs={
            "athlete_name": athlete_name,
            "confidence_level": confidence_level,
            "causes": causes,
        },
        fallback=fallback,
        min_sentences=1,
        max_sentences=1,
        max_words=30,
    )


async def generate_risk_rationale(
    *,
    athlete_name: str,
    risk_level: str,
    position_group: str,
    risk_factors: str,
    fallback: str,
) -> LlmResult:
    return await generate_prose(
        surface="risk_rationale",
        prompt_inputs={
            "athlete_name": athlete_name,
            "risk_level": risk_level,
            "position_group": position_group,
            "risk_factors": risk_factors,
        },
        fallback=fallback,
        min_sentences=1,
        max_sentences=1,
        max_words=30,
    )
