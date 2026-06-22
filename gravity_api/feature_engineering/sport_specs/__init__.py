"""Load sport feature specs for all target sports."""

from __future__ import annotations

from gravity_api.feature_engineering.sport_specs.cfb import CFB_SPEC
from gravity_api.feature_engineering.sport_specs.nba import NBA_SPEC
from gravity_api.feature_engineering.sport_specs.ncaa_baseball import NCAA_BASEBALL_SPEC
from gravity_api.feature_engineering.sport_specs.ncaa_volleyball import NCAA_VOLLEYBALL_SPEC
from gravity_api.feature_engineering.sport_specs.ncaab_mens import NCAAB_MENS_SPEC
from gravity_api.feature_engineering.sport_specs.ncaab_womens import NCAAB_WOMENS_SPEC
from gravity_api.feature_engineering.sport_specs.nfl import NFL_SPEC
from gravity_api.feature_engineering.sport_specs.wnba import WNBA_SPEC
from gravity_api.feature_engineering.types import PositionProofSpec, SportFeatureSpec

ALL_SPORT_SPECS: tuple[SportFeatureSpec, ...] = (
    CFB_SPEC,
    NCAAB_MENS_SPEC,
    NCAAB_WOMENS_SPEC,
    NCAA_BASEBALL_SPEC,
    NCAA_VOLLEYBALL_SPEC,
    NFL_SPEC,
    NBA_SPEC,
    WNBA_SPEC,
)

SPECS_BY_SPORT: dict[str, SportFeatureSpec] = {s.sport: s for s in ALL_SPORT_SPECS}


def get_sport_spec(sport: str) -> SportFeatureSpec:
    key = sport.strip().lower()
    if key not in SPECS_BY_SPORT:
        raise KeyError(f"No feature spec for sport: {sport}")
    return SPECS_BY_SPORT[key]


def get_position_spec(sport: str, position_group: str) -> PositionProofSpec:
    spec = get_sport_spec(sport)
    key = position_group.strip().upper()
    for pg in spec.position_groups:
        if pg.position_group == key:
            return pg
    raise KeyError(f"No position spec for {sport}/{position_group}")


def all_position_groups(sport: str) -> tuple[str, ...]:
    return tuple(pg.position_group for pg in get_sport_spec(sport).position_groups)


def export_specs_json() -> dict:
    """Export all specs for external tools (gravity-ml, docs)."""
    out: dict = {"sports": {}}
    for spec in ALL_SPORT_SPECS:
        out["sports"][spec.sport] = {
            "league": spec.league,
            "display_name": spec.display_name,
            "terminal_visible": spec.terminal_visible,
            "college_pro_bridge": spec.college_pro_bridge,
            "min_games_for_proof_pctile": spec.min_games_for_proof_pctile,
            "position_groups": {
                pg.position_group: {
                    "aliases": list(pg.aliases),
                    "expected_games": pg.expected_games,
                    "performance_stats": [
                        {"stat_key": s.stat_key, "weight": s.weight, "direction": s.direction}
                        for s in pg.performance_stats
                    ],
                    "recruiting_stats": list(pg.recruiting_stats),
                    "achievement_weights": pg.achievement_weights,
                }
                for pg in spec.position_groups
            },
            "brand_metrics": [m.metric_key for m in spec.brand_metrics],
            "proximity_metrics": [m.metric_key for m in spec.proximity_metrics],
            "velocity_metrics": [m.metric_key for m in spec.velocity_metrics],
            "risk_metrics": [m.metric_key for m in spec.risk_metrics],
        }
    return out
