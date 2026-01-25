#!/usr/bin/env python3
"""
Model Cache
===========

Efficient model loading and caching for FastAPI.

Author: Gravity Score Team
"""

import logging
from pathlib import Path
from typing import Dict, Optional
import json

from gravity.ml_imputer import MLImputer
from gravity.ml_models import ModelFactory
from gravity.ml_feature_engineering import MLFeatureEngineer
from gravity.data_pipeline import DataFlattener, DataImputer, FeatureExtractor, GravityScoreCalculator

logger = logging.getLogger(__name__)


# ============================================================================
# MODEL CACHE
# ============================================================================

class ModelCache:
    """
    Singleton cache for ML models
    
    Loads models once on startup and keeps them in memory
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, models_dir: str = "models"):
        """
        Initialize model cache
        
        Args:
            models_dir: Directory containing trained models
        """
        if self._initialized:
            return
        
        self.models_dir = Path(models_dir)
        
        # ML Components
        self.ml_imputer: Optional[MLImputer] = None
        self.ml_feature_engineer: Optional[MLFeatureEngineer] = None
        self.prediction_models: Dict = {}
        
        # Pipeline Components
        self.flattener = DataFlattener()
        self.rule_based_imputer = DataImputer()
        self.feature_extractor = FeatureExtractor()
        self.gravity_calculator = GravityScoreCalculator()
        
        # Model registry
        self.registry: Optional[Dict] = None
        
        # Status
        self.models_loaded = False
        
        self._initialized = True
    
    def load_models(self) -> bool:
        """
        Load all trained models
        
        Returns:
            True if models loaded successfully
        """
        logger.info("Loading ML models...")
        
        try:
            # Load imputation models
            imputation_dir = self.models_dir / "imputation"
            if imputation_dir.exists():
                self.ml_imputer = MLImputer(models_dir=str(imputation_dir))
                self.ml_imputer.load_models()
                logger.info(f"✅ Loaded {len(self.ml_imputer.trained_models)} imputation models")
            else:
                logger.warning(f"⚠️  Imputation models not found at {imputation_dir}")
            
            # Load prediction models
            prediction_dir = self.models_dir / "prediction"
            if prediction_dir.exists():
                self.prediction_models = ModelFactory.load_all_models(str(prediction_dir))
                logger.info(f"✅ Loaded {len(self.prediction_models)} prediction models")
            else:
                logger.warning(f"⚠️  Prediction models not found at {prediction_dir}")
            
            # Initialize feature engineer
            self.ml_feature_engineer = MLFeatureEngineer()
            
            # Load registry
            self._load_registry()
            
            self.models_loaded = True
            logger.info("✅ Model cache initialized")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load models: {e}")
            self.models_loaded = False
            return False
    
    def _load_registry(self):
        """Load model registry"""
        registry_path = self.models_dir / "registry.json"
        
        if registry_path.exists():
            try:
                with open(registry_path, 'r') as f:
                    self.registry = json.load(f)
                logger.info("✅ Loaded model registry")
            except Exception as e:
                logger.warning(f"⚠️  Failed to load registry: {e}")
                self.registry = None
        else:
            logger.warning(f"⚠️  Model registry not found at {registry_path}")
            self.registry = None
    
    def get_model(self, model_type: str):
        """Get a specific prediction model"""
        return self.prediction_models.get(model_type)
    
    def get_status(self) -> Dict:
        """Get cache status"""
        return {
            'models_loaded': self.models_loaded,
            'imputation_models': len(self.ml_imputer.trained_models) if self.ml_imputer else 0,
            'prediction_models': len(self.prediction_models),
            'registry_loaded': self.registry is not None
        }


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

# Global cache instance
model_cache = ModelCache()

