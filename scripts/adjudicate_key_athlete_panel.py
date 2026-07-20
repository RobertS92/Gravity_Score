#!/usr/bin/env python3
"""Build an auditable expert-range artifact for the key-athlete verify panel.

This is an evaluation/reporting tool, not production scoring code. Named ranges
capture explicit human adjudications; all other ranges are conservative,
feature-based priors using persisted evidence and the current global formula.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg

from gravity_api.config import get_settings
from gravity_api.services.global_scores import calibrate_global_commercial_score

PANEL_PATH = ROOT / "reports" / "key_athlete_verify_results.json"
JSON_PATH = ROOT / "reports" / "key_athlete_expert_ranges.json"
MD_PATH = ROOT / "reports" / "key_athlete_expert_ranges.md"

# Human evaluation targets only. These values never enter score inference.
ADJUDICATED_RANGES: dict[str, tuple[float, float, float, float, str]] = {
    "Patrick Mahomes": (90, 95, 86, 94, "Validated NFL APY plus exceptional quarterback market stature."),
    "Courtland Sutton": (70, 80, 82, 90, "Strong WR contract and production, but not a globally elite consumer brand."),
    "LeBron James": (93, 97, 90, 96, "Exceptional global attention and durable commercial brand; elite winning record."),
    "Nikola Jokic": (80, 88, 94, 98, "MVP-level impact; salary reflects performance more than global consumer demand."),
    "Bam Adebayo": (74, 83, 78, 87, "High salary and All-Star proof, with materially lower global reach than megastars."),
    "Evan Mobley": (72, 82, 80, 89, "Large salary and defensive impact, but modest measured global attention."),
    "Angel Reese": (82, 88, 70, 82, "Observed social/search attention supports an exceptional WNBA commercial outlier."),
    "A'ja Wilson": (66, 78, 95, 99, "Historic awards support elite Value; commercial evidence is strong within WNBA, not global-elite."),
    "Arch Manning": (85, 91, 55, 70, "Observed NIL and social reach support high Gravity; limited participation widens Value uncertainty."),
}


def _json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value or {}


def _num(data: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return None


def _clamp_band(center: float, width: float, lo: float = 20.0, hi: float = 98.0) -> tuple[float, float]:
    return round(max(lo, center - width), 1), round(min(hi, center + width), 1)


def _confidence(
    observed_market: float | None,
    reach: float,
    wiki: float,
    proof: float | None,
    participation: float | None,
) -> str:
    signals = sum(
        (
            observed_market is not None,
            reach > 0,
            wiki > 0,
            proof is not None,
            participation is not None and participation > 0,
        )
    )
    return "high" if signals >= 4 else "medium" if signals >= 2 else "low"


def _reason(
    *,
    sport: str,
    tier: str,
    observed_market: float | None,
    market_type: str | None,
    reach: float,
    wiki: float,
    proof: float | None,
    participation: float | None,
    award_count: int,
) -> str:
    evidence: list[str] = [f"{sport.upper()} {tier} panel stratum"]
    if observed_market is not None:
        evidence.append(f"observed {market_type or 'market'} ${observed_market:,.0f}")
    if reach > 0:
        evidence.append(f"{reach:,.0f} measured social followers")
    if wiki > 0:
        evidence.append(f"{wiki:,.0f} 30-day Wikipedia views")
    if proof is not None:
        evidence.append(f"proof {proof:.1f}")
    if participation is not None:
        evidence.append(f"participation {participation:.2f}")
    if award_count:
        evidence.append("structured major-award evidence")
    return "; ".join(evidence) + "."


async def main() -> int:
    report = json.loads(PANEL_PATH.read_text(encoding="utf-8"))
    panel_rows = list(report["results"])
    ids = [row["id"] for row in panel_rows]

    conn = await asyncpg.connect(get_settings().pg_dsn, statement_cache_size=0)
    try:
        evidence_rows = await conn.fetch(
            """
            SELECT a.id::text,
                   r.raw_data,
                   s.instagram_followers, s.tiktok_followers, s.twitter_followers,
                   gs.brand_score, gs.proof_score, gs.dollar_confidence,
                   l.value_usd, l.label_type, l.confidence AS label_confidence,
                   l.source AS label_source
            FROM athletes a
            LEFT JOIN LATERAL (
                SELECT raw_data FROM raw_athlete_data
                WHERE athlete_id=a.id ORDER BY scraped_at DESC LIMIT 1
            ) r ON TRUE
            LEFT JOIN LATERAL (
                SELECT * FROM social_snapshots
                WHERE athlete_id=a.id ORDER BY scraped_at DESC LIMIT 1
            ) s ON TRUE
            LEFT JOIN LATERAL (
                SELECT * FROM athlete_gravity_scores
                WHERE athlete_id=a.id ORDER BY calculated_at DESC LIMIT 1
            ) gs ON TRUE
            LEFT JOIN LATERAL (
                SELECT * FROM athlete_value_labels
                WHERE athlete_id=a.id AND value_usd > 0
                ORDER BY confidence DESC NULLS LAST, value_usd DESC LIMIT 1
            ) l ON TRUE
            WHERE a.id=ANY($1::uuid[])
            """,
            ids,
        )
    finally:
        await conn.close()

    evidence_by_id = {row["id"]: row for row in evidence_rows}
    output: list[dict[str, Any]] = []
    residuals: dict[str, list[tuple[float, float]]] = defaultdict(list)
    source_residuals: dict[str, list[float]] = defaultdict(list)

    for panel in panel_rows:
        ev = evidence_by_id.get(panel["id"])
        raw = _json(ev["raw_data"] if ev else {})
        dc = _json(ev["dollar_confidence"] if ev else {})
        observed_market = float(ev["value_usd"]) if ev and ev["value_usd"] else None
        market_type = str(ev["label_type"]) if ev and ev["label_type"] else None
        if observed_market is not None:
            raw = {
                **raw,
                "observed_market_value_usd": observed_market,
                "observed_market_value_type": market_type,
                "observed_market_value_confidence": float(ev["label_confidence"] or 0.8),
            }
        social_values = (
            ev["instagram_followers"] if ev else None,
            ev["tiktok_followers"] if ev else None,
            ev["twitter_followers"] if ev else None,
        )
        for key, value in zip(
            ("instagram_followers", "tiktok_followers", "twitter_followers"),
            social_values,
        ):
            if value and not raw.get(key):
                raw[key] = int(value)

        reach = sum(max(0.0, _num(raw, key) or 0.0) for key in (
            "instagram_followers", "tiktok_followers", "twitter_followers"
        ))
        wiki = _num(raw, "wikipedia_views_30d", "wikipedia_page_views_30d") or 0.0
        proof = float(ev["proof_score"]) if ev and ev["proof_score"] is not None else panel.get("proof")
        participation = panel.get("participation")
        component_brand = float(ev["brand_score"]) if ev and ev["brand_score"] is not None else 55.0
        formula_g, calibration = calibrate_global_commercial_score(
            {"brand_score": component_brand, "dollar_confidence": dc},
            raw,
            panel["sport"],
        )

        confidence = _confidence(observed_market, reach, wiki, proof, participation)
        width = {"high": 4.0, "medium": 6.0, "low": 9.0}[confidence]
        expected_g = _clamp_band(formula_g, width)

        current_v = float(panel["V_after"])
        value_width = 4.0 if confidence == "high" else 7.0 if confidence == "medium" else 10.0
        expected_v = _clamp_band(current_v, value_width, lo=25.0)

        award_blob = raw.get("major_awards_json")
        award_count = len(award_blob) if isinstance(award_blob, list) else 0
        reason = _reason(
            sport=panel["sport"],
            tier=panel.get("tier") or "unknown",
            observed_market=observed_market,
            market_type=market_type,
            reach=reach,
            wiki=wiki,
            proof=proof,
            participation=participation,
            award_count=award_count,
        )
        if panel["name"] in ADJUDICATED_RANGES:
            g_lo, g_hi, v_lo, v_hi, expert_note = ADJUDICATED_RANGES[panel["name"]]
            expected_g = (g_lo, g_hi)
            expected_v = (v_lo, v_hi)
            reason = f"{expert_note} Evidence: {reason}"
            confidence = "high" if observed_market or reach or award_count else "medium"

        g_mid = sum(expected_g) / 2.0
        v_mid = sum(expected_v) / 2.0
        residuals[panel["sport"]].append((float(panel["G_after"]) - g_mid, float(panel["V_after"]) - v_mid))
        source_residuals[str(panel.get("gravity_source") or "unknown")].append(
            float(panel["G_after"]) - g_mid
        )
        output.append(
            {
                "id": panel["id"],
                "sport": panel["sport"],
                "athlete": panel["name"],
                "position": panel.get("position"),
                "tier": panel.get("tier"),
                "current_gravity": panel["G_after"],
                "current_value": panel["V_after"],
                "expected_gravity_min": expected_g[0],
                "expected_gravity_max": expected_g[1],
                "expected_value_min": expected_v[0],
                "expected_value_max": expected_v[1],
                "confidence": confidence,
                "evidence_reason": reason,
                "evidence": {
                    "observed_market_value_usd": observed_market,
                    "observed_market_value_type": market_type,
                    "observed_market_value_source": str(ev["label_source"]) if ev and ev["label_source"] else None,
                    "social_reach": round(reach),
                    "wikipedia_views_30d": round(wiki),
                    "proof_score": proof,
                    "participation_index": participation,
                    "major_award_entries": award_count,
                    "formula_gravity_reference": formula_g,
                    "calibration": calibration,
                },
            }
        )

    sport_analysis = {
        sport: {
            "n": len(values),
            "mean_gravity_residual_vs_range_midpoint": round(sum(v[0] for v in values) / len(values), 2),
            "mean_value_residual_vs_range_midpoint": round(sum(v[1] for v in values) / len(values), 2),
        }
        for sport, values in sorted(residuals.items())
    }
    source_analysis = {
        source: {
            "n": len(values),
            "mean_gravity_residual_vs_range_midpoint": round(sum(values) / len(values), 2),
        }
        for source, values in sorted(source_residuals.items())
    }
    artifact = {
        "methodology": {
            "purpose": "Human evaluation ranges for the 125-athlete verify panel; not scoring inputs.",
            "uncertainty": "Ranges widen when salary/NIL, audience, proof, or participation evidence is sparse.",
            "global_gravity": "Cross-sport commercial scale using observed compensation as evidence, not a score floor.",
            "value": "Absolute winning impact; within-sport percentiles remain separate.",
        },
        "systematic_findings": [
            "The prior market_score-1 floor made salary/APY nearly synonymous with global commercial Gravity.",
            "Cohort-derived component brand was treated as absolute evidence even when direct social/partnership data was missing.",
            "WNBA fallback brand scores inherited within-sport strength and overstated cross-sport commercial scale.",
            "The Value proof upper tail plus velocity and availability bonuses allowed ordinary strong seasons to enter 90+.",
        ],
        "residual_analysis": {"by_sport": sport_analysis, "by_gravity_source": source_analysis},
        "confidence_counts": dict(Counter(row["confidence"] for row in output)),
        "athletes": output,
    }
    JSON_PATH.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Key Athlete Expert Ranges",
        "",
        "These are evaluation ranges, not production scoring inputs. Named adjudications reflect explicit expert anchors; all other bands use conservative feature-based priors and widen with sparse evidence.",
        "",
        "## Systematic findings",
        "",
        *[f"- {item}" for item in artifact["systematic_findings"]],
        "",
        "## Athlete ranges",
        "",
        "| Sport | Athlete | Pos | Current G | Expected G | Current V | Expected V | Confidence | Evidence |",
        "|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in sorted(output, key=lambda item: (item["sport"], -float(item["current_gravity"]), item["athlete"])):
        reason = str(row["evidence_reason"]).replace("|", "/")
        lines.append(
            f"| {row['sport']} | {row['athlete']} | {row['position'] or '—'} | "
            f"{row['current_gravity']:.1f} | {row['expected_gravity_min']:.1f}–{row['expected_gravity_max']:.1f} | "
            f"{row['current_value']:.1f} | {row['expected_value_min']:.1f}–{row['expected_value_max']:.1f} | "
            f"{row['confidence']} | {reason} |"
        )
    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {JSON_PATH}")
    print(f"wrote {MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
