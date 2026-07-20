"""Win-impact feature engineering and deterministic Value Score (winning impact).

Value Score (public) = how the athlete affects winning.
Gravity Score (public) = commercial / market value — separate path.
"""

from __future__ import annotations

import math
import re
from typing import Any

from gravity_api.feature_engineering.types import AthleteFeatureSnapshot

CFB_EXPECTED_GAMES = 12

# Season-length priors for participation_index (games_played / expected).
EXPECTED_GAMES_BY_SPORT: dict[str, int] = {
    "cfb": 12,
    "nfl": 17,
    "nba": 82,
    "wnba": 40,
    "ncaab_mens": 35,
    "ncaab_womens": 35,
    "ncaa_baseball": 56,
    "ncaa_volleyball": 30,
}


def expected_games_for_sport(sport: str) -> int:
    return EXPECTED_GAMES_BY_SPORT.get((sport or "").lower(), 30)


# ESPN NFL athlete stats expose gamesPlayed but never gamesStarted.
# For skill + every-down positions that appear in games, treat starts ≈ GP
# rather than the generic 0.5×gp_ratio prior (which crushed Value Score).
NFL_SKILL_POSITIONS = frozenset({"QB", "RB", "WR", "TE", "FB"})
# Defenders / specialists who typically play when active (not rotational depth
# with true GS tracking). Still infer gs≈gp so participation isn't halved.
NFL_EVERY_DOWN_POSITIONS = frozenset(
    {"LB", "ILB", "OLB", "MLB", "DE", "DT", "DL", "CB", "S", "DB", "SS", "FS", "OL", "OT", "OG", "C", "G", "K", "PK", "P"}
)

def _position_token(raw: dict[str, Any], position: str | None = None) -> str:
    for candidate in (
        position,
        raw.get("position_group"),
        raw.get("position"),
    ):
        if candidate is None or candidate == "":
            continue
        text = str(candidate).strip().upper()
        if not text:
            continue
        # "Quarterback" / "QB - Offense" → first token
        token = text.replace("-", " ").split()[0]
        return token
    return ""


def resolve_games_started(
    raw: dict[str, Any],
    *,
    sport: str = "cfb",
    position: str | None = None,
) -> tuple[float, bool]:
    """Return (games_started, observed).

    ``observed`` is True only when ESPN/ASS provided an explicit starts value.
    NFL skill-position inference (gs=gp) returns observed=False.
    """
    gs = _f(raw, "games_started") or _f(raw, "gs")
    if gs > 0:
        return gs, True
    gp = _f(raw, "games_played_season") or _f(raw, "gp")
    if (
        (sport or "").lower() == "nfl"
        and gp > 0
        and _position_token(raw, position) in (NFL_SKILL_POSITIONS | NFL_EVERY_DOWN_POSITIONS)
    ):
        return gp, False
    return 0.0, False


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


def _major_award_evidence(raw: dict[str, Any]) -> dict[str, float]:
    """Extract conservative career-award evidence from structured source text."""
    blobs: list[Any] = []
    for key in ("major_awards_json", "national_awards_json", "achievements_json"):
        entries = raw.get(key)
        if isinstance(entries, list):
            blobs.extend(entries)
    text_parts: list[str] = []
    for item in blobs:
        if isinstance(item, dict):
            text_parts.append(str(item.get("title") or item.get("name") or ""))
        elif item:
            text_parts.append(str(item))
    text = " ".join(text_parts).lower()

    def count_for(pattern: str) -> float:
        matches = [int(value) for value in re.findall(rf"(\d+)x\s+{pattern}", text)]
        if matches:
            return float(max(matches))
        return 1.0 if re.search(pattern, text) else 0.0

    return {
        "mvp": count_for(r"(?:wnba\s+)?mvp"),
        "dpoy": count_for(
            r"(?:ap\s+)?(?:def\.?\s*|defensive\s+)(?:player\s+of\s+the\s+year|poy)"
        ),
        "champion": count_for(r"(?:nba|wnba)?\s*champ"),
    }


