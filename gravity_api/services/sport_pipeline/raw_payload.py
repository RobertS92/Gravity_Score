"""Build ML raw_data payload enriched with BPXVR feature snapshot."""

from __future__ import annotations

from typing import Any, Optional

import asyncpg

from gravity_api.feature_engineering.types import AthleteFeatureSnapshot
from gravity_api.services.athlete_score_sync import athlete_to_raw_data


def flatten_bpxvr_for_ml(snapshot: AthleteFeatureSnapshot) -> dict[str, Any]:
    """Flatten profile cards into ML-friendly scalar fields."""
    flat: dict[str, Any] = {
        "feature_schema_version": "gravity_features_bpxvr_v1",
        "cohort_key": snapshot.cohort_key,
        "position_group": snapshot.position_group,
        "season_year": snapshot.season_year,
    }
    for component in ("brand", "proof", "proximity", "velocity", "risk"):
        block = getattr(snapshot, component)
        prefix = component
        if block.composite_index is not None:
            flat[f"{prefix}_composite_index"] = block.composite_index
        if block.composite_pctile is not None:
            flat[f"{prefix}_composite_pctile"] = block.composite_pctile
        flat[f"{prefix}_composite_tier"] = block.composite_tier.value
        flat[f"{prefix}_trajectory_class"] = block.trajectory_class.value
        if block.volatility_score is not None:
            flat[f"{prefix}_volatility_score"] = block.volatility_score
        for metric_key, card in block.profile_cards.items():
            safe = metric_key.replace(".", "_")
            if card.level_raw is not None:
                flat[f"{safe}_raw"] = card.level_raw
            if card.level_pctile is not None:
                flat[f"{safe}_pctile"] = card.level_pctile
            flat[f"{safe}_tier"] = card.level_tier.value
            if card.delta_yoy_pct is not None:
                flat[f"{safe}_yoy_pct"] = card.delta_yoy_pct
            if card.yoy_percentile_change is not None:
                flat[f"{safe}_yoy_pctile_change"] = card.yoy_percentile_change
            flat[f"{safe}_trajectory"] = card.trajectory_class.value
            if card.stability_score is not None:
                flat[f"{safe}_stability"] = card.stability_score
            flat[f"{safe}_masked"] = card.masked

    if snapshot.college_proof:
        for k, v in snapshot.college_proof.items():
            flat[f"college_proof_{k}"] = v
    return flat


def merge_raw_with_bpxvr(
    base_raw: dict[str, Any],
    snapshot: AthleteFeatureSnapshot,
) -> dict[str, Any]:
    merged = dict(base_raw)
    merged["bpxvr"] = snapshot.to_dict()
    merged.update(flatten_bpxvr_for_ml(snapshot))
    merged["proof_performance_index_pctile"] = snapshot.proof.composite_pctile
    merged["proof_performance_index_tier"] = snapshot.proof.composite_tier.value
    merged["proof_trajectory_class"] = snapshot.proof.trajectory_class.value
    merged["velocity_trajectory_class"] = snapshot.velocity.trajectory_class.value
    return merged


async def build_enriched_raw_payload(
    conn: asyncpg.Connection,
    athlete: asyncpg.Record,
    snap: Optional[asyncpg.Record],
    scraped_raw: dict[str, Any],
    cohort_context: dict[str, Any],
    metric_histories: dict[str, list[float]],
) -> dict[str, Any]:
    raw = athlete_to_raw_data(athlete, snap, scraped_raw=scraped_raw)
    if cohort_context.get("cohort_stat_means"):
        raw["cohort_stat_means"] = cohort_context["cohort_stat_means"]
        raw["cohort_stat_stds"] = cohort_context["cohort_stat_stds"]
        raw["cohort_performance_index_values"] = cohort_context.get(
            "cohort_performance_index_values", []
        )

    for metric_key, values in metric_histories.items():
        safe = metric_key.split(".")[-1]
        raw[f"{safe}_history"] = values

    # Prior-year performance index from season stats history
    prior_rows = await conn.fetch(
        """SELECT season_year, stat_key, stat_value
           FROM athlete_season_stats
           WHERE athlete_id = $1 AND sport = $2
           ORDER BY season_year DESC
           LIMIT 50""",
        athlete["id"],
        athlete["sport"],
    )
    if prior_rows:
        by_season: dict[int, dict[str, float]] = {}
        for r in prior_rows:
            by_season.setdefault(int(r["season_year"]), {})[r["stat_key"]] = float(r["stat_value"])
        seasons = sorted(by_season.keys())
        if len(seasons) >= 2:
            raw["proof.performance_index_history"] = list(by_season.values())  # simplified history

    return raw
