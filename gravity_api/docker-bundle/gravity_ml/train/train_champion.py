"""Train and export champion model bundles."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from gravity_ml.inference.predict import model_key
from gravity_ml.train.dataset import chronological_split, rows_to_xy
from gravity_ml.train.regressor import train_regressor

logger = logging.getLogger(__name__)

OBJECTIVES = ("value", "quality", "team_value", "team_quality", "brand_sponsor")


def _default_target(objective: str, league: str) -> str:
    if objective == "value":
        return "nil_valuation_usd" if league == "ncaa" else "contract_guaranteed_usd"
    if objective == "quality":
        return "quality_score"
    if objective in ("team_value", "team_quality"):
        return "team_gravity_proxy"
    return "brand_gravity_proxy"


def train_model(
    X: np.ndarray,
    y: np.ndarray,
    sample_weight: np.ndarray | None = None,
):
    return train_regressor(X, y, sample_weight)


def evaluate_regression(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    if len(y_true) > 2:
        rank_corr = float(np.corrcoef(y_true, y_pred)[0, 1])
    else:
        rank_corr = 0.0
    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "pearson": round(rank_corr, 4)}


def save_bundle(
    out_dir: Path,
    *,
    model: Any,
    vectorizer,
    entity_type: str,
    sport: str,
    objective: str,
    version: str,
    metrics: dict[str, Any],
    row_count: int,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "model.pkl").open("wb") as fh:
        pickle.dump(model, fh)
    (out_dir / "feature_manifest.json").write_text(
        json.dumps(vectorizer.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "model_key": model_key(entity_type, sport, objective) if entity_type != "brand" else "gravity_brand_sponsor_v1",
        "entity_type": entity_type,
        "sport": sport,
        "objective": objective,
        "version": version,
        "trained_at": datetime.now(tz=timezone.utc).isoformat(),
        "row_count": row_count,
    }
    (out_dir / "training_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return out_dir


async def fetch_training_rows(
    entity_type: str,
    sport: str,
    target_key: str,
    *,
    min_rows: int = 30,
) -> list[dict[str, Any]]:
    from gravity_api.config import get_settings
    import asyncpg

    conn = await asyncpg.connect(get_settings().pg_dsn, statement_cache_size=0)
    rows_out: list[dict[str, Any]] = []
    try:
        if entity_type == "athlete":
            rows = await conn.fetch(
                """
                SELECT
                  a.id::text AS entity_id,
                  a.sport,
                  s.calculated_at AS as_of,
                  s.gravity_score,
                  s.brand_score,
                  s.proof_score,
                  s.proximity_score,
                  s.velocity_score,
                  s.risk_score,
                  s.dollar_p50_usd,
                  s.confidence,
                  r.raw_data
                FROM athletes a
                JOIN LATERAL (
                  SELECT * FROM athlete_gravity_scores
                  WHERE athlete_id = a.id ORDER BY calculated_at DESC LIMIT 1
                ) s ON TRUE
                LEFT JOIN LATERAL (
                  SELECT raw_data FROM raw_athlete_data
                  WHERE athlete_id = a.id ORDER BY collected_at DESC LIMIT 1
                ) r ON TRUE
                WHERE a.sport = $1 AND s.gravity_score IS NOT NULL
                LIMIT 10000
                """,
                sport,
            )
            for row in rows:
                raw = dict(row["raw_data"] or {})
                raw.update(
                    {
                        "entity_id": row["entity_id"],
                        "sport": row["sport"],
                        "as_of": row["as_of"].isoformat() if row["as_of"] else None,
                        "gravity_score_prior": float(row["gravity_score"] or 0),
                        "brand_score_prior": float(row["brand_score"] or 0),
                        "proof_score_prior": float(row["proof_score"] or 0),
                        "proof_composite_pctile": float(row["proof_score"] or 0),
                        "quality_score_prior": float(row["proof_score"] or 0),
                    }
                )
                p50 = float(row["dollar_p50_usd"] or 0)
                if target_key == "nil_valuation_usd" and p50 > 0:
                    raw["target"] = math.log1p(p50)
                elif target_key == "quality_score":
                    raw["target"] = float(row["proof_score"] or row["gravity_score"] or 0)
                elif target_key == "contract_guaranteed_usd" and p50 > 0:
                    raw["target"] = math.log1p(p50)
                else:
                    raw["target"] = float(row["gravity_score"] or 0)
                raw["label_weight"] = float(row["confidence"] or 0.5)
                rows_out.append(raw)
        elif entity_type == "team":
            rows = await conn.fetch(
                """
                SELECT gt.id::text AS entity_id, gt.sport, gt.school,
                       AVG(s.gravity_score)::float AS roster_value,
                       AVG(s.velocity_score)::float AS roster_velocity,
                       AVG(100.0 - s.risk_score)::float AS roster_stability,
                       AVG(s.proof_score)::float AS performance
                FROM gravity_teams gt
                LEFT JOIN athletes a ON lower(trim(a.school)) = lower(trim(gt.school)) AND a.sport = gt.sport
                LEFT JOIN LATERAL (
                  SELECT * FROM athlete_gravity_scores WHERE athlete_id = a.id
                  ORDER BY calculated_at DESC LIMIT 1
                ) s ON TRUE
                WHERE gt.sport = $1
                GROUP BY gt.id, gt.sport, gt.school
                """,
                sport,
            )
            for row in rows:
                raw = {
                    "entity_id": row["entity_id"],
                    "sport": row["sport"],
                    "school": row["school"],
                    "roster_value": float(row["roster_value"] or 50),
                    "roster_velocity": float(row["roster_velocity"] or 50),
                    "roster_stability": float(row["roster_stability"] or 50),
                    "performance": float(row["performance"] or 50),
                    "retention": float(row["roster_stability"] or 50),
                    "market_reach": float(row["roster_velocity"] or 50),
                    "target": float(row["roster_value"] or row["performance"] or 50),
                    "label_weight": 0.6,
                }
                rows_out.append(raw)
    finally:
        await conn.close()

    if len(rows_out) < min_rows:
        logger.warning("Only %d rows for %s/%s — need %d", len(rows_out), entity_type, sport, min_rows)
    return rows_out


def train_from_rows(
    rows: list[dict[str, Any]],
    *,
    entity_type: str,
    sport: str,
    objective: str,
    version: str,
    out_root: Path,
) -> Path | None:
    if len(rows) < 30:
        return None
    train_rows, val_rows, test_rows = chronological_split(rows)
    obj = objective.replace("team_", "") if objective.startswith("team_") else objective
    if objective.startswith("team_"):
        obj = objective  # team_value / team_quality use full objective name for manifest exclude
    X_train, y_train, w_train, vectorizer = rows_to_xy(train_rows, objective=obj if obj in OBJECTIVES else objective)
    model = train_model(X_train, y_train, w_train)

    X_val, y_val, _, _ = rows_to_xy(val_rows, objective=obj if obj in OBJECTIVES else objective)
    val_pred = model.predict(X_val)
    metrics = {
        "validation": evaluate_regression(y_val, val_pred),
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "test_rows": len(test_rows),
    }

    mk = model_key(entity_type, sport, objective.replace("team_", "") if entity_type == "team" else objective)
    if entity_type == "team":
        mk = model_key("team", sport, objective.replace("team_", ""))
    out_dir = out_root / mk / version
    save_bundle(
        out_dir,
        model=model,
        vectorizer=vectorizer,
        entity_type=entity_type,
        sport=sport,
        objective=objective.replace("team_", "") if entity_type == "team" else objective,
        version=version,
        metrics=metrics,
        row_count=len(rows),
    )
    logger.info("Saved bundle %s metrics=%s", out_dir, metrics)
    return out_dir


async def main_async(args: argparse.Namespace) -> None:
    league = "ncaa" if args.sport not in ("nfl", "nba", "wnba") else "pro"
    target = args.target_key or _default_target(args.objective, league)
    rows: list[dict[str, Any]] = []
    dsn = os.environ.get("PG_DSN")
    if dsn and not args.allow_synthetic:
        try:
            rows = await fetch_training_rows(args.entity, args.sport, target, min_rows=args.min_rows)
        except Exception as exc:
            logger.warning("DB fetch failed: %s", exc)
    elif dsn:
        try:
            rows = await fetch_training_rows(args.entity, args.sport, target, min_rows=args.min_rows)
        except Exception as exc:
            logger.warning("DB fetch failed, will use synthetic if allowed: %s", exc)

    if len(rows) < args.min_rows and args.allow_synthetic:
        logger.info("Generating synthetic bootstrap rows for %s/%s", args.entity, args.sport)
        rows = _synthetic_rows(args.entity, args.sport, args.objective)
    out = train_from_rows(
        rows,
        entity_type=args.entity,
        sport=args.sport,
        objective=args.objective,
        version=args.version,
        out_root=Path(args.out),
    )
    if out and args.upload_s3:
        from gravity_ml.artifacts.s3 import upload_bundle_dir

        upload_bundle_dir(out)
    if out:
        _write_index(Path(args.out))


def _synthetic_rows(entity: str, sport: str, objective: str) -> list[dict[str, Any]]:
    import random

    random.seed(42)
    rows = []
    for i in range(200):
        raw = {
            "entity_id": f"syn-{i}",
            "sport": sport,
            "as_of": f"2025-{1 + i % 12:02d}-01",
            "instagram_followers": random.randint(1000, 500000),
            "proof_composite_pctile": random.uniform(20, 95),
            "nil_valuation": random.uniform(5000, 2_000_000),
            "data_quality_score": random.uniform(0.4, 0.95),
            "partnership_brand_score": random.uniform(0, 85),
            "news_count_30d": random.randint(0, 40),
            "google_trends_score": random.uniform(30, 90),
        }
        if entity == "team":
            raw.update(
                {
                    "roster_value": random.uniform(40, 90),
                    "performance": random.uniform(40, 90),
                    "market_reach": random.uniform(30, 85),
                    "retention": random.uniform(50, 95),
                }
            )
        g = random.uniform(30, 90)
        raw["target"] = math.log1p(random.uniform(10_000, 500_000)) if "value" in objective else g
        raw["label_weight"] = 0.5
        rows.append(raw)
    return rows


def _write_index(out_root: Path) -> None:
    champions: dict[str, str] = {}
    if not out_root.exists():
        return
    for model_dir in out_root.iterdir():
        if not model_dir.is_dir():
            continue
        versions = sorted((v for v in model_dir.iterdir() if v.is_dir()), key=lambda p: p.name, reverse=True)
        if versions:
            champions[model_dir.name] = versions[0].name
    (out_root / "index.json").write_text(
        json.dumps({"champions": champions, "updated_at": datetime.now(tz=timezone.utc).isoformat()}, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Gravity champion model bundle")
    parser.add_argument("--entity", choices=["athlete", "team", "brand"], default="athlete")
    parser.add_argument("--sport", default="global")
    parser.add_argument("--objective", choices=list(OBJECTIVES), default="value")
    parser.add_argument("--target-key")
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--out", default="models/bundles")
    parser.add_argument("--min-rows", type=int, default=30)
    parser.add_argument("--allow-synthetic", action="store_true", help="Bootstrap with synthetic rows if DB thin")
    parser.add_argument("--upload-s3", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
