"""Sport-specific pipeline and model routing."""

from __future__ import annotations

from dataclasses import dataclass

from gravity_api.feature_engineering.constants import FEATURE_SCHEMA_VERSION
from gravity_api.scraper_registry.sports import SPORTS


@dataclass(frozen=True)
class SportPipelineConfig:
    sport: str
    league: str
    model_key: str
    model_version: str
    ml_endpoint: str
    fallback_endpoint: str
    feature_schema_version: str
    terminal_visible: bool
    college_pro_bridge: bool


def _cfg(sport: str, league: str, *, pro: bool = False) -> SportPipelineConfig:
    meta = SPORTS[sport]
    return SportPipelineConfig(
        sport=sport,
        league=league,
        model_key=f"gravity_athlete_{sport}_value_v1",
        model_version="1.0.0",
        ml_endpoint=f"/score/athlete/{sport}",
        fallback_endpoint="/score/athlete",
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        terminal_visible=bool(meta.get("terminal_visible")),
        college_pro_bridge=pro,
    )


ALL_SPORT_PIPELINES: dict[str, SportPipelineConfig] = {
    "cfb": SportPipelineConfig(
        sport="cfb",
        league="ncaa",
        model_key="gravity_athlete_cfb_value_v1",
        model_version="1.1.0-beta",
        ml_endpoint="/score/athlete/cfb",
        fallback_endpoint="/score/athlete",
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        terminal_visible=bool(SPORTS["cfb"].get("terminal_visible")),
        college_pro_bridge=False,
    ),
    "ncaab_mens": _cfg("ncaab_mens", "ncaa"),
    "ncaab_womens": _cfg("ncaab_womens", "ncaa"),
    "ncaa_baseball": _cfg("ncaa_baseball", "ncaa"),
    "ncaa_volleyball": _cfg("ncaa_volleyball", "ncaa"),
    "nfl": _cfg("nfl", "nfl", pro=True),
    "nba": _cfg("nba", "nba", pro=True),
    "wnba": _cfg("wnba", "wnba", pro=True),
}


def get_sport_pipeline_config(sport: str) -> SportPipelineConfig:
    key = sport.strip().lower()
    if key not in ALL_SPORT_PIPELINES:
        raise KeyError(f"No pipeline config for sport: {sport}")
    return ALL_SPORT_PIPELINES[key]
