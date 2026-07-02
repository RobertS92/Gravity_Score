"""Compute external on-field quality score from awards/honors (not stat composites)."""

from __future__ import annotations

from typing import Any


def compute_external_quality_score(raw: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """
    Derive a 0–100 quality proxy from awards/honors only.
    Used as ML training label — excludes stat columns used as features.
    """
    components: dict[str, float] = {}
    score = 42.0

    aa = float(raw.get("all_american_count") or 0)
    if aa:
        components["all_american"] = min(30.0, aa * 12.0)
        score += components["all_american"]

    nat = float(raw.get("national_awards_count") or 0)
    if nat:
        components["national_awards"] = min(20.0, nat * 8.0)
        score += components["national_awards"]

    conf = float(raw.get("conference_honors_count") or 0)
    if conf:
        components["conference_honors"] = min(12.0, conf * 4.0)
        score += components["conference_honors"]

    if raw.get("heisman_finalist"):
        components["heisman_finalist"] = 18.0
        score += 18.0

    draft = raw.get("draft_round") or raw.get("nfl_draft_round")
    if draft is not None:
        try:
            rnd = int(float(draft))
            if rnd > 0:
                components["draft_capital"] = max(5.0, 28.0 - (rnd - 1) * 4.0)
                score += components["draft_capital"]
        except (TypeError, ValueError):
            pass

    stars = raw.get("recruiting_stars")
    if stars is not None:
        try:
            s = float(stars)
            if s >= 3:
                components["recruiting"] = (s - 2.0) * 6.0
                score += components["recruiting"]
        except (TypeError, ValueError):
            pass

    score = max(0.0, min(100.0, score))
    return round(score, 4), components


def apply_external_quality_fields(fields: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    """Merge award fields into raw snapshot and attach external_quality_score."""
    merged = dict(raw)
    merged.update(fields)
    score, breakdown = compute_external_quality_score(merged)
    if score > 42.0 or breakdown:
        fields = dict(fields)
        fields["external_quality_score"] = score
        fields["external_quality_score_observed"] = 1
        fields["external_quality_components"] = breakdown
    return fields
