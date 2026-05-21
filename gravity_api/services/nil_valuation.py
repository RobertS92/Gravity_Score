"""Normalize NIL valuation dollars from scraper/API payloads."""

from __future__ import annotations

import math
import re
from typing import Any, Mapping, Optional


def _coerce_float(val: Any) -> Optional[float]:
    if val is None or val == "" or val == "ERROR":
        return None
    if isinstance(val, (int, float)):
        v = float(val)
        return v if math.isfinite(v) else None
    text = str(val).strip().replace(",", "").replace("$", "")
    if not text:
        return None
    m = re.search(r"([\d.]+)\s*([kKmM]?)", text)
    if not m:
        try:
            return float(text)
        except ValueError:
            return None
    v = float(m.group(1))
    suf = (m.group(2) or "").upper()
    if suf == "K":
        v *= 1_000
    elif suf == "M":
        v *= 1_000_000
    elif "illion" in text.lower():
        v *= 1_000_000
    return v


def elite_signal_strength(row: Mapping[str, Any]) -> float:
    """0–1 proxy for whether athlete is likely top-tier commercially."""
    stars = _coerce_float(row.get("recruiting_stars")) or 0.0
    ig = _coerce_float(row.get("instagram_followers")) or 0.0
    tw = _coerce_float(row.get("twitter_followers")) or 0.0
    tt = _coerce_float(row.get("tiktok_followers")) or 0.0
    trends = _coerce_float(row.get("google_trends_score")) or 0.0
    social = ig + tw + tt
    score = 0.0
    if stars >= 4:
        score += 0.35
    elif stars >= 3:
        score += 0.15
    if social >= 1_000_000:
        score += 0.45
    elif social >= 250_000:
        score += 0.30
    elif social >= 75_000:
        score += 0.15
    if trends >= 70:
        score += 0.20
    return min(1.0, score)


def sanitize_nil_valuation_usd(
    val: Any,
    row: Optional[Mapping[str, Any]] = None,
) -> Optional[float]:
    """
    Return NIL valuation in USD.

    Fixes common scraper under-scale: elite athletes stored with raw numbers in
    the 10k–500k band that represent thousands-of-dollars or truncated On3 values
    (e.g. 21866 → ~$21.9M when social/recruiting signals are elite).
    """
    v = _coerce_float(val)
    if v is None or v <= 0:
        return None

    ctx = row or {}
    elite = elite_signal_strength(ctx)

    if 5_000 <= v < 500_000 and elite >= 0.55:
        scaled = v * 1_000
        if 500_000 <= scaled <= 50_000_000:
            return scaled

    if v < 50_000 and elite >= 0.70:
        return max(v, 250_000.0)

    return v


def nil_from_row(row: Mapping[str, Any]) -> Optional[float]:
    """Best-effort NIL USD from a raw_data or athlete dict."""
    for key in ("nil_valuation", "nil_valuation_raw", "verified_nil_amount_usd"):
        v = sanitize_nil_valuation_usd(row.get(key), row)
        if v is not None and v > 0:
            return v
    return None
