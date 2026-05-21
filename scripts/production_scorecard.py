"""
Production scorecard — runs the A-grade verification SQL pack against Supabase
and prints a per-layer grade (scrapers, ML, composite fallback, API/CSC).

Usage:
    PYTHONPATH=. .venv/bin/python scripts/production_scorecard.py
    PYTHONPATH=. .venv/bin/python scripts/production_scorecard.py --json
    PYTHONPATH=. .venv/bin/python scripts/production_scorecard.py --fail-below B

A-grade gates (mirrors the remediation plan):
    Scrapers     last scrape <7d, NIL suspect band <5%, weekly_pipeline success in 7d
    Neural v2    >=60% rows gravity_athlete_v2 (30d), label_raw_hi>30, spread>=15
    Composite    fallback dollar_p50 stddev >$200K on SEC QBs
    API/CSC      conference coverage >=95% CFB
    Website      consistent NIL (sanitized=True on profile, no $0.0M for >$5k)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import asyncpg  # noqa: E402

logger = logging.getLogger("production_scorecard")


_GRADE_ORDER = ("A", "B", "C", "D", "F")


def _grade_index(grade: str) -> int:
    return _GRADE_ORDER.index(grade) if grade in _GRADE_ORDER else len(_GRADE_ORDER)


def _grade_from_score(score: float, thresholds: tuple[float, float, float, float]) -> str:
    """thresholds = (A, B, C, D); values >=A → 'A', etc."""
    a, b, c, d = thresholds
    if score >= a:
        return "A"
    if score >= b:
        return "B"
    if score >= c:
        return "C"
    if score >= d:
        return "D"
    return "F"


@dataclass
class LayerReport:
    layer: str
    grade: str
    metrics: dict
    notes: list[str]


async def _scraper_layer(conn: asyncpg.Connection) -> LayerReport:
    notes: list[str] = []
    metrics: dict = {}

    row = await conn.fetchrow(
        "SELECT MAX(scraped_at) AS last_scrape FROM raw_athlete_data"
    )
    last_scrape = row["last_scrape"] if row else None
    metrics["last_scrape_at"] = last_scrape.isoformat() if last_scrape else None
    if last_scrape is not None:
        age_days = (
            await conn.fetchval(
                "SELECT EXTRACT(EPOCH FROM (NOW() - $1::timestamptz))/86400.0",
                last_scrape,
            )
            or 0.0
        )
        metrics["last_scrape_age_days"] = round(float(age_days), 1)
        if age_days > 7:
            notes.append(f"Last scrape was {age_days:.1f} days ago (target <7d)")
    else:
        metrics["last_scrape_age_days"] = None
        notes.append("raw_athlete_data is empty")

    suspect = await conn.fetchval(
        """SELECT 100.0 * COUNT(*) FILTER (
              WHERE (raw_data->>'nil_valuation')::numeric BETWEEN 5000 AND 500000
            ) / NULLIF(COUNT(*) FILTER (WHERE raw_data ? 'nil_valuation'), 0)
           FROM raw_athlete_data"""
    )
    metrics["nil_suspect_band_pct"] = round(float(suspect or 0.0), 2)

    pipeline = await conn.fetchval(
        """SELECT COUNT(*)::int FROM scraper_jobs
            WHERE job_type IN ('weekly_pipeline','weekly_full_scrape')
              AND status = 'completed'
              AND started_at > NOW() - INTERVAL '7 days'"""
    )
    metrics["weekly_pipeline_runs_7d"] = int(pipeline or 0)
    if not pipeline:
        notes.append("No completed weekly_pipeline in the last 7 days")

    # Composite score: 0–100 (freshness + NIL band + pipeline run)
    freshness = 100.0 if (metrics["last_scrape_age_days"] or 1e9) < 7 else 50.0 if (metrics["last_scrape_age_days"] or 1e9) < 14 else 0.0
    nil_band = max(0.0, 100.0 - 4.0 * metrics["nil_suspect_band_pct"])
    pipeline_score = 100.0 if pipeline else 0.0
    composite = round(0.45 * freshness + 0.35 * nil_band + 0.20 * pipeline_score, 1)
    metrics["composite"] = composite
    grade = _grade_from_score(composite, (85, 75, 65, 50))
    return LayerReport(layer="scrapers", grade=grade, metrics=metrics, notes=notes)


async def _ml_layer(conn: asyncpg.Connection) -> LayerReport:
    notes: list[str] = []
    metrics: dict = {}

    mix = await conn.fetch(
        """SELECT model_version, COUNT(*)::int AS n
             FROM athlete_gravity_scores
            WHERE calculated_at > NOW() - INTERVAL '30 days'
            GROUP BY model_version"""
    )
    total = sum(int(r["n"]) for r in mix) or 1
    v2_share = (
        sum(int(r["n"]) for r in mix if "gravity_athlete_v2" in (r["model_version"] or ""))
        / total
        * 100.0
    )
    metrics["model_version_mix_30d"] = {r["model_version"]: int(r["n"]) for r in mix}
    metrics["v2_share_pct"] = round(v2_share, 2)
    if v2_share < 60:
        notes.append(f"Only {v2_share:.1f}% of last-30d scores are gravity_athlete_v2 (target >=60%)")

    spread = await conn.fetchrow(
        """SELECT MAX(gravity_score) - MIN(gravity_score) AS spread,
                  STDDEV_POP(gravity_score)::float AS stddev,
                  AVG(gravity_score)::float AS mean
             FROM athlete_gravity_scores
            WHERE calculated_at > NOW() - INTERVAL '30 days'
              AND model_version LIKE '%v2%'"""
    )
    if spread:
        metrics["v2_gravity_spread"] = round(float(spread["spread"] or 0.0), 2)
        metrics["v2_gravity_stddev"] = round(float(spread["stddev"] or 0.0), 2)
        if (spread["spread"] or 0.0) < 15.0:
            notes.append("v2 gravity spread <15 (model collapsed)")

    composite = 100.0 * (v2_share / 100.0) - (
        15.0 if metrics.get("v2_gravity_spread", 100.0) < 15.0 else 0.0
    )
    composite = max(0.0, min(100.0, composite))
    metrics["composite"] = round(composite, 1)
    grade = _grade_from_score(composite, (85, 70, 55, 40))
    return LayerReport(layer="ml_v2", grade=grade, metrics=metrics, notes=notes)


async def _composite_fallback_layer(conn: asyncpg.Connection) -> LayerReport:
    notes: list[str] = []
    metrics: dict = {}

    sec_qb_disp = await conn.fetchrow(
        """SELECT STDDEV_POP(s.dollar_p50_usd)::float AS stddev,
                  COUNT(*)::int AS n
             FROM athlete_gravity_scores s
             JOIN athletes a ON a.id = s.athlete_id
            WHERE a.conference = 'SEC' AND a.position ILIKE 'QB%'
              AND s.calculated_at > NOW() - INTERVAL '30 days'
              AND s.dollar_p50_usd IS NOT NULL"""
    )
    if sec_qb_disp:
        metrics["sec_qb_dollar_stddev"] = round(float(sec_qb_disp["stddev"] or 0.0), 0)
        metrics["sec_qb_count"] = int(sec_qb_disp["n"] or 0)
        if (sec_qb_disp["stddev"] or 0.0) < 200_000:
            notes.append("SEC QB dollar_p50 stddev <$200K (model + fallback not differentiating)")

    suspect_p50 = await conn.fetchval(
        """SELECT 100.0 * COUNT(*) FILTER (WHERE s.dollar_p50_usd < 50000)
                  / NULLIF(COUNT(*), 0)
             FROM athlete_gravity_scores s
             JOIN athletes a ON a.id = s.athlete_id
            WHERE a.is_active IS TRUE
              AND a.recruiting_stars >= 4
              AND s.calculated_at > NOW() - INTERVAL '30 days'"""
    )
    metrics["elite_low_p50_share_pct"] = round(float(suspect_p50 or 0.0), 2)
    if (suspect_p50 or 0.0) > 10.0:
        notes.append(
            f"{suspect_p50:.1f}% of 4+ star active athletes have dollar_p50 <$50K"
        )

    composite = 100.0
    if (sec_qb_disp and (sec_qb_disp["stddev"] or 0) < 200_000):
        composite -= 30
    composite -= min(40.0, float(suspect_p50 or 0.0) * 2.0)
    composite = max(0.0, composite)
    metrics["composite"] = round(composite, 1)
    grade = _grade_from_score(composite, (85, 70, 55, 40))
    return LayerReport(layer="composite_fallback", grade=grade, metrics=metrics, notes=notes)


async def _api_layer(conn: asyncpg.Connection) -> LayerReport:
    notes: list[str] = []
    metrics: dict = {}

    cfb_coverage = await conn.fetchrow(
        """SELECT
              100.0 * COUNT(*) FILTER (WHERE conference IS NOT NULL AND TRIM(conference) <> '')
                    / NULLIF(COUNT(*), 0) AS pct,
              COUNT(*)::int AS total
            FROM athletes
           WHERE sport = 'cfb'"""
    )
    if cfb_coverage:
        metrics["cfb_conference_coverage_pct"] = round(float(cfb_coverage["pct"] or 0.0), 2)
        metrics["cfb_total"] = int(cfb_coverage["total"] or 0)
        if (cfb_coverage["pct"] or 0.0) < 95.0:
            notes.append(f"CFB conference coverage {cfb_coverage['pct']:.1f}% (target >=95%)")

    inactive = await conn.fetchrow(
        """SELECT
              COUNT(*) FILTER (WHERE is_active IS FALSE)::int AS inactive,
              COUNT(*)::int AS total
            FROM athletes"""
    )
    if inactive:
        metrics["inactive_count"] = int(inactive["inactive"] or 0)
        metrics["inactive_pct"] = round(
            100.0 * int(inactive["inactive"] or 0) / max(int(inactive["total"] or 1), 1),
            2,
        )

    pct = float(metrics.get("cfb_conference_coverage_pct") or 0.0)
    composite = pct  # 95+ → A, etc.
    metrics["composite"] = round(composite, 1)
    grade = _grade_from_score(composite, (95, 85, 70, 55))
    return LayerReport(layer="api_csc", grade=grade, metrics=metrics, notes=notes)


_LAYERS = (
    ("scrapers", _scraper_layer),
    ("ml_v2", _ml_layer),
    ("composite_fallback", _composite_fallback_layer),
    ("api_csc", _api_layer),
)


async def run(*, as_json: bool, fail_below: str | None) -> int:
    dsn = os.environ["PG_DSN"]
    conn = await asyncpg.connect(dsn)
    reports: list[LayerReport] = []
    try:
        for _name, fn in _LAYERS:
            try:
                reports.append(await fn(conn))
            except Exception as exc:
                logger.exception("layer failed: %s", exc)
                reports.append(
                    LayerReport(
                        layer=_name,
                        grade="F",
                        metrics={},
                        notes=[f"layer crashed: {exc}"],
                    )
                )
    finally:
        await conn.close()

    payload = {r.layer: asdict(r) for r in reports}
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"{'LAYER':<22} {'GRADE':<6} {'COMPOSITE':<10} NOTES")
        print("-" * 78)
        for r in reports:
            comp = r.metrics.get("composite")
            comp_s = f"{comp:.1f}" if isinstance(comp, (int, float)) else "—"
            print(f"{r.layer:<22} {r.grade:<6} {comp_s:<10} {' | '.join(r.notes) or 'OK'}")

    if fail_below:
        worst = max(reports, key=lambda r: _grade_index(r.grade))
        if _grade_index(worst.grade) > _grade_index(fail_below):
            logger.error(
                "scorecard below threshold: %s=%s < %s",
                worst.layer, worst.grade, fail_below,
            )
            return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Production scorecard")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of table")
    parser.add_argument(
        "--fail-below",
        choices=_GRADE_ORDER,
        help="Exit non-zero if any layer's grade is below this threshold",
    )
    parser.add_argument(
        "--log-level", default="WARNING", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")

    sys.exit(asyncio.run(run(as_json=args.json, fail_below=args.fail_below)))


if __name__ == "__main__":
    main()
