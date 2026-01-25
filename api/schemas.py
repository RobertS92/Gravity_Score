#!/usr/bin/env python3
"""
API Schemas
===========

Pydantic models for request/response validation.

Author: Gravity Score Team
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================

class PlayerDataInput(BaseModel):
    """Input schema for player data"""
    
    player_name: str = Field(..., description="Player's full name")
    team: Optional[str] = Field(None, description="Current team")
    position: Optional[str] = Field(None, description="Playing position")
    
    # Identity
    age: Optional[int] = Field(None, ge=15, le=50)
    height: Optional[int] = Field(None, description="Height in inches")
    weight: Optional[int] = Field(None, description="Weight in pounds")
    birth_date: Optional[str] = None
    hometown: Optional[str] = None
    college: Optional[str] = None
    draft_year: Optional[int] = None
    draft_round: Optional[int] = None
    draft_pick: Optional[int] = None
    years_in_league: Optional[int] = None
    contract_value: Optional[float] = None
    
    # Brand
    instagram_followers: Optional[int] = Field(None, ge=0)
    twitter_followers: Optional[int] = Field(None, ge=0)
    tiktok_followers: Optional[int] = Field(None, ge=0)
    youtube_subscribers: Optional[int] = Field(None, ge=0)
    endorsement_count: Optional[int] = Field(None, ge=0)
    media_mentions: Optional[int] = Field(None, ge=0)
    
    # Proof (Performance)
    career_points: Optional[float] = Field(None, ge=0)
    career_yards: Optional[float] = Field(None, ge=0)
    career_touchdowns: Optional[int] = Field(None, ge=0)
    career_receptions: Optional[int] = Field(None, ge=0)
    career_sacks: Optional[float] = Field(None, ge=0)
    career_interceptions: Optional[int] = Field(None, ge=0)
    current_season_points: Optional[float] = Field(None, ge=0)
    current_season_yards: Optional[float] = Field(None, ge=0)
    pro_bowls: Optional[int] = Field(None, ge=0)
    all_pro_selections: Optional[int] = Field(None, ge=0)
    all_star_selections: Optional[int] = Field(None, ge=0)
    super_bowl_wins: Optional[int] = Field(None, ge=0)
    championships: Optional[int] = Field(None, ge=0)
    awards_count: Optional[int] = Field(None, ge=0)
    
    # Risk
    games_missed_career: Optional[int] = Field(None, ge=0)
    games_missed_last_season: Optional[int] = Field(None, ge=0)
    injury_risk_score: Optional[float] = Field(None, ge=0, le=100)
    controversy_risk_score: Optional[float] = Field(None, ge=0, le=100)
    
    # Velocity
    year_over_year_change: Optional[float] = None
    performance_trend: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "player_name": "Patrick Mahomes",
                "team": "Kansas City Chiefs",
                "position": "QB",
                "age": 28,
                "height": 75,
                "weight": 230,
                "career_points": 0,
                "career_yards": 28424,
                "career_touchdowns": 234,
                "pro_bowls": 6,
                "super_bowl_wins": 2,
                "instagram_followers": 5200000,
                "twitter_followers": 2100000
            }
        }


class BatchPlayerInput(BaseModel):
    """Input schema for batch scoring"""
    players: List[PlayerDataInput]


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class MLPrediction(BaseModel):
    """ML prediction result"""
    value: Any
    confidence: Optional[float] = Field(None, ge=0, le=1)
    model_version: Optional[str] = None


class PlayerScoreOutput(BaseModel):
    """Output schema for scored player"""
    
    player_name: str
    
    # Scores
    gravity_score: float = Field(..., description="Rule-based gravity score (0-100)")
    ml_market_value: Optional[float] = Field(None, description="ML predicted market value")
    ensemble_score: Optional[float] = Field(None, description="Ensemble of ML + rule-based")
    
    # ML Predictions
    ml_draft_prediction: Optional[MLPrediction] = None
    ml_contract_prediction: Optional[MLPrediction] = None
    ml_performance_trend: Optional[MLPrediction] = None
    ml_injury_risk: Optional[MLPrediction] = None
    
    # Component scores
    brand_score: Optional[float] = None
    proof_score: Optional[float] = None
    proximity_score: Optional[float] = None
    velocity_score: Optional[float] = None
    risk_score: Optional[float] = None
    
    # Metadata
    processed_at: datetime = Field(default_factory=datetime.now)
    data_quality: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "player_name": "Patrick Mahomes",
                "gravity_score": 94.5,
                "ml_market_value": 92.3,
                "ensemble_score": 93.4,
                "brand_score": 88.2,
                "proof_score": 96.8,
                "velocity_score": 91.5,
                "risk_score": 85.0,
                "processed_at": "2025-12-10T12:00:00"
            }
        }


class BatchScoreOutput(BaseModel):
    """Output schema for batch scoring"""
    players: List[PlayerScoreOutput]
    total_players: int
    processing_time_seconds: float


class ModelStatus(BaseModel):
    """Model status information"""
    model_name: str
    version: str
    trained_on: str
    performance_metrics: Dict[str, Any]
    feature_count: Optional[int] = None
    samples: Optional[int] = None


class ModelsStatusResponse(BaseModel):
    """Response for models status endpoint"""
    imputation_models: Dict[str, ModelStatus]
    prediction_models: Dict[str, ModelStatus]
    last_updated: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    models_loaded: Dict[str, int]
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

