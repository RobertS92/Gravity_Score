"""Score key athletes from STORED raw (no re-scrape) to verify cohort baselines.

Builds the BPXVR snapshot exactly like run_feature_pipeline (uses the rebuilt
gravity_cohort_baselines) and scores via score_with_sport_model, which routes
CFB to its champion ML bundle and every other sport to heuristic_gravity_v1.
"""
from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

load_dotenv(".env")
os.environ["SCORING_MODE"] = "local"
os.environ.setdefault("MODEL_BUNDLE_ROOT", os.path.abspath("models/bundles"))

import logging

logging.disable(logging.WARNING)

import asyncpg

from gravity_api.feature_engineering.engine import FeatureEngineeringEngine
from gravity_api.services.athlete_score_sync import fetch_latest_scraped_raw
from gravity_api.services.sport_pipeline.cohort_context import build_cohort_context
from gravity_api.services.sport_pipeline.metric_history import load_metric_histories
from gravity_api.services.sport_pipeline.raw_payload import build_enriched_raw_payload
from gravity_api.services.sport_pipeline.score import score_with_sport_model

TARGETS = [
    ("nfl", "Mahomes"),
    ("nfl", "Courtland Sutton"),
    ("nfl", "Patrick Taylor"),
    ("nba", "LeBron"),
    ("nba", "Jokic"),
    ("wnba", "Clark"),
]


async def score_one(conn, sport: str, name: str) -> None:
    athlete = await conn.fetchrow(
        "SELECT * FROM athletes WHERE sport=$1 AND name ILIKE $2 ORDER BY updated_at DESC LIMIT 1",
        sport,
        f"%{name}%",
    )
    if not athlete:
        print(f"  {name:18s}({sport}): NOT FOUND")
        return
    athlete_id = str(athlete["id"])
    scraped = await fetch_latest_scraped_raw(conn, athlete_id) or {}
    snap = await conn.fetchrow(
        "SELECT * FROM social_snapshots WHERE athlete_id=$1::uuid ORDER BY scraped_at DESC LIMIT 1",
        athlete_id,
    )
    cohort_ctx = await build_cohort_context(conn, sport=sport, position=athlete.get("position"))
    metric_histories = await load_metric_histories(
        conn, athlete_id, ("brand.social_reach_total", "brand.instagram_followers")
    )
    raw = await build_enriched_raw_payload(conn, athlete, snap, scraped, cohort_ctx, metric_histories)

    engine = FeatureEngineeringEngine()
    snapshot = engine.build_snapshot(
        entity_id=athlete_id,
        sport=sport,
        position=athlete.get("position"),
        season_year=int(cohort_ctx["season_year"]),
        raw=raw,
        baselines=cohort_ctx.get("baselines"),
    )
    score = await score_with_sport_model(
        conn, athlete_id=athlete_id, sport=sport, raw_data=raw, snapshot=snapshot
    )
    comp = score.get("components") or {}
    print(
        f"  {name:18s}({sport}/{athlete.get('position')}/{snapshot.position_group}): "
        f"gravity={score.get('gravity_score')} "
        f"proof={comp.get('proof')} brand={comp.get('brand')} prox={comp.get('proximity')} "
        f"vel={comp.get('velocity')} risk={comp.get('risk')} "
        f"proof_pctile={snapshot.proof.composite_pctile} model={score.get('model_key')} "
        f"fallback={score.get('fallback_used')}"
    )


async def main() -> None:
    conn = await asyncpg.connect(os.environ["PG_DSN"], command_timeout=120, statement_cache_size=0)
    try:
        for sport, name in TARGETS:
            try:
                await score_one(conn, sport, name)
            except Exception as exc:  # noqa: BLE001
                print(f"  {name:18s}({sport}): ERR {type(exc).__name__}: {exc}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
