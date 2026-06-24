"""Main feature engineering engine — builds BPXVR snapshot from raw inputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from gravity_api.feature_engineering.composites import (
    blend_proof_with_recruiting_prior,
    compute_achievement_density,
    compute_performance_index,
    compute_recruiting_signal,
)
from gravity_api.feature_engineering.positions import cohort_key, derive_position_group
from gravity_api.feature_engineering.profile_card import build_profile_card, build_proof_profile_card
from gravity_api.feature_engineering.sport_specs import get_sport_spec
from gravity_api.feature_engineering.trajectory import classify_trajectory, stability_score
from gravity_api.feature_engineering.transforms import log1p_safe, percentile_rank, tier_from_percentile
from gravity_api.feature_engineering.types import (
    AthleteFeatureSnapshot,
    ComponentFeatureBlock,
    CohortBaseline,
    ProfileCard,
)


def _extract_float(raw: dict[str, Any], key: str) -> float | None:
    val = raw.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _metric_history(raw: dict[str, Any], key: str) -> list[float]:
    hist = raw.get(f"{key}_history") or raw.get("history", {}).get(key)
    if not isinstance(hist, list):
        return []
    out: list[float] = []
    for v in hist:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def _build_component_block(
    metrics_specs,
    raw: dict[str, Any],
    baselines: dict[str, CohortBaseline],
    *,
    league: str,
    sport: str,
    position_group: str,
    season_year: int,
    risk_mode: bool = False,
) -> ComponentFeatureBlock:
    block = ComponentFeatureBlock(component=metrics_specs[0].component if metrics_specs else "unknown")
    for spec in metrics_specs:
        raw_key = spec.level_raw_key or spec.metric_key.split(".")[-1]
        value = _extract_float(raw, raw_key)
        if spec.log_transform and value is not None:
            value = log1p_safe(value)
        history = _metric_history(raw, raw_key)
        if value is not None and not history:
            history = [value]

        baseline = baselines.get(f"{spec.metric_key}:primary")
        cohort_vals = raw.get(f"cohort_{raw_key}_values")
        if isinstance(cohort_vals, list):
            cohort_vals = [float(v) for v in cohort_vals]
        else:
            cohort_vals = []

        prior_pctile = None
        if len(history) >= 2 and cohort_vals:
            prior_pctile = percentile_rank(cohort_vals, history[-2])

        card = build_profile_card(
            spec=spec,
            current_value=value,
            history=history,
            baseline=baseline,
            cohort_values=cohort_vals,
            prior_pctile=prior_pctile,
            confidence=float(raw.get(f"{raw_key}_confidence", 1.0)),
            risk_mode=risk_mode,
        )
        block.profile_cards[spec.metric_key] = card

    return block


class FeatureEngineeringEngine:
    """Builds full BPXVR athlete feature snapshot from normalized raw payload."""

    def build_snapshot(
        self,
        *,
        entity_id: str,
        sport: str,
        position: str | None,
        season_year: int,
        raw: dict[str, Any],
        baselines: dict[str, CohortBaseline] | None = None,
        as_of: datetime | None = None,
    ) -> AthleteFeatureSnapshot:
        spec = get_sport_spec(sport)
        baselines = baselines or {}
        position_group = derive_position_group(position, sport) or "UNKNOWN"
        as_of = as_of or datetime.now(tz=timezone.utc)

        pos_spec = next((p for p in spec.position_groups if p.position_group == position_group), None)
        from gravity_api.scrapers.parsers.stat_normalizer import flatten_raw_for_stats

        flat_stats = flatten_raw_for_stats(raw, sport)
        season_stats = flat_stats or {
            k: v for k, v in raw.items() if isinstance(v, (int, float))
        }
        cohort_means = raw.get("cohort_stat_means", {})
        cohort_stds = raw.get("cohort_stat_stds", {})

        perf_index = None
        if pos_spec:
            perf_index = compute_performance_index(
                sport=sport,
                position_group=position_group,
                season_stats=season_stats,
                cohort_means=cohort_means,
                cohort_stds=cohort_stds,
            )

        index_history = _metric_history(raw, "proof.performance_index")
        if perf_index is not None:
            index_history = index_history + [perf_index] if not index_history else index_history[:-1] + [perf_index]

        cohort_index_values = raw.get("cohort_performance_index_values") or []
        if isinstance(cohort_index_values, list):
            cohort_index_values = [float(v) for v in cohort_index_values]

        games_played = int(raw.get("games_played_season") or 0)
        proof_card = build_proof_profile_card(
            performance_index=perf_index,
            index_history=index_history,
            cohort_index_values=cohort_index_values,
            prior_index_pctile=raw.get("proof.performance_index_pctile_prior"),
            games_played=games_played,
            min_games=spec.min_games_for_proof_pctile,
        )

        recruiting_signal = compute_recruiting_signal(raw, pos_spec.recruiting_stats if pos_spec else ())
        recruiting_pctile = raw.get("recruiting_pctile")
        if recruiting_pctile is not None:
            recruiting_pctile = float(recruiting_pctile)

        blended_pctile = blend_proof_with_recruiting_prior(
            proof_card.level_pctile,
            recruiting_pctile,
            games_played,
            pos_spec.expected_games if pos_spec else 1,
        )

        proof_block = ComponentFeatureBlock(component="proof")
        proof_block.profile_cards["proof.performance_index"] = proof_card
        proof_block.composite_index = perf_index
        proof_block.composite_pctile = blended_pctile or proof_card.level_pctile
        proof_block.composite_tier = tier_from_percentile(proof_block.composite_pctile)
        proof_block.trajectory_class = proof_card.trajectory_class
        proof_block.volatility_score = proof_card.stability_score

        if recruiting_signal is not None:
            proof_block.profile_cards["proof.recruiting_signal"] = ProfileCard(
                metric_key="proof.recruiting_signal",
                level_raw=recruiting_signal,
                level_pctile=recruiting_pctile,
                level_tier=tier_from_percentile(recruiting_pctile),
            )

        achievements = raw.get("achievements") or []
        if isinstance(achievements, list) and pos_spec:
            ach_density = compute_achievement_density(achievements, pos_spec.achievement_weights)
            proof_block.profile_cards["proof.achievement_density"] = ProfileCard(
                metric_key="proof.achievement_density",
                level_raw=ach_density,
            )

        brand_block = _build_component_block(
            spec.brand_metrics, raw, baselines,
            league=spec.league, sport=sport, position_group=position_group, season_year=season_year,
        )
        brand_block.component = "brand"

        proximity_block = _build_component_block(
            spec.proximity_metrics, raw, baselines,
            league=spec.league, sport=sport, position_group=position_group, season_year=season_year,
        )
        proximity_block.component = "proximity"

        velocity_block = _build_component_block(
            spec.velocity_metrics, raw, baselines,
            league=spec.league, sport=sport, position_group=position_group, season_year=season_year,
        )
        velocity_block.component = "velocity"
        velocity_block.trajectory_class = proof_card.trajectory_class
        if index_history:
            velocity_block.volatility_score = stability_score(index_history)

        risk_block = _build_component_block(
            spec.risk_metrics, raw, baselines,
            league=spec.league, sport=sport, position_group=position_group, season_year=season_year,
            risk_mode=True,
        )
        risk_block.component = "risk"

        college_proof = None
        if spec.college_pro_bridge:
            college_proof = {
                "exit_pctile": raw.get("college.proof_index_pctile_at_exit"),
                "to_pro_delta_pctile": raw.get("college.to_pro_proof_delta"),
                "trajectory_class_at_draft": raw.get("college.proof_trajectory_class"),
                "yoy_final_2yr": raw.get("college.proof_yoy_final_2yr"),
                "archetype": raw.get("college.archetype"),
            }

        missingness: dict[str, bool] = {}
        for block in (brand_block, proof_block, proximity_block, velocity_block, risk_block):
            for key, card in block.profile_cards.items():
                missingness[key] = card.masked

        return AthleteFeatureSnapshot(
            entity_id=entity_id,
            sport=sport,
            league=spec.league,
            position_group=position_group,
            season_year=season_year,
            cohort_key=cohort_key(
                league=spec.league, sport=sport, position_group=position_group, season_year=season_year,
            ),
            as_of=as_of.isoformat(),
            brand=brand_block,
            proof=proof_block,
            proximity=proximity_block,
            velocity=velocity_block,
            risk=risk_block,
            college_proof=college_proof,
            missingness=missingness,
        )
