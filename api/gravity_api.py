#!/usr/bin/env python3
"""
Gravity Score API
=================

FastAPI server for real-time player scoring and predictions.

Usage:
    uvicorn api.gravity_api:app --reload --port 8000

Author: Gravity Score Team
"""

import logging
import sys
from pathlib import Path
from typing import List
import pandas as pd
from datetime import datetime
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.schemas import (
    PlayerDataInput, BatchPlayerInput,
    PlayerScoreOutput, BatchScoreOutput,
    ModelStatus, ModelsStatusResponse,
    HealthResponse, ErrorResponse,
    MLPrediction
)
from api.model_cache import model_cache

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Gravity Score API",
    description="Real-time API for player market value scoring and predictions",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# STARTUP / SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Load models on startup"""
    logger.info("=" * 80)
    logger.info("🚀 STARTING GRAVITY SCORE API")
    logger.info("=" * 80)
    
    success = model_cache.load_models()
    
    if success:
        logger.info("✅ API ready!")
    else:
        logger.warning("⚠️  API started but some models failed to load")
    
    logger.info("=" * 80)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Gravity Score API...")


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/", tags=["General"])
async def root():
    """Root endpoint"""
    return {
        "message": "Gravity Score API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """
    Health check endpoint
    
    Returns API status and models loaded
    """
    status = model_cache.get_status()
    
    return HealthResponse(
        status="healthy" if status['models_loaded'] else "degraded",
        version="1.0.0",
        models_loaded={
            "imputation": status['imputation_models'],
            "prediction": status['prediction_models']
        }
    )


@app.post("/score/player", response_model=PlayerScoreOutput, tags=["Scoring"])
async def score_player(player: PlayerDataInput):
    """
    Score a single player
    
    Applies imputation, feature engineering, ML predictions, and gravity score calculation.
    
    Returns:
        Scored player with gravity score and ML predictions
    """
    try:
        start_time = time.time()
        
        # Convert input to DataFrame
        player_dict = player.dict()
        df = pd.DataFrame([player_dict])
        
        # Flatten column names to match expected format
        df = _flatten_column_names(df)
        
        # Process through pipeline
        df = _process_player_data(df)
        
        # Extract results
        result = _extract_player_result(df.iloc[0], player.player_name)
        
        processing_time = time.time() - start_time
        logger.info(f"Scored {player.player_name} in {processing_time:.3f}s")
        
        return result
        
    except Exception as e:
        logger.error(f"Error scoring player: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/score/batch", response_model=BatchScoreOutput, tags=["Scoring"])
async def score_batch(batch: BatchPlayerInput):
    """
    Score multiple players in batch
    
    Efficient batch processing with shared feature engineering.
    
    Returns:
        Batch results with all scored players
    """
    try:
        start_time = time.time()
        
        # Convert inputs to DataFrame
        players_data = [p.dict() for p in batch.players]
        df = pd.DataFrame(players_data)
        
        # Flatten column names
        df = _flatten_column_names(df)
        
        # Process through pipeline
        df = _process_player_data(df)
        
        # Extract results
        results = []
        for idx, row in df.iterrows():
            player_name = batch.players[idx].player_name
            result = _extract_player_result(row, player_name)
            results.append(result)
        
        processing_time = time.time() - start_time
        logger.info(f"Scored {len(results)} players in {processing_time:.3f}s")
        
        return BatchScoreOutput(
            players=results,
            total_players=len(results),
            processing_time_seconds=processing_time
        )
        
    except Exception as e:
        logger.error(f"Error scoring batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predict/draft/{player_name}", tags=["Predictions"])
async def predict_draft(player_name: str):
    """
    Predict draft position for a college player
    
    Requires the player to be scored first via /score/player
    """
    # This is a simplified version - in production, you'd look up player data
    raise HTTPException(
        status_code=501,
        detail="Please use /score/player endpoint with player data to get draft predictions"
    )


@app.get("/predict/contract/{player_name}", tags=["Predictions"])
async def predict_contract(player_name: str):
    """
    Predict contract value for a professional player
    
    Requires the player to be scored first via /score/player
    """
    raise HTTPException(
        status_code=501,
        detail="Please use /score/player endpoint with player data to get contract predictions"
    )


@app.get("/models/status", response_model=ModelsStatusResponse, tags=["Models"])
async def models_status():
    """
    Get status of all loaded models
    
    Returns version, performance metrics, and metadata for each model.
    """
    registry = model_cache.registry or {}
    imputation_models = {}
    for model_name, model_info in registry.get('imputation_models', {}).items():
        imputation_models[model_name] = ModelStatus(
            model_name=model_name,
            version=model_info.get('version', '1.0.0'),
            trained_on=model_info.get('trained_on', 'unknown'),
            performance_metrics=model_info.get('performance', {}),
            samples=model_info.get('samples')
        )
    
    prediction_models = {}
    for model_name, model_info in registry.get('prediction_models', {}).items():
        prediction_models[model_name] = ModelStatus(
            model_name=model_name,
            version=model_info.get('version', '1.0.0'),
            trained_on=model_info.get('trained_on', 'unknown'),
            performance_metrics=model_info.get('performance', {}),
            feature_count=model_info.get('feature_count')
        )
    
    return ModelsStatusResponse(
        imputation_models=imputation_models,
        prediction_models=prediction_models,
        last_updated=registry.get('last_updated', 'external_ml_repo'),
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _flatten_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'identity.', 'brand.', 'proof.' prefixes to match expected format"""
    df = df.copy()
    
    # Mapping of flat names to nested names
    identity_cols = [
        'age', 'height', 'weight', 'birth_date', 'hometown', 'college',
        'draft_year', 'draft_round', 'draft_pick', 'years_in_league', 'contract_value'
    ]
    
    brand_cols = [
        'instagram_followers', 'twitter_followers', 'tiktok_followers',
        'youtube_subscribers', 'endorsement_count', 'media_mentions'
    ]
    
    proof_cols = [
        'career_points', 'career_yards', 'career_touchdowns', 'career_receptions',
        'career_sacks', 'career_interceptions', 'current_season_points',
        'current_season_yards', 'pro_bowls', 'all_pro_selections',
        'all_star_selections', 'super_bowl_wins', 'championships', 'awards_count'
    ]
    
    risk_cols = [
        'games_missed_career', 'games_missed_last_season',
        'injury_risk_score', 'controversy_risk_score'
    ]
    
    velocity_cols = ['year_over_year_change', 'performance_trend']
    
    # Rename columns
    rename_map = {}
    for col in df.columns:
        if col in identity_cols:
            rename_map[col] = f'identity.{col}'
        elif col in brand_cols:
            rename_map[col] = f'brand.{col}'
        elif col in proof_cols:
            rename_map[col] = f'proof.{col}'
        elif col in risk_cols:
            rename_map[col] = f'risk.{col}'
        elif col in velocity_cols:
            rename_map[col] = f'velocity.{col}'
    
    df.rename(columns=rename_map, inplace=True)
    
    return df


def _process_player_data(df: pd.DataFrame) -> pd.DataFrame:
    """Process player data through the rule-based pipeline (ML lives in external repo)."""
    df = model_cache.rule_based_imputer.impute_data(df)
    df = model_cache.feature_extractor.extract_features(df)
    df = model_cache.gravity_calculator.calculate_scores(df)
    return df


def _extract_player_result(row: pd.Series, player_name: str) -> PlayerScoreOutput:
    """Extract scoring results from DataFrame row"""
    
    # Build ML predictions
    ml_predictions = {}
    
    if 'ml_draft_prediction' in row.index:
        ml_predictions['ml_draft_prediction'] = MLPrediction(
            value=float(row['ml_draft_prediction']),
            confidence=float(row.get('ml_draft_confidence', 0.5))
        )
    
    if 'ml_contract_prediction' in row.index:
        ml_predictions['ml_contract_prediction'] = MLPrediction(
            value=float(row['ml_contract_prediction']),
            confidence=float(row.get('ml_contract_confidence', 0.5))
        )
    
    if 'ml_performance_prediction' in row.index:
        ml_predictions['ml_performance_trend'] = MLPrediction(
            value=str(row['ml_performance_prediction']),
            confidence=float(row.get('ml_performance_confidence', 0.5))
        )
    
    if 'ml_injury_prediction' in row.index:
        ml_predictions['ml_injury_risk'] = MLPrediction(
            value=str(row['ml_injury_prediction']),
            confidence=float(row.get('ml_injury_confidence', 0.5))
        )
    
    return PlayerScoreOutput(
        player_name=player_name,
        gravity_score=float(row.get('gravity_score', 0)),
        ml_market_value=float(row.get('ml_market_prediction', 0)) if 'ml_market_prediction' in row.index else None,
        ensemble_score=float(row.get('ensemble_score', 0)) if 'ensemble_score' in row.index else None,
        brand_score=float(row.get('brand_score', 0)) if 'brand_score' in row.index else None,
        proof_score=float(row.get('proof_score', 0)) if 'proof_score' in row.index else None,
        proximity_score=float(row.get('proximity_score', 0)) if 'proximity_score' in row.index else None,
        velocity_score=float(row.get('velocity_score', 0)) if 'velocity_score' in row.index else None,
        risk_score=float(row.get('risk_score', 0)) if 'risk_score' in row.index else None,
        data_quality=float(row.get('data_quality_score', 0)) if 'data_quality_score' in row.index else None,
        **ml_predictions
    )


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            detail=str(exc)
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc)
        ).dict()
    )


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                      GRAVITY SCORE API                               ║
    ║                                                                      ║
    ║  🚀 Starting FastAPI server...                                       ║
    ║                                                                      ║
    ║  📚 Documentation: http://localhost:8000/docs                        ║
    ║  🏥 Health Check:  http://localhost:8000/health                      ║
    ║  📊 Models Status: http://localhost:8000/models/status               ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "api.gravity_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

