"""Empirically calibrate sport-specific composite weights from labeled outcomes.

Usage:
  PYTHONPATH=. python -m gravity_api.jobs.calibrate_composite_weights --sport cfb
  PYTHONPATH=. python -m gravity_api.jobs.calibrate_composite_weights --all --dry-run

Target: log1p(dollar_p50_usd) from athlete_gravity_scores joined to component scores.
Requires >= 30 rows per sport; otherwise keeps Delphi priors in config.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math

import asyncpg

from gravity_api.config import get_settings
from gravity_composite.composite import fit_weights_nonneg_least_squares, save_sport_weights

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


async def _fetch_calibration_rows(conn: asyncpg.Connection, sport: str) -> list[dict[str, float]]:
    rows = await conn.fetch(
        """
        SELECT
          s.brand_score,
          s.proof_score,
          s.proximity_score,
          s.velocity_score,
          s.risk_score,
          s.dollar_p50_usd,
          s.gravity_score
        FROM athlete_gravity_scores s
        JOIN athletes a ON a.id = s.athlete_id
        WHERE a.sport = $1
          AND s.brand_score IS NOT NULL
          AND s.proof_score IS NOT NULL
          AND s.proximity_score IS NOT NULL
          AND s.velocity_score IS NOT NULL
          AND s.risk_score IS NOT NULL
          AND s.dollar_p50_usd IS NOT NULL
          AND s.dollar_p50_usd > 0
        ORDER BY s.scored_at DESC NULLS LAST
        LIMIT 5000
        """,
        sport,
    )
    out: list[dict[str, float]] = []
    for row in rows:
        p50 = float(row["dollar_p50_usd"])
        out.append(
            {
                "brand": float(row["brand_score"]),
                "proof": float(row["proof_score"]),
                "proximity": float(row["proximity_score"]),
                "velocity": float(row["velocity_score"]),
                "risk": float(row["risk_score"]),
                "target": math.log1p(p50),
            }
        )
    return out


async def calibrate_sport(sport: str, *, dry_run: bool = False) -> dict | None:
    conn = await asyncpg.connect(get_settings().pg_dsn, statement_cache_size=0)
    try:
        rows = await _fetch_calibration_rows(conn, sport)
        if len(rows) < 30:
            logger.warning(
                "%s: only %d labeled rows — need 30+ for empirical fit; keeping priors",
                sport,
                len(rows),
            )
            return None
        weights = fit_weights_nonneg_least_squares(rows, target_key="target")
        logger.info(
            "%s fitted weights: B=%.3f P=%.3f X=%.3f V=%.3f R=%.3f (n=%d)",
            sport,
            weights.brand,
            weights.proof,
            weights.proximity,
            weights.velocity,
            weights.risk,
            len(rows),
        )
        if not dry_run:
            save_sport_weights(sport, weights)
        return weights.as_dict()
    finally:
        await conn.close()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate Gravity composite weights per sport")
    parser.add_argument("--sport", choices=SPORTS)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sports = list(SPORTS) if args.all else ([args.sport] if args.sport else [])
    if not sports:
        parser.error("Specify --sport or --all")

    for sport in sports:
        await calibrate_sport(sport, dry_run=args.dry_run)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
