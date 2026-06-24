"""
Export Gravity training data as CSV for Colab / GPU training.

Examples:
  # All scored CFB athletes (features + proxy labels) — best for Colab bootstrap
  PYTHONPATH=. python3 -m gravity_api.jobs.export_training_csv \\
    --mode scored --sport cfb --out data/cfb_scored.csv

  # All sports into one file
  PYTHONPATH=. python3 -m gravity_api.jobs.export_training_csv \\
    --mode scored --out data/all_sports_scored.csv

  # Leakage-safe labeled rows (requires gravity_training_labels)
  PYTHONPATH=. python3 -m gravity_api.jobs.export_training_csv \\
    --mode labeled --target-key nil_valuation_usd --out data/labeled_nil.csv

  # Per-sport directory for Colab
  PYTHONPATH=. python3 -m gravity_api.jobs.export_training_csv \\
    --mode scored --out-dir data/colab_exports/

  # All roster athletes + raw scrape fields (no scores required)
  PYTHONPATH=. python3 -m gravity_api.jobs.export_training_csv \\
    --mode raw --out-dir data/raw_exports/

After export, upload CSV to Colab:
  from google.colab import files
  files.upload()  # or mount Drive / pull from S3
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)

import asyncpg

from gravity_api.config import get_settings
from gravity_api.services.sport_pipeline.config import ALL_SPORT_PIPELINES
from gravity_api.services.athlete_enrichment import parse_raw_data
from gravity_api.services.training_export import build_scraped_row, build_training_row, write_csv

logger = logging.getLogger(__name__)


async def export_scored_athletes(
    conn: asyncpg.Connection,
    *,
    sport: str | None = None,
    limit: int = 50_000,
) -> list[dict]:
    sport_clause = "AND a.sport = $1" if sport else ""
    params: list = [limit]
    if sport:
        params = [sport, limit]
        query = f"""
            SELECT
              a.id::text AS entity_id,
              a.name, a.school, a.position, a.conference, a.class_year,
              a.sport,
              s.calculated_at AS as_of,
              s.gravity_score, s.brand_score, s.proof_score,
              s.proximity_score, s.velocity_score, s.risk_score,
              s.quality_score, s.partnership_brand_score,
              s.dollar_p10_usd, s.dollar_p50_usd, s.dollar_p90_usd,
              s.confidence, s.model_version,
              r.raw_data,
              fs.features AS snapshot_features,
              fs.as_of AS snapshot_as_of
            FROM athletes a
            JOIN LATERAL (
              SELECT * FROM athlete_gravity_scores
              WHERE athlete_id = a.id ORDER BY calculated_at DESC LIMIT 1
            ) s ON TRUE
            LEFT JOIN LATERAL (
              SELECT raw_data FROM raw_athlete_data
              WHERE athlete_id = a.id ORDER BY scraped_at DESC LIMIT 1
            ) r ON TRUE
            LEFT JOIN LATERAL (
              SELECT features, as_of FROM gravity_feature_snapshots
              WHERE entity_type = 'athlete' AND entity_id = a.id
              ORDER BY as_of DESC LIMIT 1
            ) fs ON TRUE
            WHERE s.gravity_score IS NOT NULL {sport_clause}
            ORDER BY a.sport, s.calculated_at DESC
            LIMIT ${len(params)}
        """
    else:
        query = f"""
            SELECT
              a.id::text AS entity_id,
              a.name, a.school, a.position, a.conference, a.class_year,
              a.sport,
              s.calculated_at AS as_of,
              s.gravity_score, s.brand_score, s.proof_score,
              s.proximity_score, s.velocity_score, s.risk_score,
              s.quality_score, s.partnership_brand_score,
              s.dollar_p10_usd, s.dollar_p50_usd, s.dollar_p90_usd,
              s.confidence, s.model_version,
              r.raw_data,
              fs.features AS snapshot_features,
              fs.as_of AS snapshot_as_of
            FROM athletes a
            JOIN LATERAL (
              SELECT * FROM athlete_gravity_scores
              WHERE athlete_id = a.id ORDER BY calculated_at DESC LIMIT 1
            ) s ON TRUE
            LEFT JOIN LATERAL (
              SELECT raw_data FROM raw_athlete_data
              WHERE athlete_id = a.id ORDER BY scraped_at DESC LIMIT 1
            ) r ON TRUE
            LEFT JOIN LATERAL (
              SELECT features, as_of FROM gravity_feature_snapshots
              WHERE entity_type = 'athlete' AND entity_id = a.id
              ORDER BY as_of DESC LIMIT 1
            ) fs ON TRUE
            WHERE s.gravity_score IS NOT NULL
            ORDER BY a.sport, s.calculated_at DESC
            LIMIT $1
        """
    rows = await conn.fetch(query, *params)
    out = []
    for row in rows:
        raw = parse_raw_data(row["raw_data"])
        snap = parse_raw_data(row["snapshot_features"]) or None
        if not snap:
            snap = None
        out.append(
            build_training_row(
                entity_id=row["entity_id"],
                entity_type="athlete",
                sport=row["sport"],
                as_of=(row["as_of"].isoformat() if row["as_of"] else None),
                identity=dict(row),
                scores=dict(row),
                snapshot_features=snap,
                raw_data=raw,
            )
        )
    return out


async def export_labeled_rows(
    conn: asyncpg.Connection,
    *,
    entity_type: str,
    target_key: str,
    sport: str | None = None,
    limit: int = 100_000,
) -> list[dict]:
    sport_join = ""
    params: list = [entity_type, target_key, limit]
    if sport and entity_type == "athlete":
        sport_join = "JOIN athletes a ON a.id = s.entity_id AND a.sport = $4"
        params.append(sport)

    rows = await conn.fetch(
        f"""
        SELECT
          s.entity_id::text AS entity_id,
          s.entity_type,
          s.as_of,
          s.features,
          s.data_quality_score,
          l.target_key,
          l.target_value,
          l.target_class,
          l.label_start_at,
          l.available_at,
          l.confidence AS label_confidence,
          l.verified AS label_verified
        FROM gravity_feature_snapshots s
        JOIN gravity_training_labels l
          ON l.entity_type = s.entity_type
         AND l.entity_id = s.entity_id
         AND l.target_key = $2
        {sport_join}
        WHERE s.entity_type = $1
          AND l.label_start_at >= s.as_of
          AND l.available_at >= l.label_start_at
        ORDER BY s.as_of, s.entity_id
        LIMIT $3
        """,
        *params,
    )
    out = []
    for row in rows:
        features = parse_raw_data(row["features"])
        sport_val = features.get("sport") or (sport if sport else None)
        out.append(
            build_training_row(
                entity_id=row["entity_id"],
                entity_type=entity_type,
                sport=sport_val,
                as_of=row["as_of"].isoformat() if row["as_of"] else None,
                snapshot_features=features,
                labels={
                    "target_key": row["target_key"],
                    "target_value": float(row["target_value"]) if row["target_value"] is not None else None,
                    "target_class": row["target_class"],
                    "label_confidence": float(row["label_confidence"] or 0),
                    "label_verified": bool(row["label_verified"]),
                    "label_start_at": row["label_start_at"].isoformat() if row["label_start_at"] else None,
                    "available_at": row["available_at"].isoformat() if row["available_at"] else None,
                },
            )
        )
    return out


async def export_raw_athletes(
    conn: asyncpg.Connection,
    *,
    sport: str | None = None,
    limit: int = 200_000,
    active_only: bool = True,
) -> list[dict]:
    """Export every roster athlete with latest raw_athlete_data (scores not required)."""
    clauses = ["WHERE 1=1"]
    params: list = []
    if sport:
        params.append(sport)
        clauses.append(f"AND a.sport = ${len(params)}")
    if active_only:
        clauses.append("AND COALESCE(a.is_active, TRUE) = TRUE")
    params.append(limit)
    limit_idx = len(params)
    query = f"""
        SELECT
          a.id::text AS entity_id,
          a.name, a.school, a.position, a.conference, a.class_year,
          a.sport, a.espn_id, a.jersey_number, a.height_inches, a.weight_lbs,
          a.hometown, a.home_state, a.is_active, a.roster_status,
          r.raw_data,
          r.scraped_at,
          r.scrape_version,
          (r.raw_data IS NOT NULL) AS has_raw
        FROM athletes a
        LEFT JOIN LATERAL (
          SELECT raw_data, scraped_at, scrape_version
          FROM raw_athlete_data
          WHERE athlete_id = a.id
          ORDER BY scraped_at DESC NULLS LAST
          LIMIT 1
        ) r ON TRUE
        {' '.join(clauses)}
        ORDER BY a.sport, a.school, a.name
        LIMIT ${limit_idx}
    """
    rows = await conn.fetch(query, *params)
    out = []
    for row in rows:
        raw = parse_raw_data(row["raw_data"])
        out.append(
            build_scraped_row(
                entity_id=row["entity_id"],
                sport=row["sport"],
                identity=dict(row),
                raw_data=raw if raw else None,
                scraped_at=row["scraped_at"].isoformat() if row["scraped_at"] else None,
                scrape_version=row["scrape_version"],
                has_raw=bool(row["has_raw"]),
            )
        )
    return out


async def export_teams(
    conn: asyncpg.Connection,
    *,
    sport: str | None = None,
) -> list[dict]:
    sport_clause = "WHERE gt.sport = $1" if sport else ""
    params = [sport] if sport else []
    rows = await conn.fetch(
        f"""
        SELECT
          gt.id::text AS entity_id,
          gt.sport,
          gt.school,
          gt.conference,
          AVG(s.gravity_score)::float AS roster_value,
          AVG(s.velocity_score)::float AS roster_velocity,
          AVG(100.0 - s.risk_score)::float AS roster_stability,
          AVG(s.proof_score)::float AS performance,
          AVG(s.dollar_p50_usd)::float AS avg_nil_p50,
          COUNT(a.id)::int AS roster_size
        FROM gravity_teams gt
        LEFT JOIN athletes a
          ON lower(trim(a.school)) = lower(trim(gt.school)) AND a.sport = gt.sport
        LEFT JOIN LATERAL (
          SELECT * FROM athlete_gravity_scores
          WHERE athlete_id = a.id ORDER BY calculated_at DESC LIMIT 1
        ) s ON TRUE
        {sport_clause}
        GROUP BY gt.id, gt.sport, gt.school, gt.conference
        """,
        *params,
    )
    out = []
    for row in rows:
        out.append(
            build_training_row(
                entity_id=row["entity_id"],
                entity_type="team",
                sport=row["sport"],
                as_of=None,
                identity={"school": row["school"], "conference": row["conference"]},
                scores={
                    "roster_value": row["roster_value"],
                    "performance": row["performance"],
                    "dollar_p50_usd": row["avg_nil_p50"],
                },
                raw_data={
                    "roster_size": row["roster_size"],
                    "roster_value": row["roster_value"],
                    "roster_velocity": row["roster_velocity"],
                    "roster_stability": row["roster_stability"],
                    "performance": row["performance"],
                    "retention": row["roster_stability"],
                    "market_reach": row["roster_velocity"],
                },
            )
        )
        out[-1]["target_team_value"] = row["roster_value"]
        out[-1]["target_team_quality"] = row["performance"]
    return out


async def run_export(args: argparse.Namespace) -> dict:
    settings = get_settings()
    if not settings.pg_dsn:
        raise RuntimeError("PG_DSN required")

    conn = await asyncpg.connect(settings.pg_dsn, statement_cache_size=0)
    try:
        if args.mode == "scored":
            if args.out_dir:
                results = {}
                for sport in ([args.sport] if args.sport else ALL_SPORT_PIPELINES.keys()):
                    rows = await export_scored_athletes(conn, sport=sport, limit=args.limit)
                    path = Path(args.out_dir) / f"athletes_{sport}_scored.csv"
                    n = write_csv(rows, str(path))
                    results[sport] = {"path": str(path), "rows": n}
                    logger.info("Wrote %d rows → %s", n, path)
                return {"exports": results}

            rows = await export_scored_athletes(conn, sport=args.sport, limit=args.limit)
            if not args.out:
                raise ValueError("--out required when not using --out-dir")
            n = write_csv(rows, str(args.out))
            return {"path": str(args.out), "rows": n}

        if args.mode == "raw":
            compress = not args.no_compress
            if args.out_dir:
                results = {}
                sports = [args.sport] if args.sport else ALL_SPORT_PIPELINES.keys()
                for sp in sports:
                    rows = await export_raw_athletes(
                        conn,
                        sport=sp,
                        limit=args.limit,
                        active_only=not args.include_inactive,
                    )
                    path = Path(args.out_dir) / f"athletes_{sp}_raw.csv"
                    n = write_csv(rows, str(path), compress=compress)
                    out_path = str(path.with_suffix(path.suffix + ".gz")) if compress else str(path)
                    results[sp] = {
                        "path": out_path,
                        "rows": n,
                        "with_raw": sum(1 for r in rows if r.get("has_raw_scrape")),
                    }
                    logger.info(
                        "Wrote %d rows (%d with raw) → %s",
                        n,
                        results[sp]["with_raw"],
                        out_path,
                    )
                return {"exports": results}

            rows = await export_raw_athletes(
                conn,
                sport=args.sport,
                limit=args.limit,
                active_only=not args.include_inactive,
            )
            if not args.out:
                raise ValueError("--out required when not using --out-dir")
            n = write_csv(rows, str(args.out), compress=compress)
            out_path = (
                str(args.out.with_suffix(args.out.suffix + ".gz"))
                if compress
                else str(args.out)
            )
            return {
                "path": out_path,
                "rows": n,
                "with_raw": sum(1 for r in rows if r.get("has_raw_scrape")),
            }

        if args.mode == "labeled":
            rows = await export_labeled_rows(
                conn,
                entity_type=args.entity_type,
                target_key=args.target_key,
                sport=args.sport,
                limit=args.limit,
            )
            if not args.out:
                raise ValueError("--out required")
            n = write_csv(rows, str(args.out))
            return {"path": str(args.out), "rows": n}

        if args.mode == "teams":
            if args.out_dir:
                results = {}
                for sport in ([args.sport] if args.sport else ALL_SPORT_PIPELINES.keys()):
                    rows = await export_teams(conn, sport=sport)
                    path = Path(args.out_dir) / f"teams_{sport}.csv"
                    n = write_csv(rows, str(path))
                    results[sport] = {"path": str(path), "rows": n}
                return {"exports": results}
            rows = await export_teams(conn, sport=args.sport)
            if not args.out:
                raise ValueError("--out required")
            n = write_csv(rows, str(args.out))
            return {"path": str(args.out), "rows": n}

        raise ValueError(f"Unknown mode: {args.mode}")
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Gravity training CSV for Colab")
    parser.add_argument(
        "--mode",
        choices=["scored", "raw", "labeled", "teams"],
        default="scored",
        help="scored=features+labels; raw=all roster athletes+raw scrape; labeled=leakage-safe; teams=programs",
    )
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="For raw mode: include inactive roster departures",
    )
    parser.add_argument(
        "--no-compress",
        action="store_true",
        help="For raw mode: write plain .csv (requires ~600MB+ free disk for full export)",
    )
    parser.add_argument("--sport", default=None, help="Filter to one sport")
    parser.add_argument("--entity-type", default="athlete", choices=["athlete", "team", "brand"])
    parser.add_argument("--target-key", default="nil_valuation_usd", help="For labeled mode")
    parser.add_argument("--out", type=Path, default=None, help="Output CSV path")
    parser.add_argument("--out-dir", type=Path, default=None, help="Write one CSV per sport")
    parser.add_argument("--limit", type=int, default=200_000)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(run_export(args))
    print(result)


if __name__ == "__main__":
    main()
