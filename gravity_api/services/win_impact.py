"""Win-impact feature engineering and deterministic performance value scorer (CFB MVP)."""

from __future__ import annotations

import math
from typing import Any

from gravity_api.feature_engineering.types import AthleteFeatureSnapshot

CFB_EXPECTED_GAMES = 12

# ~30-feature MVP manifest for gravity_athlete_cfb_impact_v1
IMPACT_FEATURE_KEYS: tuple[str, ...] = (
    "games_played_season",
    "games_started",
    "gs_rate",
    "participation_index",
    "team_wins",
    "team_losses",
    "team_win_pct",
    "team_win_pct_percentile",
    "proof_performance_index_pctile",
    "proof_composite_pctile",
    "proof_composite_index",
    "proof_residual_team",
    "proof_x_participation",
    "proof_x_weak_team",
    "recruiting_stars",
    "recruiting_rank_national",
    "recruiting_outperformance",
    "velocity_composite_pctile",
    "velocity_proof_yoy",
    "data_quality_score",
    "external_quality_score",
    "all_american_count",
    "national_awards_count",
    "seasons_with_gp",
    "team_record_observed",
    "games_started_observed",
    "gp_observed",
    "impact_confidence",
    "win_impact_score_v0",
    "target_impact_score",
)


def _f(raw: dict[str, Any], key: str, default: float = 0.0) -> float:
    val = raw.get(key)
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _block_pctile(snapshot: AthleteFeatureSnapshot | None, block: str) -> float | None:
    if snapshot is None:
        return None
    comp = getattr(snapshot, block, None)
    if comp is None:
        return None
    if comp.composite_pctile is not None:
        return float(comp.composite_pctile)
    if comp.composite_index is not None:
        return float(comp.composite_index)
    return None


def _proof_pctile(raw: dict[str, Any], snapshot: AthleteFeatureSnapshot | None) -> float:
    snap = _block_pctile(snapshot, "proof")
    if snap is not None and snap > 0:
        return min(100.0, max(0.0, snap))
    for key in ("proof_performance_index_pctile", "proof_composite_pctile"):
        v = _f(raw, key)
        if v > 0:
            return min(100.0, max(0.0, v))
    return 0.0


def compute_participation_index(
    raw: dict[str, Any],
    *,
    expected_games: int = CFB_EXPECTED_GAMES,
) -> tuple[float, float]:
    gp = _f(raw, "games_played_season") or _f(raw, "gp")
    gs = _f(raw, "games_started") or _f(raw, "gs")
    gp_ratio = min(1.0, gp / max(expected_games, 1)) if gp > 0 else 0.0
    gs_rate = min(1.0, gs / max(gp, 1.0)) if gs > 0 and gp > 0 else (0.5 * gp_ratio if gp_ratio else 0.0)
    participation = 0.4 * gp_ratio + 0.6 * gs_rate
    return round(participation, 4), round(gs_rate, 4)