def _season_scoring_rebounds(raw: dict[str, Any]) -> tuple[float, float]:
    """Return (avg_points, avg_rebounds), deriving from season totals when needed."""
    gp = _f(raw, "games_played_season") or _f(raw, "gp")
    avg_points = (
        _f(raw, "avgPoints")
        or _f(raw, "avg_points")
        or _f(raw, "ppg")
        or _f(raw, "points_per_game")
    )
    avg_rebounds = (
        _f(raw, "avgRebounds")
        or _f(raw, "avg_rebounds")
        or _f(raw, "rpg")
        or _f(raw, "rebounds_per_game")
    )
    if gp > 0:
        if avg_points <= 0:
            pts = _f(raw, "pts") or _f(raw, "points")
            if pts > 0:
                avg_points = pts / gp
        if avg_rebounds <= 0:
            reb = _f(raw, "reb") or _f(raw, "rebounds")
            if reb > 0:
                avg_rebounds = reb / gp
    return avg_points, avg_rebounds


def _block_pctile(snapshot: AthleteFeatureSnapshot | None, block: str) -> float | None:
    if snapshot is None:
        return None
    comp = getattr(snapshot, block, None)
    if comp is None:
        return None
    if comp.composite_pctile is not None:
        return float(comp.composite_pctile)
    if comp.composite_index is not None:
        # Unbounded z-sum — map to 0–100; do not return raw index as a pctile.
        from gravity_composite.composite import perf_index_to_score

        mapped = perf_index_to_score(comp.composite_index)
        return float(mapped) if mapped is not None else None
    return None


def _proof_pctile(raw: dict[str, Any], snapshot: AthleteFeatureSnapshot | None) -> float:
    snap = _block_pctile(snapshot, "proof")
    if snap is not None and snap > 0:
        return min(100.0, max(0.0, snap))
    for key in (
        "proof_performance_index_pctile",
        "proof_composite_pctile",
        "proof.performance_index_pctile",
    ):
        v = _f(raw, key)
        if v > 0:
            return min(100.0, max(0.0, v))
    # When cohort percentile is masked (small/missing peer set) but we still
    # have a performance index, map it to a usable 0–100 proof signal so
    # starters with real counting stats are not floored at V=5.
    for key in ("proof_composite_index", "proof_performance_index_raw"):
        idx = raw.get(key)
        if idx is None and snapshot is not None and getattr(snapshot, "proof", None) is not None:
            idx = snapshot.proof.composite_index
        if idx is None:
            continue
        try:
            from gravity_composite.composite import perf_index_to_score

            mapped = perf_index_to_score(float(idx))
            if mapped is not None and mapped > 0:
                return min(100.0, max(0.0, float(mapped)))
        except (TypeError, ValueError):
            continue
    return 0.0


