"""
Stage 1 training targets: composite 0–100 label from observable market signals (Option 1).

Not dollar regression — relative commercial strength proxy for ranking supervision.
"""

from __future__ import annotations

import math
import re
from typing import Any, Mapping

import numpy as np
import pandas as pd

_DEFAULT_WEIGHTS = {
    "nil": 0.28,
    "recruiting": 0.22,
    "social": 0.20,
    "news": 0.12,
    "trends": 0.10,
    "draft": 0.08,
}


def _log1p_safe(x: float) -> float:
    if math.isnan(x) or x < 0:
        return 0.0
    return math.log1p(x)


def _inv_rank(x: float) -> float:
    if math.isnan(x) or x <= 0:
        return 0.0
    return 1.0 / x


def _parse_nil_scalar(val: Any) -> float:
    if val is None or val == "ERROR":
        return math.nan
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(",", "").replace("$", "")
    m = re.search(r"([\d.]+)\s*([kKmM]?)", s)
    if not m:
        return math.nan
    v = float(m.group(1))
    suf = (m.group(2) or "").upper()
    if suf == "K":
        v *= 1_000
    elif suf == "M":
        v *= 1_000_000
    return v


def raw_composite_score(row: Mapping[str, Any]) -> float:
    """Unbounded scalar — higher means stronger commercial signals."""
    w = _DEFAULT_WEIGHTS

    nil_v = _parse_nil_scalar(row.get("nil_valuation"))
    nil_part = _log1p_safe(nil_v) if not math.isnan(nil_v) else 0.0

    rk = float(row.get("recruiting_rank_national") or math.nan)
    rec_part = _inv_rank(rk) * 100.0

    ig = float(row.get("instagram_followers") or 0) or 0.0
    tw = float(row.get("twitter_followers") or 0) or 0.0
    soc_part = _log1p_safe(ig) + 0.7 * _log1p_safe(tw)

    news = float(row.get("news_count_30d") or 0) or 0.0
    news_part = _log1p_safe(news)

    tr = float(row.get("google_trends_score") or 0) or 0.0
    tr_part = max(tr, 0.0)

    draft_txt = row.get("nba_draft_projection") or row.get("wnba_draft_projection")
    d_rank = math.nan
    if draft_txt and draft_txt != "ERROR":
        m = re.search(r"#\s*(\d+)", str(draft_txt))
        if m:
            d_rank = float(m.group(1))
    draft_part = _inv_rank(d_rank) * 50.0 if not math.isnan(d_rank) else 0.0

    return (
        w["nil"] * nil_part
        + w["recruiting"] * rec_part / 10.0
        + w["social"] * soc_part
        + w["news"] * news_part
        + w["trends"] * tr_part / 100.0
        + w["draft"] * draft_part
    )


def composite_labels_0_100(df: pd.DataFrame) -> np.ndarray:
    """Min–max raw composite on this corpus → [0, 100]."""
    raws = np.array(
        [raw_composite_score(r) for r in df.to_dict("records")],
        dtype=np.float64,
    )
    lo, hi = float(raws.min()), float(raws.max())
    if hi - lo < 1e-9:
        return np.full_like(raws, 50.0, dtype=np.float32)
    scaled = (raws - lo) / (hi - lo) * 100.0
    return scaled.astype(np.float32)


def apply_trained_label_scaling(
    row: Mapping[str, Any],
    lo: float,
    hi: float,
) -> float:
    """At inference, reuse training min/max so labels stay comparable."""
    r = raw_composite_score(row)
    if hi - lo < 1e-9:
        return 50.0
    v = (r - lo) / (hi - lo) * 100.0
    return float(max(0.0, min(100.0, v)))


__all__ = [
    "apply_trained_label_scaling",
    "composite_labels_0_100",
    "raw_composite_score",
]