def compute_win_impact_features(
    raw: dict[str, Any],
    *,
    snapshot: AthleteFeatureSnapshot | None = None,
    sport: str = "cfb",
) -> dict[str, Any]:
    """Derive win-context and impact interaction features from raw + BPXVR snapshot."""
    expected = CFB_EXPECTED_GAMES if sport == "cfb" else 30
    participation, gs_rate = compute_participation_index(raw, expected_games=expected)
    proof_pct = _proof_pctile(raw, snapshot)
    team_win_pct = _f(raw, "team_win_pct")
    team_pctile = _f(raw, "team_win_pct_percentile")
    if team_pctile <= 0 and team_win_pct > 0:
        team_pctile = min(100.0, team_win_pct * 100.0)

    proof_residual = proof_pct - team_pctile if team_pctile > 0 else proof_pct
    proof_x_part = proof_pct * participation
    proof_x_weak = proof_pct * max(0.0, 1.0 - team_pctile / 100.0) if team_pctile > 0 else proof_pct * 0.5

    recruiting_pct = max(0.0, 100.0 - min(100.0, _f(raw, "recruiting_rank_national") / 50.0)) if _f(
        raw, "recruiting_rank_national"
    ) > 0 else _f(raw, "recruiting_stars") * 20.0
    recruiting_out = proof_pct - recruiting_pct if recruiting_pct > 0 else 0.0

    velocity_pct = _block_pctile(snapshot, "velocity") or _f(raw, "velocity_composite_pctile")
    hist = raw.get("proof_performance_index_history") or raw.get("proof_index_history")
    velocity_proof_yoy = 0.0
    if isinstance(hist, list) and len(hist) >= 2:
        try:
            velocity_proof_yoy = float(hist[-1]) - float(hist[-2])
        except (TypeError, ValueError):
            pass

    gp = _f(raw, "games_played_season") or _f(raw, "gp")
    gs = _f(raw, "games_started") or _f(raw, "gs")
    history = raw.get("season_stats_history")
    seasons_gp = 1 if gp > 0 else 0
    if isinstance(history, dict):
        seasons_gp = sum(
            1
            for blob in history.values()
            if isinstance(blob, dict)
            and (_f(blob, "gp") or _f(blob, "games_played_season") or _f(blob, "gamesPlayed")) > 0
        )

    ext_q = _f(raw, "external_quality_score")
    conf = 0.25
    if int(_f(raw, "team_record_observed")) == 1:
        conf += 0.2
    if gp > 0:
        conf += 0.15
    if gs > 0:
        conf += 0.1
    if proof_pct > 0:
        conf += 0.15
    if ext_q > 42:
        conf += 0.1
    conf = round(min(0.92, conf), 4)

    features: dict[str, Any] = {
        "games_played_season": gp if gp > 0 else None,
        "games_started": gs if gs > 0 else None,
        "gs_rate": gs_rate if gs_rate > 0 else None,
        "participation_index": participation,
        "team_wins": int(_f(raw, "team_wins")) if _f(raw, "team_wins") > 0 else None,
        "team_losses": int(_f(raw, "team_losses")) if _f(raw, "team_losses") > 0 else None,
        "team_win_pct": team_win_pct if team_win_pct > 0 else None,
        "team_win_pct_percentile": team_pctile if team_pctile > 0 else None,
        "proof_performance_index_pctile": proof_pct if proof_pct > 0 else None,
        "proof_composite_pctile": _f(raw, "proof_composite_pctile") or (proof_pct if proof_pct > 0 else None),
        "proof_composite_index": _f(raw, "proof_composite_index") or None,
        "proof_residual_team": round(proof_residual, 4),
        "proof_x_participation": round(proof_x_part, 4),
        "proof_x_weak_team": round(proof_x_weak, 4),
        "recruiting_stars": _f(raw, "recruiting_stars") or None,
        "recruiting_rank_national": _f(raw, "recruiting_rank_national") or None,
        "recruiting_outperformance": round(recruiting_out, 4) if recruiting_out else None,
        "velocity_composite_pctile": velocity_pct if velocity_pct > 0 else None,
        "velocity_proof_yoy": round(velocity_proof_yoy, 4) if velocity_proof_yoy else None,
        "data_quality_score": _f(raw, "data_quality_score") or None,
        "external_quality_score": ext_q if ext_q > 0 else None,
        "all_american_count": _f(raw, "all_american_count") or None,
        "national_awards_count": _f(raw, "national_awards_count") or None,
        "seasons_with_gp": seasons_gp,
        "team_record_observed": int(_f(raw, "team_record_observed")),
        "games_started_observed": 1 if gs > 0 else 0,
        "gp_observed": 1 if gp > 0 else 0,
        "impact_confidence": conf,
    }
    return {k: v for k, v in features.items() if v is not None}


def compute_win_impact_score_v0(
    raw: dict[str, Any],
    *,
    snapshot: AthleteFeatureSnapshot | None = None,
    sport: str = "cfb",
) -> float:
    """Deterministic 0–100 performance/win-impact index (Tier 2b)."""
    feats = compute_win_impact_features(raw, snapshot=snapshot, sport=sport)
    proof_pct = float(feats.get("proof_performance_index_pctile") or _proof_pctile(raw, snapshot))
    participation = float(feats.get("participation_index") or 0.0)
    team_pctile = float(feats.get("team_win_pct_percentile") or 0.0)
    team_factor = 0.5 + 0.5 * (team_pctile / 100.0) if team_pctile > 0 else 0.65

    raw_impact = proof_pct * participation * team_factor
    yoy = float(feats.get("velocity_proof_yoy") or 0.0)
    velocity_boost = max(-10.0, min(10.0, yoy * 5.0))

    ext = float(feats.get("external_quality_score") or 0.0)
    if ext > 42 and int(_f(raw, "external_quality_score_observed")) == 1:
        score = 0.55 * ext + 0.45 * raw_impact
    else:
        score = raw_impact + velocity_boost

    awards = _f(raw, "all_american_count") * 3.0 + _f(raw, "national_awards_count") * 2.0
    score += min(8.0, awards)
    return round(min(100.0, max(5.0, score)), 4)


def compute_target_impact_score(
    raw: dict[str, Any],
    *,
    snapshot: AthleteFeatureSnapshot | None = None,
    sport: str = "cfb",
) -> float:
    """Training label: v0 impact score (bootstrap until external win-share labels land)."""
    return compute_win_impact_score_v0(raw, snapshot=snapshot, sport=sport)


def merge_win_impact_into_raw(
    raw: dict[str, Any],
    *,
    snapshot: AthleteFeatureSnapshot | None = None,
    sport: str = "cfb",
) -> dict[str, Any]:
    """Attach impact features and scores to raw payload for ML vectorizer + API."""
    out = dict(raw)
    features = compute_win_impact_features(out, snapshot=snapshot, sport=sport)
    out.update(features)
    v0 = compute_win_impact_score_v0(out, snapshot=snapshot, sport=sport)
    out["win_impact_score_v0"] = v0
    out["win_impact_score"] = v0
    out["target_impact_score"] = compute_target_impact_score(out, snapshot=snapshot, sport=sport)
    return out


__all__ = [
    "IMPACT_FEATURE_KEYS",
    "compute_participation_index",
    "compute_target_impact_score",
    "compute_win_impact_features",
    "compute_win_impact_score_v0",
    "merge_win_impact_into_raw",
]
