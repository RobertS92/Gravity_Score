"""Football (CFB) position proof composites — all positions."""

from __future__ import annotations

from gravity_api.feature_engineering.sport_specs._shared import (
    ACHIEVEMENT_WEIGHTS,
    BRAND_METRICS,
    COLLEGE_RECRUITING_KEYS,
    PROXIMITY_COLLEGE_METRICS,
    RISK_METRICS,
    VELOCITY_METRICS,
)
from gravity_api.feature_engineering.types import PositionProofSpec, SportFeatureSpec, StatWeight

_FOOTBALL_POSITIONS: tuple[PositionProofSpec, ...] = (
    PositionProofSpec(
        "QB",
        ("QB", "QUARTERBACK"),
        (
            StatWeight("pass_yards", 0.22),
            StatWeight("pass_td", 0.18),
            StatWeight("passer_rating", 0.20),
            StatWeight("qbr", 0.15),
            StatWeight("completion_pct", 0.10),
            StatWeight("pass_int", 0.10, "lower"),
            StatWeight("rush_yards", 0.05),
        ),
        expected_games=12,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "RB",
        ("RB", "FB", "TB", "RUNNING BACK"),
        (
            StatWeight("rush_yards", 0.30),
            StatWeight("rush_td", 0.20),
            StatWeight("yards_per_carry", 0.20),
            StatWeight("scrimmage_yards", 0.15),
            StatWeight("receptions", 0.08),
            StatWeight("fumbles", 0.07, "lower"),
        ),
        expected_games=12,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "WR",
        ("WR", "WIDE RECEIVER"),
        (
            StatWeight("rec_yards", 0.30),
            StatWeight("receptions", 0.20),
            StatWeight("rec_td", 0.22),
            StatWeight("yards_per_catch", 0.18),
            StatWeight("scrimmage_yards", 0.10),
        ),
        expected_games=12,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "TE",
        ("TE", "TIGHT END"),
        (
            StatWeight("rec_yards", 0.28),
            StatWeight("receptions", 0.22),
            StatWeight("rec_td", 0.20),
            StatWeight("yards_per_catch", 0.15),
            StatWeight("blocks_grade", 0.15),
        ),
        expected_games=12,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "OL",
        ("OL", "OT", "OG", "OC", "C", "G", "T", "LT", "RT", "LG", "RG", "IOL"),
        (
            StatWeight("games_started", 0.35),
            StatWeight("pancakes", 0.20),
            StatWeight("sacks_allowed", 0.20, "lower"),
            StatWeight("penalties", 0.15, "lower"),
            StatWeight("team_rush_yards", 0.10),
        ),
        expected_games=12,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "DL",
        ("DL", "DE", "DT", "NT", "EDGE"),
        (
            StatWeight("tackles", 0.20),
            StatWeight("sacks", 0.30),
            StatWeight("tfl", 0.25),
            StatWeight("qb_hits", 0.15),
            StatWeight("forced_fumbles", 0.10),
        ),
        expected_games=12,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "LB",
        ("LB", "ILB", "OLB", "MLB", "WLB", "SLB"),
        (
            StatWeight("tackles", 0.30),
            StatWeight("tfl", 0.20),
            StatWeight("sacks", 0.15),
            StatWeight("interceptions", 0.20),
            StatWeight("passes_defended", 0.15),
        ),
        expected_games=12,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "DB",
        ("DB", "CB", "S", "FS", "SS", "SAF", "NICKEL"),
        (
            StatWeight("tackles", 0.20),
            StatWeight("interceptions", 0.30),
            StatWeight("passes_defended", 0.25),
            StatWeight("forced_fumbles", 0.10),
            StatWeight("completion_pct_allowed", 0.15, "lower"),
        ),
        expected_games=12,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
    PositionProofSpec(
        "K",
        ("K", "PK", "P", "PUNTER", "LS"),
        (
            StatWeight("fg_pct", 0.35),
            StatWeight("fg_made", 0.20),
            StatWeight("xp_pct", 0.20),
            StatWeight("long_fg", 0.15),
            StatWeight("punt_avg", 0.10),
        ),
        expected_games=12,
        recruiting_stats=COLLEGE_RECRUITING_KEYS,
        achievement_weights=ACHIEVEMENT_WEIGHTS,
    ),
)

CFB_SPEC = SportFeatureSpec(
    sport="cfb",
    league="ncaa",
    display_name="College Football",
    terminal_visible=True,
    position_groups=_FOOTBALL_POSITIONS,
    brand_metrics=BRAND_METRICS,
    proximity_metrics=PROXIMITY_COLLEGE_METRICS,
    velocity_metrics=VELOCITY_METRICS,
    risk_metrics=RISK_METRICS,
    min_games_for_proof_pctile=4,
)
