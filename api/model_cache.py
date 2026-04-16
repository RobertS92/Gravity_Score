#!/usr/bin/env python3
"""
Model cache — rule-based pipeline only.

ML training, imputation models, and scrapers live in separate repositories.
This cache holds DataImputer / FeatureExtractor / GravityScoreCalculator only.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from gravity.data_pipeline import (
    DataFlattener,
    DataImputer,
    FeatureExtractor,
    GravityScoreCalculator,
)

logger = logging.getLogger(__name__)


class ModelCache:
    """Singleton cache for the scoring pipeline (no bundled ML models)."""

    _instance = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "ModelCache":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, models_dir: str = "models") -> None:
        if getattr(self, "_initialized", False):
            return

        self.models_dir = Path(models_dir)
        self.flattener = DataFlattener()
        self.rule_based_imputer = DataImputer()
        self.feature_extractor = FeatureExtractor()
        self.gravity_calculator = GravityScoreCalculator()
        self.registry: Optional[Dict[str, Any]] = None
        self.models_loaded = False
        self._initialized = True

    def load_models(self) -> bool:
        logger.info("Initializing pipeline (ML models are external to this repo)")
        try:
            registry_path = self.models_dir / "registry.json"
            if registry_path.exists():
                with open(registry_path, encoding="utf-8") as f:
                    self.registry = json.load(f)
                logger.info("Loaded model registry metadata (optional)")
            else:
                self.registry = None
            self.models_loaded = True
            return True
        except Exception as e:
            logger.error("Failed to initialize cache: %s", e)
            self.models_loaded = False
            return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "models_loaded": self.models_loaded,
            "imputation_models": 0,
            "prediction_models": 0,
            "registry_loaded": self.registry is not None,
            "note": "Train and serve ML in the dedicated models repository.",
        }


model_cache = ModelCache()
