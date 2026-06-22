"""Bootstrap ML: train initial bundles, optional S3 upload, register candidates."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SPORTS = (
    "cfb",
    "ncaab_mens",
    "ncaab_womens",
    "ncaa_baseball",
    "ncaa_volleyball",
    "nfl",
    "nba",
    "wnba",
)


def _run_train(entity: str, sport: str, objective: str, out: str, *, synthetic: bool, upload: bool) -> bool:
    cmd = [
        sys.executable,
        "-m",
        "gravity_ml.train.train_champion",
        "--entity",
        entity,
        "--sport",
        sport,
        "--objective",
        objective,
        "--out",
        out,
        "--version",
        "1.0.0",
    ]
    if synthetic:
        cmd.append("--allow-synthetic")
    if upload:
        cmd.append("--upload-s3")
    logger.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, env={**os.environ, "PYTHONPATH": "."})
    return result.returncode == 0


async def register_bundles(out_root: Path, stage: str = "candidate") -> int:
    from gravity_api.config import get_settings
    import asyncpg

    index_path = out_root / "index.json"
    if not index_path.exists():
        return 0
    index = json.loads(index_path.read_text(encoding="utf-8"))
    champions = index.get("champions") or {}
    conn = await asyncpg.connect(get_settings().pg_dsn, statement_cache_size=0)
    count = 0
    try:
        for model_key, version in champions.items():
            bundle_dir = out_root / model_key / version
            metrics_path = bundle_dir / "metrics.json"
            manifest_path = bundle_dir / "training_manifest.json"
            metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
            manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
            artifact_uri = os.environ.get("MODEL_S3_BUCKET")
            if artifact_uri:
                prefix = os.environ.get("MODEL_S3_PREFIX", "gravity-models")
                artifact_uri = f"s3://{artifact_uri}/{prefix}/{model_key}/{version}/"
            else:
                artifact_uri = str(bundle_dir.resolve())

            entity_type = manifest.get("entity_type", "athlete")
            await conn.execute(
                """
                INSERT INTO gravity_model_registry (
                  model_key, model_version, entity_type, stage,
                  artifact_uri, feature_schema_version, target_schema_version,
                  trained_at, metrics, config
                ) VALUES ($1, $2, $3, $4, $5, 'gravity_features_bpxvr_v1', 'auto', NOW(), $6::jsonb, $7::jsonb)
                ON CONFLICT (model_key, model_version) DO UPDATE SET
                  stage = EXCLUDED.stage,
                  artifact_uri = EXCLUDED.artifact_uri,
                  metrics = EXCLUDED.metrics,
                  trained_at = NOW(),
                  config = EXCLUDED.config
                """,
                model_key,
                version,
                entity_type,
                stage,
                artifact_uri,
                json.dumps(metrics),
                json.dumps(manifest),
            )
            count += 1
    finally:
        await conn.close()
    return count


async def main_async(args: argparse.Namespace) -> None:
    out = Path(args.out)
    sports = [args.sport] if args.sport else list(SPORTS)
    trained = 0
    for sport in sports:
        for objective in ("value", "quality"):
            if _run_train("athlete", sport, objective, str(out), synthetic=args.synthetic, upload=args.upload_s3):
                trained += 1
        if args.include_teams:
            for objective in ("team_value", "team_quality"):
                if _run_train("team", sport, objective, str(out), synthetic=args.synthetic, upload=args.upload_s3):
                    trained += 1
    if args.include_brands:
        _run_train("brand", "global", "brand_sponsor", str(out), synthetic=True, upload=args.upload_s3)

    registered = 0
    if args.register and os.environ.get("PG_DSN"):
        registered = await register_bundles(out, stage=args.stage)
    print(
        json.dumps(
            {
                "trained_jobs": trained,
                "registered_models": registered,
                "bundle_root": str(out.resolve()),
                "completed_at": datetime.now(tz=timezone.utc).isoformat(),
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap Gravity ML bundles")
    parser.add_argument("--sport", choices=SPORTS)
    parser.add_argument("--out", default="models/bundles")
    parser.add_argument("--synthetic", action="store_true", help="Allow synthetic training if DB thin")
    parser.add_argument("--upload-s3", action="store_true")
    parser.add_argument("--register", action="store_true", help="Register bundles in gravity_model_registry")
    parser.add_argument("--stage", default="candidate", choices=["candidate", "shadow", "champion"])
    parser.add_argument("--include-teams", action="store_true")
    parser.add_argument("--include-brands", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
