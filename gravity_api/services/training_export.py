"""Flatten snapshots and raw payloads into tabular training rows."""

from __future__ import annotations

import json
import math
from typing import Any, Iterable


# Scalar fields pulled from raw_athlete_data when present
RAW_NUMERIC_KEYS = (
    "instagram_followers",
    "tiktok_followers",
    "twitter_followers",
    "youtube_subscribers",
    "google_trends_score",
    "news_count_30d",
    "nil_valuation",
    "nil_deal_count",
    "nil_deal_count_verified",
    "data_quality_score",
    "recruiting_stars",
    "recruiting_rank_national",
    "recruiting_rank_position",
    "games_played_season",
    "games_started",
    "gs_rate",
    "participation_index",
    "team_wins",
    "team_losses",
    "team_win_pct",
    "team_win_pct_percentile",
    "proof_residual_team",
    "proof_x_participation",
    "proof_x_weak_team",
    "win_impact_score",
    "win_impact_score_v0",
    "impact_confidence",
    "partnership_brand_score",
    "partnership_proof_boost",
    "partnership_deal_count",
    "partnership_verified_count",
    "school_market_rank",
    "nil_environment_score",
    "nil_collective_budget_est",
    "conference_media_index",
    "program_social_followers",
)

SKIP_JSON_KEYS = frozenset({"bpxvr", "cohort_stat_means", "cohort_stat_stds", "nil_deals", "brand_deals"})


def _safe_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    if isinstance(val, bool):
        return float(val)
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def flatten_snapshot_features(features: dict[str, Any] | None) -> dict[str, Any]:
    """Flatten gravity_feature_snapshots.features JSON to scalar columns."""
    if not features:
        return {}
    out: dict[str, Any] = {}
    out["feature_schema_version"] = features.get("feature_schema_version")
    out["cohort_key"] = features.get("cohort_key")
    out["position_group"] = features.get("position_group")
    out["season_year"] = features.get("season_year")

    for component in ("brand", "proof", "proximity", "velocity", "risk"):
        block = features.get(component) or {}
        if not isinstance(block, dict):
            continue
        prefix = component
        for key in ("composite_index", "composite_pctile", "volatility_score"):
            val = block.get(key)
            if val is not None:
                out[f"{prefix}_{key}"] = val
        tier = block.get("composite_tier")
        if tier is not None:
            out[f"{prefix}_composite_tier"] = tier.get("value") if isinstance(tier, dict) else tier
        traj = block.get("trajectory_class")
        if traj is not None:
            out[f"{prefix}_trajectory_class"] = traj.get("value") if isinstance(traj, dict) else traj

        cards = block.get("profile_cards") or {}
        if isinstance(cards, dict):
            for metric_key, card in cards.items():
                if not isinstance(card, dict):
                    continue
                safe = str(metric_key).replace(".", "_")
                if card.get("level_raw") is not None:
                    out[f"{safe}_raw"] = card["level_raw"]
                if card.get("level_pctile") is not None:
                    out[f"{safe}_pctile"] = card["level_pctile"]
                if card.get("delta_yoy_pct") is not None:
                    out[f"{safe}_yoy_pct"] = card["delta_yoy_pct"]
                if card.get("stability_score") is not None:
                    out[f"{safe}_stability"] = card["stability_score"]
                if card.get("masked") is True:
                    out[f"{safe}_masked"] = 1

    college_proof = features.get("college_proof")
    if isinstance(college_proof, dict):
        for k, v in college_proof.items():
            out[f"college_proof_{k}"] = v
    return out


