"""Gravity ML inference package."""

from gravity_ml.inference.predict import SUPPORTED_SPORTS, score_athlete, score_brand, score_team
from gravity_ml.schemas import (
    ScoreAthleteRequest,
    ScoreAthleteResponse,
    ScoreBrandRequest,
    ScoreBrandResponse,
    ScoreTeamRequest,
    ScoreTeamResponse,
)

__all__ = [
    "SUPPORTED_SPORTS",
    "score_athlete",
    "score_team",
    "score_brand",
    "ScoreAthleteRequest",
    "ScoreAthleteResponse",
    "ScoreTeamRequest",
    "ScoreTeamResponse",
    "ScoreBrandRequest",
    "ScoreBrandResponse",
]
