"""Request/response models for gravity-ml scoring API."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ScoreAthleteRequest(BaseModel):
    athlete_id: str
    sport: str
    raw_data: dict[str, Any] = Field(default_factory=dict)
    model_key: Optional[str] = None
    model_version: Optional[str] = None
    feature_schema_version: Optional[str] = None
    feature_snapshot: Optional[dict[str, Any]] = None
    partial_scoring: bool = False


class ScoreAthleteResponse(BaseModel):
    athlete_id: str
    sport: str
    model_key: str
    model_version: str
    gravity_score: float
    quality_score: Optional[float] = None
    # Winning impact (Value Score). Distinct from commercial gravity_score.
    value_score: Optional[float] = None
    value_score_source: Optional[str] = None
    brand_score: float
    proof_score: float
    proximity_score: float
    velocity_score: float
    risk_score: float
    confidence: float = 0.5
    brand_gravity_score: Optional[float] = None
    partnership_brand_score: Optional[float] = None
    partnership_top_brands: Optional[list[dict[str, Any]]] = None
    dollar_p10_usd: Optional[float] = None
    dollar_p50_usd: Optional[float] = None
    dollar_p90_usd: Optional[float] = None
    dollar_confidence: Optional[dict[str, Any]] = None
    shap_values: Optional[dict[str, float]] = None
    fallback_used: bool = False
    feature_schema_version: Optional[str] = None


class ScoreTeamRequest(BaseModel):
    team_id: str
    sport: str
    raw_data: dict[str, Any] = Field(default_factory=dict)
    model_key: Optional[str] = None
    model_version: Optional[str] = None


class ScoreTeamResponse(BaseModel):
    team_id: str
    sport: str
    model_key: str
    model_version: str
    gravity_score: float
    quality_score: Optional[float] = None
    brand_score: float = 0.0
    proof_score: float = 0.0
    proximity_score: float = 0.0
    velocity_score: float = 0.0
    risk_score: float = 0.0
    confidence: float = 0.5
    fallback_used: bool = False


class ScoreBrandRequest(BaseModel):
    brand_id: str
    raw_data: dict[str, Any] = Field(default_factory=dict)
    model_key: Optional[str] = None


class ScoreBrandResponse(BaseModel):
    brand_id: str
    model_key: str
    model_version: str
    gravity_score: float
    reach_score: float = 0.0
    authenticity_score: float = 0.0
    value_score: float = 0.0
    fit_score: float = 0.0
    stability_score: float = 0.0
    category: Optional[str] = None
    prestige_score: Optional[float] = None
    fallback_used: bool = False


class ScoreFitRequest(BaseModel):
    athlete_id: str
    brand_id: str
    sport: str
    raw_data: dict[str, Any] = Field(default_factory=dict)


class ScoreFitResponse(BaseModel):
    athlete_id: str
    brand_id: str
    fit_score: float
    model_version: str = "1.0.0-heuristic-fit"
    fallback_used: bool = True