def flatten_raw_data(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Extract numeric scalars from raw_athlete_data JSON."""
    if not raw:
        return {}
    out: dict[str, Any] = {}
    for key in RAW_NUMERIC_KEYS:
        val = _safe_float(raw.get(key))
        if val is not None:
            out[key] = val

    deals = raw.get("nil_deals") or raw.get("brand_deals")
    if isinstance(deals, list):
        out["nil_deal_count_raw"] = len(deals)
        verified = sum(1 for d in deals if isinstance(d, dict) and d.get("verified"))
        out["nil_deal_verified_count_raw"] = verified
        values = [
            _safe_float(d.get("value") or d.get("deal_value"))
            for d in deals
            if isinstance(d, dict)
        ]
        values = [v for v in values if v is not None and v > 0]
        if values:
            out["nil_deal_max_usd"] = max(values)
            out["nil_deal_sum_usd"] = sum(values)

    top_brands = raw.get("partnership_top_brands")
    if isinstance(top_brands, list) and top_brands:
        out["partnership_top_brand_1"] = top_brands[0].get("brand_name") if isinstance(top_brands[0], dict) else None
        out["partnership_top_prestige_1"] = (
            top_brands[0].get("prestige") if isinstance(top_brands[0], dict) else None
        )
    return out


def flatten_raw_data_export(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Flatten all top-level raw_athlete_data fields for CSV export."""
    if not raw:
        return {}
    out: dict[str, Any] = {}
    out.update(flatten_raw_data(raw))
    for key, value in raw.items():
        if key in SKIP_JSON_KEYS:
            continue
        col = f"raw_{key}"
        if col in out:
            continue
        if isinstance(value, (dict, list)):
            out[col] = json.dumps(value, default=str)
        elif value is not None and value != "":
            out[col] = value
    return out


def build_scraped_row(
    *,
    entity_id: str,
    sport: str | None,
    identity: dict[str, Any],
    raw_data: dict[str, Any] | None,
    scraped_at: str | None = None,
    scrape_version: str | None = None,
    has_raw: bool = False,
) -> dict[str, Any]:
    """Build export row from athlete identity + latest raw scrape (no scores)."""
    row: dict[str, Any] = {
        "entity_id": entity_id,
        "entity_type": "athlete",
        "sport": sport,
        "scraped_at": scraped_at,
        "scrape_version": scrape_version,
        "has_raw_scrape": has_raw,
    }
    for k in (
        "name",
        "school",
        "position",
        "conference",
        "class_year",
        "espn_id",
        "jersey_number",
        "height_inches",
        "weight_lbs",
        "hometown",
        "home_state",
        "is_active",
        "roster_status",
    ):
        if identity.get(k) is not None:
            row[k] = identity[k]
    parsed = raw_data or {}
    if parsed:
        row["raw_data_json"] = json.dumps(parsed, default=str)
        row["roster_seeded"] = bool(parsed.get("roster_seeded"))
    row.update(flatten_raw_data_export(parsed))
    return row


def build_training_row(
    *,
    entity_id: str,
    entity_type: str,
    sport: str | None,
    as_of: str | None,
    identity: dict[str, Any] | None = None,
    scores: dict[str, Any] | None = None,
    labels: dict[str, Any] | None = None,
    snapshot_features: dict[str, Any] | None = None,
    raw_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "sport": sport,
        "as_of": as_of,
    }
    if identity:
        for k in ("name", "school", "position", "conference", "class_year"):
            if identity.get(k) is not None:
                row[k] = identity[k]

    row.update(flatten_snapshot_features(snapshot_features))
    row.update(flatten_raw_data(raw_data))

    if scores:
        for k, col in (
            ("gravity_score", "gravity_score"),
            ("brand_score", "brand_score"),
            ("proof_score", "proof_score"),
            ("proximity_score", "proximity_score"),
            ("velocity_score", "velocity_score"),
            ("risk_score", "risk_score"),
            ("quality_score", "quality_score"),
            ("dollar_p50_usd", "dollar_p50_usd"),
            ("dollar_p10_usd", "dollar_p10_usd"),
            ("dollar_p90_usd", "dollar_p90_usd"),
            ("partnership_brand_score", "partnership_brand_score"),
            ("confidence", "score_confidence"),
            ("model_version", "model_version"),
        ):
            if scores.get(k) is not None:
                row[col] = scores[k]
        p50 = _safe_float(scores.get("dollar_p50_usd"))
        if p50 and p50 > 0:
            row["target_log_nil_usd"] = math.log1p(p50)
            row["target_nil_usd"] = p50
        proof = _safe_float(scores.get("proof_score"))
        if proof is not None:
            row["target_quality"] = proof
        grav = _safe_float(scores.get("gravity_score"))
        if grav is not None:
            row["target_gravity"] = grav
        impact = _safe_float(scores.get("win_impact_score"))
        if impact is not None:
            row["target_impact_score"] = impact
            row["win_impact_score"] = impact

    if labels:
        for k, col in (
            ("target_key", "label_target_key"),
            ("target_value", "label_target_value"),
            ("target_class", "label_target_class"),
            ("label_confidence", "label_confidence"),
            ("label_verified", "label_verified"),
            ("label_start_at", "label_start_at"),
            ("available_at", "label_available_at"),
        ):
            if labels.get(k) is not None:
                row[col] = labels[k]
        tv = _safe_float(labels.get("target_value"))
        if tv is not None and tv > 0:
            key = str(labels.get("target_key") or "")
            if "nil" in key or "deal" in key or "contract" in key:
                row["target_nil_usd"] = tv
                row["target_log_nil_usd"] = math.log1p(tv)
            elif key == "quality_score":
                row["target_quality"] = tv
            elif key == "target_impact_score" or key == "win_impact_score":
                row["target_impact_score"] = tv

    return row


def _csv_columns(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                columns.append(key)
    return columns


def _csv_row_values(row: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, (dict, list)):
            clean[k] = json.dumps(v, default=str)
        elif v is None:
            clean[k] = ""
        else:
            clean[k] = v
    return clean


def rows_to_csv(rows: list[dict[str, Any]]) -> str:
    """Serialize rows to CSV string (stdlib, no pandas required)."""
    import csv
    from io import StringIO

    if not rows:
        return ""
    columns = _csv_columns(rows)
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(_csv_row_values(row))
    return buf.getvalue()


def write_csv(
    rows: list[dict[str, Any]],
    path: str,
    *,
    compress: bool = False,
) -> int:
    """Write rows to CSV, streaming to disk. Optional gzip (.gz appended when compress=True)."""
    import csv
    import gzip
    from pathlib import Path

    p = Path(path)
    if compress and p.suffix != ".gz":
        p = p.with_suffix(p.suffix + ".gz")
    p.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        p.write_text("", encoding="utf-8")
        return 0

    columns = _csv_columns(rows)
    opener = gzip.open if p.suffix == ".gz" else open
    mode = "wt"
    encoding = None if p.suffix == ".gz" else "utf-8"
    with opener(p, mode, encoding=encoding, newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(_csv_row_values(row))
    return len(rows)
