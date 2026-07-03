"""Shared cohort-relative display calibration (config-driven knots)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Mapping, Sequence

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "gravity_score_calibration.json"


@lru_cache(maxsize=1)
def load_calibration_config() -> dict:
    if not _CONFIG_PATH.exists():
        return {"global_knots": [], "version": "1.0.0"}
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


def load_calibration_knots() -> list[dict[str, float]]:
    return list(load_calibration_config().get("global_knots") or [])


def cohort_percentile(latent: float, cohort_latents: Sequence[float]) -> float:
    if not cohort_latents:
        return 50.0
    below = sum(1 for x in cohort_latents if x < latent)
    equal = sum(1 for x in cohort_latents if x == latent)
    n = len(cohort_latents)
    return 100.0 * (below + 0.5 * equal) / n


def interpolate_calibration(percentile: float, knots: Sequence[Mapping[str, float]] | None = None) -> float:
    knot_list = list(knots or load_calibration_knots())
    if not knot_list:
        return max(0.0, min(100.0, float(percentile)))

    pct = max(0.0, min(100.0, float(percentile)))
    sorted_knots = sorted(knot_list, key=lambda k: float(k["percentile"]))
    if pct <= float(sorted_knots[0]["percentile"]):
        return float(sorted_knots[0]["score"])
    if pct >= float(sorted_knots[-1]["percentile"]):
        return float(sorted_knots[-1]["score"])

    for i in range(len(sorted_knots) - 1):
        k0, k1 = sorted_knots[i], sorted_knots[i + 1]
        p0, p1 = float(k0["percentile"]), float(k1["percentile"])
        if pct <= p1:
            if p1 <= p0:
                return float(k1["score"])
            t = (pct - p0) / (p1 - p0)
            return float(k0["score"]) + t * (float(k1["score"]) - float(k0["score"]))
    return float(sorted_knots[-1]["score"])


def calibrate_display_score(
    latent: float,
    cohort_latents: Sequence[float] | None,
) -> tuple[float, float]:
    pctile = cohort_percentile(latent, cohort_latents or [])
    display = interpolate_calibration(pctile)
    return round(max(0.0, min(99.0, display)), 4), round(pctile, 4)


__all__ = [
    "calibrate_display_score",
    "cohort_percentile",
    "interpolate_calibration",
    "load_calibration_config",
    "load_calibration_knots",
]
