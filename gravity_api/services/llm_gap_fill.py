"""Tier-4 LLM gap-fill for high-value college athletes (capped budget)."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

COLLEGE_SPORTS = frozenset({"cfb", "ncaab_mens", "ncaab_womens"})
_BUDGET_FILE = Path(__file__).resolve().parents[2] / "reports" / "llm_gap_fill_budget.json"


def _llm_enabled() -> bool:
    return os.environ.get("LLM_GAP_FILL_ENABLED", "").strip().lower() in ("1", "true", "yes")


def _max_per_run() -> int:
    try:
        return max(0, int(os.environ.get("LLM_GAP_FILL_MAX_PER_RUN", "50")))
    except ValueError:
        return 50


def _max_per_month() -> int:
    try:
        return max(0, int(os.environ.get("LLM_GAP_FILL_MAX_PER_MONTH", "500")))
    except ValueError:
        return 500


def _llm_model() -> str:
    return (
        os.environ.get("LLM_GAP_FILL_MODEL")
        or os.environ.get("ANTHROPIC_MODEL")
        or "claude-3-5-haiku-20241022"
    ).strip()


def _load_budget() -> dict[str, Any]:
    if not _BUDGET_FILE.exists():
        return {"month": "", "month_count": 0, "run_count": 0}
    try:
        return json.loads(_BUDGET_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"month": "", "month_count": 0, "run_count": 0}


def _save_budget(data: dict[str, Any]) -> None:
    _BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    _BUDGET_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def reset_run_budget() -> None:
    data = _load_budget()
    data["run_count"] = 0
    _save_budget(data)


def _budget_ok() -> bool:
    if not _llm_enabled():
        return False
    month = datetime.now(tz=timezone.utc).strftime("%Y-%m")
    data = _load_budget()
    if data.get("month") != month:
        data = {"month": month, "month_count": 0, "run_count": 0}
    if data.get("month_count", 0) >= _max_per_month():
        return False
    if data.get("run_count", 0) >= _max_per_run():
        return False
    return True


def _record_call() -> None:
    month = datetime.now(tz=timezone.utc).strftime("%Y-%m")
    data = _load_budget()
    if data.get("month") != month:
        data = {"month": month, "month_count": 0, "run_count": 0}
    data["month_count"] = int(data.get("month_count", 0)) + 1
    data["run_count"] = int(data.get("run_count", 0)) + 1
    _save_budget(data)


def _coerce_float(val: Any) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def is_llm_gap_fill_candidate(
    raw: dict[str, Any],
    sport: str,
    *,
    score_confidence: float | None = None,
) -> bool:
    if sport not in COLLEGE_SPORTS:
        return False
    stars = _coerce_float(raw.get("recruiting_stars"))
    nil_rank = _coerce_float(raw.get("nil_rank_national") or raw.get("on3_nil_rank"))
    reach = (
        _coerce_float(raw.get("instagram_followers"))
        + _coerce_float(raw.get("tiktok_followers"))
        + _coerce_float(raw.get("twitter_followers"))
    )
    high_social = reach >= 250_000
    priority = stars >= 4 or nil_rank > 0 or high_social
    if not priority:
        return False
    observed_nil = int(float(raw.get("nil_valuation_observed") or 0)) == 1
    low_conf = (score_confidence or 1.0) < 0.5
    if observed_nil and not low_conf:
        return False
    return True


def _parse_json_blob(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


async def llm_estimate_nil_commercial(
    *,
    name: str,
    sport: str,
    school: str | None,
    position: str | None,
    raw: dict[str, Any],
) -> dict[str, Any]:
    """Return estimated NIL/commercial fields (never observed=1)."""
    if not _budget_ok():
        return {}

    from gravity_api.config import get_settings

    settings = get_settings()
    if not settings.anthropic_api_key:
        return {}

    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        return {}

    prompt = f"""You estimate college athlete NIL commercial value for internal analytics only.
Return ONLY valid JSON with keys:
nil_estimate_usd (number), nil_p10_usd (number), nil_p90_usd (number),
commercial_notes (string, max 120 chars), confidence (0-1 float).

Athlete: {name}
Sport: {sport}
School: {school or 'unknown'}
Position: {position or 'unknown'}
Recruiting stars: {raw.get('recruiting_stars')}
Instagram followers: {raw.get('instagram_followers')}
NIL rank: {raw.get('nil_rank_national') or raw.get('on3_nil_rank')}
Known NIL valuation: {raw.get('nil_valuation') if raw.get('nil_valuation_observed') else 'none observed'}
"""
    client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=45.0)
    try:
        resp = await client.messages.create(
            model=_llm_model(),
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        for block in resp.content:
            if hasattr(block, "text"):
                text += block.text
        parsed = _parse_json_blob(text)
        if not parsed.get("nil_estimate_usd"):
            return {}
        _record_call()
        p50 = float(parsed["nil_estimate_usd"])
        p10 = float(parsed.get("nil_p10_usd") or p50 * 0.6)
        p90 = float(parsed.get("nil_p90_usd") or p50 * 1.8)
        conf = float(parsed.get("confidence") or 0.4)
        return {
            "nil_valuation": p50,
            "nil_valuation_observed": 0,
            "nil_confidence": min(0.55, max(0.25, conf)),
            "nil_valuation_source": "llm_estimate",
            "nil_dollar_p10_usd": p10,
            "nil_dollar_p50_usd": p50,
            "nil_dollar_p90_usd": p90,
            "llm_commercial_notes": str(parsed.get("commercial_notes") or "")[:200],
            "llm_gap_fill_at": datetime.now(tz=timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.warning("LLM gap-fill failed for %s: %s", name, exc)
        return {}


__all__ = [
    "is_llm_gap_fill_candidate",
    "llm_estimate_nil_commercial",
    "reset_run_budget",
]