def compute_participation_index(
    raw: dict[str, Any],
    *,
    expected_games: int = CFB_EXPECTED_GAMES,
    sport: str = "cfb",
    position: str | None = None,
) -> tuple[float, float]:
    gp = _f(raw, "games_played_season") or _f(raw, "gp")
    gs, _observed = resolve_games_started(raw, sport=sport, position=position)
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
    expected = expected_games_for_sport(sport)
    position = str(raw.get("position_group") or raw.get("position") or "") or None
    participation, gs_rate = compute_participation_index(
        raw, expected_games=expected, sport=sport, position=position
    )
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
    gs, gs_observed = resolve_games_started(raw, sport=sport, position=position)
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
    if gs_observed:
        conf += 0.1
    elif gs > 0:
        conf += 0.05  # inferred starts (NFL skill) — partial credit
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
        "games_started_observed": 1 if gs_observed else 0,
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
    """Position-aware additive winning-impact score.

    Proof is primary. Availability and starter status modify rather than
    multiply it; team context is intentionally small. Missing evidence shrinks
    toward a neutral prior instead of collapsing to a hard floor.
    """
    feats = compute_win_impact_features(raw, snapshot=snapshot, sport=sport)
    proof_pct = float(feats.get("proof_performance_index_pctile") or _proof_pctile(raw, snapshot))
    expected = expected_games_for_sport(sport)
    gp = float(feats.get("games_played_season") or 0.0)
    gp_ratio = min(1.0, gp / max(expected, 1)) if gp > 0 else 0.0
    gs_rate = float(feats.get("gs_rate") or 0.0)
    gs_observed = int(feats.get("games_started_observed") or 0) == 1
    position = _position_token(raw)

    proof_observed = proof_pct > 0
    ext = float(feats.get("external_quality_score") or 0.0)
    ext_observed = int(_f(raw, "external_quality_score_observed")) == 1 and ext > 0
    if not proof_observed and ext_observed:
        proof_pct = ext
    elif not proof_observed:
        # Position-aware neutral priors. Full-season OL/defenders have genuine
        # impact even when public box-score proof is sparse; specialists remain
        # conservative. No participation evidence receives a below-neutral prior.
        if gp_ratio <= 0:
            proof_pct = 38.0
        elif position in {"OL", "OT", "OG", "C", "G", "LB", "ILB", "OLB", "MLB", "DE", "DT", "DL", "CB", "S", "DB"}:
            proof_pct = 50.0 + 12.0 * gp_ratio
        elif position in {"K", "PK", "P", "LS"}:
            proof_pct = 46.0 + 6.0 * gp_ratio
        else:
            proof_pct = 46.0 + 10.0 * gp_ratio

    # Convert proof percentile to an impact display scale. Ordinary season
    # production alone should not mint a 90; that tail is reserved for
    # sustained, award-backed dominance handled below.
    proof_knots = (
        (0.0, 25.0),
        (20.0, 38.0),
        (40.0, 52.0),
        (50.0, 60.0),
        (60.0, 68.0),
        (70.0, 76.0),
        (80.0, 81.5),
        (90.0, 85.5),
        (97.0, 89.0),
        (100.0, 91.0),
    )
    proof_x = max(0.0, min(100.0, proof_pct))
    proof_impact = proof_knots[-1][1]
    for (x0, y0), (x1, y1) in zip(proof_knots, proof_knots[1:]):
        if proof_x <= x1:
            t = (proof_x - x0) / max(x1 - x0, 1e-9)
            proof_impact = y0 + t * (y1 - y0)
            break

    availability_score = 35.0 + 65.0 * gp_ratio if gp > 0 else 40.0
    if gs_observed:
        starter_score = 40.0 + 60.0 * min(1.0, gs_rate)
    elif sport == "nfl" and position in NFL_SKILL_POSITIONS and gp > 0:
        # ESPN commonly omits GS for offensive skill players; substantial
        # availability plus position-native proof is strong starter evidence.
        starter_score = 75.0 + 25.0 * gp_ratio
    elif gp > 0:
        # Unknown starts are not treated as either a bench role or a full start.
        starter_score = 55.0 + 10.0 * gp_ratio
    else:
        starter_score = 40.0

    team_pctile = float(feats.get("team_win_pct_percentile") or 55.0)
    # Regress team context strongly toward neutral so individual Value does not
    # become a disguised team-wins score.
    team_score = 50.0 + 0.40 * (max(0.0, min(100.0, team_pctile)) - 50.0)
    score = (
        0.72 * proof_impact
        + 0.14 * availability_score
        + 0.08 * starter_score
        + 0.06 * team_score
    )

    # Position leverage is small and evidence-gated. It does not replace proof.
    if sport == "nfl" and position == "QB" and proof_pct >= 80 and gp_ratio >= 0.70:
        score += 6.0

    if ext_observed:
        score += max(-2.0, min(2.0, (ext - 50.0) * 0.04))

    yoy = float(feats.get("velocity_proof_yoy") or 0.0)
    score += max(-1.0, min(1.0, yoy))

    awards = (
        _f(raw, "all_american_count") * 1.5
        + _f(raw, "national_awards_count") * 1.5
        + _f(raw, "all_pro_count") * 2.0
        + _f(raw, "mvp_count") * 3.0
    )
    score += min(6.0, awards)

    # Career awards and all-in production are strong absolute winning-impact
    # evidence. This feature-based gate lets historically dominant athletes
    # reach the elite tail without assigning scores by name.
    award_evidence = _major_award_evidence(raw)
    rating = _f(raw, "NBARating")
    avg_points, avg_rebounds = _season_scoring_rebounds(raw)
    elite_production = (
        rating >= 35.0
        or (avg_points >= 20.0 and avg_rebounds >= 8.0)
        or proof_pct >= 97.0
    )
    if award_evidence["mvp"] > 0 and elite_production and gp_ratio >= 0.40:
        elite_floor = (
            93.0
            + min(3.0, award_evidence["mvp"])
            + min(1.0, 0.5 * award_evidence["dpoy"])
        )
        score = max(score, elite_floor)
    elif award_evidence["dpoy"] > 0 and elite_production and gp_ratio >= 0.40:
        score = max(score, 91.0 + min(2.0, award_evidence["dpoy"] * 0.5))
    elif (
        (sport or "").lower() == "nfl"
        and position in NFL_EVERY_DOWN_POSITIONS
        and gp_ratio >= 0.70
        and (_f(raw, "all_pro_count") >= 2.0 or award_evidence["dpoy"] > 0)
    ):
        # Multiple All-Pros / DPOY for every-down defenders is absolute
        # winning-impact evidence even when public box-score proof is sparse.
        all_pro = _f(raw, "all_pro_count")
        defender_floor = 84.0 + min(6.0, max(0.0, all_pro - 1.0) * 2.5)
        if award_evidence["dpoy"] > 0:
            defender_floor = max(defender_floor, 89.0 + min(2.0, award_evidence["dpoy"]))
        score = max(score, min(93.0, defender_floor))
    elif (
        (sport or "").lower() == "wnba"
        and gp_ratio >= 0.40
        and avg_rebounds >= 10.0
        and avg_points >= 10.0
    ):
        # Elite board presence is a durable WNBA winning-impact signal. Sustained
        # double-digit rebounding with starter-level scoring clears ~80 Value
        # without MVP awards (those remain reserved for the ~95+ tail).
        reb_floor = (
            74.0
            + min(8.0, (avg_rebounds - 10.0) * 2.5)
            + min(3.0, max(0.0, avg_points - 10.0) * 0.35)
        )
        score = max(score, min(88.0, reb_floor))
    elif (
        (sport or "").lower() == "nba"
        and gp_ratio >= 0.55
        and avg_points >= 24.0
        and (
            _f(raw, "all_star_count") >= 2.0
            or _f(raw, "all_nba_count") >= 1.0
            or proof_pct >= 88.0
        )
    ):
        # High-usage NBA creators with repeated star recognition should land in
        # the public Impact tail even when games-started is missing from feeds.
        all_star = _f(raw, "all_star_count")
        all_nba = _f(raw, "all_nba_count")
        nba_star_floor = (
            86.5
            + min(1.5, max(0.0, avg_points - 24.0) * 0.20)
            + min(1.0, all_star * 0.20)
            + min(1.0, all_nba * 0.35)
            + (0.75 if proof_pct >= 75.0 else 0.0)
        )
        score = max(score, min(92.0, nba_star_floor))

    # If proof itself is imputed, shrink gently toward neutral and expose the
    # lower confidence through impact_confidence.
    if not proof_observed and not ext_observed:
        score = 0.75 * score + 0.25 * 55.0

    return round(min(98.0, max(25.0, score)), 4)


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
    # Public Value Score alias — winning impact (not commercial Gravity).
    out["value_score"] = v0
    out["value_score_source"] = "win_impact_v1_additive"
    out["target_impact_score"] = compute_target_impact_score(out, snapshot=snapshot, sport=sport)
    return out


__all__ = [
    "EXPECTED_GAMES_BY_SPORT",
    "IMPACT_FEATURE_KEYS",
    "NFL_SKILL_POSITIONS",
    "compute_participation_index",
    "compute_target_impact_score",
    "compute_win_impact_features",
    "compute_win_impact_score_v0",
    "expected_games_for_sport",
    "merge_win_impact_into_raw",
    "resolve_games_started",
]
