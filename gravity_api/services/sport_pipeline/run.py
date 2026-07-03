"""End-to-end per-sport athlete pipeline."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

from gravity_api.feature_engineering.engine import FeatureEngineeringEngine
from gravity_api.feature_engineering.materialize import materialize_bpxvr_snapshot
from gravity_api.services.athlete_score_sync import (
    athlete_to_raw_data,
    brand_gravity_score,
    fetch_latest_scraped_raw,
    shap_values_from_ml,
)
from gravity_api.services.score_imputation import (
    apply_heuristic_imputations,
    apply_manual_imputations,
    load_manual_imputations,
)
from gravity_api.services.sport_pipeline.cohort_context import build_cohort_context
from gravity_api.services.sport_pipeline.config import get_sport_pipeline_config
from gravity_api.services.sport_pipeline.metric_history import (
    load_metric_histories,
    sync_metric_history_from_social,
)
from gravity_api.services.sport_pipeline.raw_payload import build_enriched_raw_payload
from gravity_api.services.scoring_stack import finalize_score_metadata
from gravity_api.services.sport_pipeline.score import score_with_sport_model
from gravity_api.services.sport_pipeline.season_stats import upsert_season_stats_from_raw
from gravity_ml.brand.taxonomy import enrich_raw_with_partnerships

logger = logging.getLogger(__name__)


async def run_feature_pipeline(
    conn: asyncpg.Connection,
    athlete_id: str,
) -> dict[str, Any]:
    """Scrape → season stats → metric history → BPXVR snapshot (no ML score)."""
    athlete = await conn.fetchrow("SELECT * FROM athletes WHERE id = $1::uuid", athlete_id)
    if not athlete:
        raise ValueError("Athlete not found")

    sport = str(athlete["sport"])
    pipeline = get_sport_pipeline_config(sport)
    scraped = await fetch_latest_scraped_raw(conn, athlete_id) or {}
    snap = await conn.fetchrow(
        """SELECT * FROM social_snapshots WHERE athlete_id = $1::uuid
           ORDER BY scraped_at DESC LIMIT 1""",
        athlete_id,
    )

    stats_written = await upsert_season_stats_from_raw(
        conn,
        athlete_id=athlete_id,
        sport=sport,
        position=athlete.get("position"),
        raw=scraped,
    )
    history_written = await sync_metric_history_from_social(conn, athlete_id)

    cohort_ctx = await build_cohort_context(
        conn, sport=sport, position=athlete.get("position")
    )
    metric_histories = await load_metric_histories(
        conn,
        athlete_id,
        ("brand.social_reach_total", "brand.instagram_followers"),
    )

    raw = await build_enriched_raw_payload(
        conn, athlete, snap, scraped, cohort_ctx, metric_histories
    )

    engine = FeatureEngineeringEngine()
    snapshot = engine.build_snapshot(
        entity_id=athlete_id,
        sport=sport,
        position=athlete.get("position"),
        season_year=int(cohort_ctx["season_year"]),
        raw=raw,
        baselines=cohort_ctx.get("baselines"),
    )

    try:
        snap_row = await materialize_bpxvr_snapshot(
            conn,
            entity_id=athlete_id,
            sport=sport,
            position=athlete.get("position"),
            season_year=int(cohort_ctx["season_year"]),
            raw=raw,
        )
    except asyncpg.PostgresError as exc:
        logger.warning("BPXVR snapshot persist skipped: %s", exc)
        snap_row = {"features": snapshot.to_dict()}

    return {
        "athlete_id": athlete_id,
        "sport": sport,
        "pipeline": pipeline.model_key,
        "season_stats_written": stats_written,
        "metric_history_written": history_written,
        "position_group": snapshot.position_group,
        "proof_pctile": snapshot.proof.composite_pctile,
        "proof_trajectory": snapshot.proof.trajectory_class.value,
        "feature_snapshot_id": str(snap_row.get("id")) if snap_row.get("id") else None,
        "snapshot": snapshot.to_dict(),
    }


async def run_athlete_pipeline(
    conn: asyncpg.Connection,
    athlete_id: str,
    *,
    score: bool = True,
) -> dict[str, Any]:
    """Full pipeline: features → BPXVR snapshot → sport-specific ML score."""
    feature_result = await run_feature_pipeline(conn, athlete_id)

    if not score:
        return feature_result

    athlete = await conn.fetchrow("SELECT * FROM athletes WHERE id = $1::uuid", athlete_id)
    if not athlete:
        raise ValueError("Athlete not found")

    sport = str(athlete["sport"])
    pipeline = get_sport_pipeline_config(sport)
    scraped = await fetch_latest_scraped_raw(conn, athlete_id) or {}
    snap = await conn.fetchrow(
        """SELECT * FROM social_snapshots WHERE athlete_id = $1::uuid
           ORDER BY scraped_at DESC LIMIT 1""",
        athlete_id,
    )
    cohort_ctx = await build_cohort_context(conn, sport=sport, position=athlete.get("position"))
    metric_histories = await load_metric_histories(
        conn, athlete_id, ("brand.social_reach_total",)
    )
    raw = await build_enriched_raw_payload(
        conn, athlete, snap, scraped, cohort_ctx, metric_histories
    )

    from gravity_api.services.sport_pipeline.raw_stats_sync import (
        apply_ass_enrichment_to_raw,
        enrich_raw_from_athlete_season_stats,
    )

    ass_enrichment = await enrich_raw_from_athlete_season_stats(conn, athlete_id, sport)
    raw = apply_ass_enrichment_to_raw(raw, ass_enrichment)

    manual = await load_manual_imputations(conn, athlete_id)
    apply_manual_imputations(raw, manual)
    apply_heuristic_imputations(raw, athlete)
    raw = enrich_raw_with_partnerships(raw)

    if sport == "cfb":
        from gravity_api.services.team_season_records import enrich_raw_with_team_season

        raw = await enrich_raw_with_team_season(
            conn,
            athlete_id=athlete_id,
            sport=sport,
            team_name=athlete.get("school") or raw.get("school"),
            season_year=int(cohort_ctx["season_year"]),
            raw=raw,
        )

    commercial_viability: dict[str, Any] | None = None
    from gravity_api.services.commercial_viability import (
        COLLEGE_COMMERCIAL_SPORTS,
        compute_college_commercial_viability,
    )

    from gravity_api.services.llm_gap_fill import (
        is_llm_gap_fill_candidate,
        llm_estimate_nil_commercial,
    )
    from gravity_api.services.scoring_stack import overlay_commercial_viability

    llm_fields: dict[str, Any] = {}
    if is_llm_gap_fill_candidate(raw, sport):
        llm_fields = await llm_estimate_nil_commercial(
            name=str(athlete.get("name") or ""),
            sport=sport,
            school=athlete.get("school"),
            position=athlete.get("position"),
            raw=raw,
        )
        if llm_fields:
            raw.update({k: v for k, v in llm_fields.items() if v is not None})
            from gravity_api.scrapers.observations import merge_raw_athlete_data

            await merge_raw_athlete_data(conn, athlete_id=athlete_id, fields=llm_fields)

    if sport in COLLEGE_COMMERCIAL_SPORTS:
        commercial_viability = await compute_college_commercial_viability(
            conn, athlete_id, sport, raw
        )
        raw.update(
            {
                "commercial_viability_index": commercial_viability["commercial_viability_index"],
                "commercial_viability_score": commercial_viability["commercial_viability_score"],
                "nil_signal_source": commercial_viability["nil_signal_source"],
                "nil_dollar_p10_usd": commercial_viability["nil_dollar_p10"],
                "nil_dollar_p50_usd": commercial_viability["nil_dollar_p50"],
                "nil_dollar_p90_usd": commercial_viability["nil_dollar_p90"],
            }
        )
        from gravity_api.scrapers.observations import merge_raw_athlete_data

        await merge_raw_athlete_data(
            conn,
            athlete_id=athlete_id,
            fields={
                "commercial_viability_index": commercial_viability["commercial_viability_index"],
                "commercial_viability_score": commercial_viability["commercial_viability_score"],
                "nil_signal_source": commercial_viability["nil_signal_source"],
                "nil_dollar_p10_usd": commercial_viability["nil_dollar_p10"],
                "nil_dollar_p50_usd": commercial_viability["nil_dollar_p50"],
                "nil_dollar_p90_usd": commercial_viability["nil_dollar_p90"],
            },
        )

    engine = FeatureEngineeringEngine()
    snapshot = engine.build_snapshot(
        entity_id=athlete_id,
        sport=sport,
        position=athlete.get("position"),
        season_year=int(cohort_ctx["season_year"]),
        raw=raw,
        baselines=cohort_ctx.get("baselines"),
    )

    score_data = await score_with_sport_model(
        conn,
        athlete_id=athlete_id,
        sport=sport,
        raw_data=raw,
        snapshot=snapshot,
        pipeline=pipeline,
    )

    score_data = overlay_commercial_viability(score_data, raw, commercial_viability, sport)
    score_data = finalize_score_metadata(score_data)

    from gravity_api.services.win_impact import merge_win_impact_into_raw

    raw = merge_win_impact_into_raw(raw, snapshot=snapshot, sport=sport)
    score_data["win_impact_score"] = raw.get("win_impact_score")
    score_data["participation_index"] = raw.get("participation_index")

    from gravity_api.scrapers.observations import merge_raw_athlete_data

    await merge_raw_athlete_data(
        conn,
        athlete_id=athlete_id,
        fields={
            k: raw[k]
            for k in (
                "win_impact_score",
                "win_impact_score_v0",
                "participation_index",
                "gs_rate",
                "team_wins",
                "team_losses",
                "team_win_pct",
                "team_win_pct_percentile",
                "proof_residual_team",
                "proof_x_participation",
                "proof_x_weak_team",
                "impact_confidence",
            )
            if raw.get(k) is not None
        },
    )

    await _persist_score_row(conn, athlete, score_data, raw, manual, pipeline.model_key)
    feature_result["score"] = {
        "gravity_score": score_data.get("gravity_score"),
        "model_key": score_data.get("model_key"),
        "model_version": score_data.get("model_version"),
        "fallback_used": score_data.get("fallback_used", False),
        "fallback_kind": score_data.get("fallback_kind"),
        "score_tier": score_data.get("score_tier"),
        "win_impact_score": score_data.get("win_impact_score"),
    }
    return feature_result


async def _persist_score_row(
    conn: asyncpg.Connection,
    athlete: asyncpg.Record,
    score_data: dict[str, Any],
    raw: dict[str, Any],
    manual_fields: list[str],
    model_key: str,
) -> None:
    brand = float(score_data.get("brand_score") or 0)
    vel = float(score_data.get("velocity_score") or 0)
    proof = float(score_data.get("proof_score") or 0)
    brand_g = score_data.get("brand_gravity_score")
    if brand_g is None:
        brand_g = brand_gravity_score(brand, vel, proof)

    shap = shap_values_from_ml(score_data)
    heuristic_imputed = score_data.get("imputed_fields_heuristic") or []
    imputed = {"manual": manual_fields, "heuristic": heuristic_imputed}
    dq = raw.get("data_quality_score")
    dollar_conf = dict(score_data.get("dollar_confidence") or {})
    if score_data.get("score_tier") is not None:
        dollar_conf["score_tier"] = score_data.get("score_tier")
    if score_data.get("fallback_kind"):
        dollar_conf["fallback_kind"] = score_data.get("fallback_kind")
    if score_data.get("replaced_model_version"):
        dollar_conf["replaced_model_version"] = score_data.get("replaced_model_version")
    if score_data.get("win_impact_score") is not None:
        dollar_conf["win_impact_score"] = score_data.get("win_impact_score")
    if score_data.get("participation_index") is not None:
        dollar_conf["participation_index"] = score_data.get("participation_index")
    if score_data.get("gravity_score_latent") is not None:
        dollar_conf["gravity_score_latent"] = score_data.get("gravity_score_latent")
    if score_data.get("gravity_cohort_percentile") is not None:
        dollar_conf["gravity_cohort_percentile"] = score_data.get("gravity_cohort_percentile")

    params = (
        athlete["id"],
        float(score_data["gravity_score"]),
        brand,
        proof,
        float(score_data.get("proximity_score") or 0),
        vel,
        float(score_data.get("risk_score") or 0),
        float(score_data.get("confidence") or 0.5),
        str(score_data.get("model_version") or model_key),
        score_data.get("dollar_p10_usd"),
        score_data.get("dollar_p50_usd"),
        score_data.get("dollar_p90_usd"),
        json.dumps(dollar_conf),
        None,
        float(brand_g),
        json.dumps(shap or {}),
        json.dumps(imputed),
        float(dq) if dq is not None else None,
    )

    updated = await conn.execute(
        """UPDATE athlete_gravity_scores SET
            gravity_score = $2, brand_score = $3, proof_score = $4,
            proximity_score = $5, velocity_score = $6, risk_score = $7,
            confidence = $8, model_version = $9,
            dollar_p10_usd = $10, dollar_p50_usd = $11, dollar_p90_usd = $12,
            dollar_confidence = $13::jsonb, company_gravity_score = $14,
            brand_gravity_score = $15, shap_values = $16::jsonb,
            imputed_fields = $17::jsonb, effective_data_quality = $18,
            calculated_at = NOW()
           WHERE athlete_id = $1""",
        *params,
    )
    if updated.split()[-1] == "0":
        await conn.execute(
            """INSERT INTO athlete_gravity_scores (
                athlete_id, gravity_score, brand_score, proof_score, proximity_score,
                velocity_score, risk_score, confidence, model_version,
                dollar_p10_usd, dollar_p50_usd, dollar_p90_usd, dollar_confidence,
                company_gravity_score, brand_gravity_score, shap_values,
                imputed_fields, effective_data_quality
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::jsonb,$14,$15,$16::jsonb,$17::jsonb,$18)""",
            *params,
        )

    try:
        await conn.execute(
            """UPDATE athlete_gravity_scores SET
                 quality_score = $2,
                 partnership_brand_score = $3,
                 partnership_top_brands = $4::jsonb
               WHERE athlete_id = $1""",
            athlete["id"],
            score_data.get("quality_score"),
            score_data.get("partnership_brand_score"),
            json.dumps(score_data.get("partnership_top_brands") or []),
        )
    except asyncpg.PostgresError:
        logger.debug("quality/partnership columns not available yet", exc_info=True)

    try:
        await conn.execute(
            """INSERT INTO gravity_predictions (
                 entity_type, entity_id, model_key, model_version, as_of,
                 gravity_score, component_scores, predictions, intervals,
                 confidence, data_quality_score, fallback_used, metadata
               ) VALUES (
                 'athlete', $1::uuid, $2, $3, $4, $5, $6::jsonb, '{}'::jsonb, '{}'::jsonb,
                 $7, $8, $9, $10::jsonb
               )""",
            athlete["id"],
            model_key,
            str(score_data.get("model_version") or "unknown"),
            datetime.now(tz=timezone.utc),
            score_data.get("gravity_score"),
            json.dumps({
                "brand": score_data.get("brand_score"),
                "proof": score_data.get("proof_score"),
                "proximity": score_data.get("proximity_score"),
                "velocity": score_data.get("velocity_score"),
                "risk": score_data.get("risk_score"),
                "quality": score_data.get("quality_score"),
            }),
            float(score_data.get("confidence") or 0),
            float(dq or 0),
            bool(score_data.get("fallback_used")),
            json.dumps({
                "pipeline": "sport_pipeline",
                "sport": athlete["sport"],
                "score_tier": score_data.get("score_tier"),
                "fallback_kind": score_data.get("fallback_kind"),
            }),
        )
    except asyncpg.PostgresError:
        logger.debug("gravity_predictions insert skipped", exc_info=True)
