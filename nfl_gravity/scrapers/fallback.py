"""LLM fallback helpers for messy markup extraction."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, Optional

LOGGER = logging.getLogger("nfl_gravity.scrapers.fallback")


def call_llm(prompt: str) -> str:
    """Call an LLM to extract structured data.

    This function intentionally keeps its implementation lightweight so it can be
    monkeypatched during tests. In production, configure it to call a Mistral HF
    endpoint or a locally hosted model that returns JSON.
    """

    raise RuntimeError("LLM backend not configured")


def extract_with_llm(html: str, fields: Iterable[str], prompt_template: Optional[str] = None) -> Dict[str, Any]:
    """Use a language model to extract specific keys from an HTML snippet."""

    if not fields:
        return {}

    template = prompt_template or (
        "You are an information extraction assistant. "
        "Given the following HTML snippet, return a JSON object with the requested fields. "
        "If a field is missing, use null. Only return valid JSON.\n\n"
        "Fields: {fields}\nHTML:\n{html}"
    )
    prompt = template.format(fields=", ".join(fields), html=html)
    try:
        response = call_llm(prompt)
    except Exception as exc:
        LOGGER.warning("LLM extraction failed: %s", exc)
        return {}

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        LOGGER.warning("LLM returned non-JSON payload: %s", response)
        return {}

    return {field: parsed.get(field) for field in fields}


__all__ = ["extract_with_llm", "call_llm"]
