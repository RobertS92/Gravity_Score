#!/usr/bin/env python3
"""
ML Prediction Models
====================

Predictive models for various player outcomes:
- Draft position prediction
- Contract value prediction
- Performance trend prediction
- Injury risk prediction
- Market value prediction

Author: Gravity Score Team
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import pickle
from pathlib import Path
from datetime import datetime

try:
    import xgboost as xgb
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import (
        mean_absolute_error, mean_squared_error, 
        accuracy_score, f1_score, classification_report,
        mean_absolute_percentage_error
    )
    from sklearn.preprocessing import LabelEncoder
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================================================
# BASE PREDICTOR CLASS
# ============================================================================

class BasePredictor:
    """Base class for all prediction models"""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize predictor
        
        Args:
            model_path: Path to save/load trained model
        """
        self.model = None
        self.model_path = model_path
        self.feature_columns = []
        self.label_encoder = None
        self.performance_metrics = {}
        self.feature_importance = {}
        self.trained_date = None
    
    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs):
        """Train the model - implemented by subclasses"""
        raise NotImplementedError
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions"""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first or load() a trained model.")
        
        X_prepared = self._prepare_features(X)
        predictions = self.model.predict(X_prepared)
        
        # Decode if classifier
        if self.label_encoder is not None:
            predictions = self.label_encoder.inverse_transform(predictions.astype(int))
        
        return predictions
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get prediction probabilities (for classifiers only)"""
        if self.model is None or not hasattr(self.model, 'predict_proba'):
            raise ValueError("Model does not support probability predictions")
        
        X_prepared = self._prepare_features(X)
        return self.model.predict_proba(X_prepared)
    
    def _prepare_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for prediction"""
        X = X.copy()
        
        # Ensure all required features are present
        for col in self.feature_columns:
            if col not in X.columns:
                X[col] = 0  # Add missing features as 0
        
        # Select only trained features in correct order
        X = X[self.feature_columns]
        
        # Fill missing values
        X = X.fillna(X.median())
        
        return X
    
    def save(self, path: Optional[str] = None):
        """Save trained model to disk"""
        save_path = path or self.model_path
        
        if save_path is None:
            raise ValueError("No path specified for saving model")
        
        model_data = {
            'model': self.model,
            'feature_columns': self.feature_columns,
            'label_encoder': self.label_encoder,
            'performance_metrics': self.performance_metrics,
            'feature_importance': self.feature_importance,
            'trained_date': self.trained_date
        }
        
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(save_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"✅ Model saved to {save_path}")
    
    def load(self, path: Optional[str] = None):
        """Load trained model from disk"""
        load_path = path or self.model_path
        
        if load_path is None or not Path(load_path).exists():
            raise ValueError(f"Model file not found: {load_path}")
        
        with open(load_path, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.feature_columns = model_data['feature_columns']
        self.label_encoder = model_data.get('label_encoder')
        self.performance_metrics = model_data.get('performance_metrics', {})
        self.feature_importance = model_data.get('feature_importance', {})
        self.trained_date = model_data.get('trained_date')
        
        logger.info(f"✅ Model loaded from {load_path}")
    
    def get_feature_importance(self, top_n: int = 20) -> Dict[str, float]:
        """Get top N most important features"""
        if not self.feature_importance:
            return {}
        
        sorted_features = sorted(
            self.feature_importance.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        return dict(sorted_features[:top_n])


# ============================================================================
# DRAFT POSITION PREDICTOR
# ============================================================================

class DraftPositionPredictor(BasePredictor):
    """
    Predict NFL/NBA draft position for college players
    
    Features:
    - College performance stats
    - Awards and achievements
    - Recruiting ranking
    - Physical measurements
    - Class year
    """
    
    def __init__(self, model_path: str = "models/prediction/draft_predictor.pkl"):
        super().__init__(model_path)
    
    def train(self, df: pd.DataFrame, target: str = 'identity.draft_round', **kwargs):
        """
        Train draft position predictor
        
        Args:
            df: Training data with college players who were drafted
            target: Target variable ('identity.draft_round' or 'identity.draft_pick')
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("sklearn and xgboost required. Install with: pip install xgboost scikit-learn")
        
        # Filter to players who were drafted
        train_df = df[df[target].notna()].copy()
        
        # Remove "Undrafted" entries
        if train_df[target].dtype == 'object':
            train_df = train_df[train_df[target] != 'Undrafted']
            train_df[target] = pd.to_numeric(train_df[target], errors='coerce')
            train_df = train_df[train_df[target].notna()]
        
        if len(train_df) < 50:
            raise ValueError(f"Insufficient training data: {len(train_df)} samples")
        
        logger.info(f"Training draft predictor on {len(train_df)} drafted players")
        
        # Select features
        feature_candidates = [
            # Recruiting data
            'identity.recruiting_stars',
            'identity.recruiting_ranking',
            'identity.recruiting_state_ranking',
            'identity.recruiting_position_ranking',
            
            # Physical
            'identity.height',
            'identity.weight',
            'identity.age',
            
            # College stats
            'proof.career_points',
            'proof.career_yards',
            'proof.career_touchdowns',
            'proof.career_receptions',
            'proof.career_rebounds',
            'proof.career_assists',
            
            # Performance metrics
            'proof.points_per_game',
            'proof.yards_per_game',
            'proof.field_goal_pct',
            
            # Awards
            'proof.all_american_selections',
            'proof.conference_championships',
            'proof.awards_count',
            
            # Class/Eligibility
            'identity.class_year',
            'identity.eligibility_year',
            
            # Social proof (indicator of hype)
            'brand.instagram_followers',
            'brand.twitter_followers',
            'brand.nil_valuation'
        ]
        
        self.feature_columns = [f for f in feature_candidates if f in train_df.columns]
        
        if not self.feature_columns:
            raise ValueError("No valid features found for training")
        
        # Prepare data
        X = train_df[self.feature_columns].fillna(0)
        y = train_df[target]
        
        # Split
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Train XGBoost Regressor (draft round/pick as continuous)
        self.model = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric='mae'
        )
        
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        
        # Evaluate
        y_pred = self.model.predict(X_val)
        
        self.performance_metrics = {
            'mae': mean_absolute_error(y_val, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_val, y_pred)),
            'samples': len(train_df),
            'target': target
        }
        
        # Feature importance
        self.feature_importance = dict(zip(self.feature_columns, self.model.feature_importances_))
        self.trained_date = datetime.now().isoformat()
        
        # Log within-1-round accuracy for draft_round
        if 'round' in target:
            within_1 = np.abs(y_pred - y_val) <= 1
            within_1_acc = within_1.sum() / len(y_val)
            self.performance_metrics['within_1_round_accuracy'] = within_1_acc
            logger.info(f"  Within 1 round accuracy: {within_1_acc:.2%}")
        
        logger.info(f"✅ Draft predictor trained: MAE={self.performance_metrics['mae']:.2f}")
        
        return self.performance_metrics


# ============================================================================
# CONTRACT VALUE PREDICTOR
# ============================================================================

class ContractValuePredictor(BasePredictor):
    """
    Predict contract value (APY) for professional players
    
    Features:
    - Performance stats
    - Awards and achievements
    - Social media following
    - Age and experience
    - Position
    """
    
    def __init__(self, model_path: str = "models/prediction/contract_predictor.pkl"):
        super().__init__(model_path)
    
    def train(self, df: pd.DataFrame, target: str = 'identity.contract_value', **kwargs):
        """Train contract value predictor"""
        
        if not SKLEARN_AVAILABLE:
            raise ImportError("sklearn and xgboost required")
        
        # Filter to players with contract data
        train_df = df[df[target].notna()].copy()
        train_df = train_df[train_df[target] > 0]  # Remove $0 contracts
        
        if len(train_df) < 50:
            raise ValueError(f"Insufficient training data: {len(train_df)} samples")
        
        logger.info(f"Training contract predictor on {len(train_df)} players")
        
        # Select features
        feature_candidates = [
            # Performance
            'proof.career_points',
            'proof.career_yards',
            'proof.career_touchdowns',
            'proof.career_receptions',
            'proof.career_sacks',
            'proof.career_interceptions',
            
            # Recent performance
            'proof.current_season_points',
            'proof.current_season_yards',
            'proof.points_per_game',
            'proof.yards_per_game',
            
            # Awards
            'proof.pro_bowls',
            'proof.all_pro_selections',
            'proof.super_bowl_wins',
            'proof.all_star_selections',
            'proof.championships',
            'proof.awards_count',
            
            # Experience
            'identity.age',
            'identity.years_in_league',
            'identity.draft_round',
            
            # Physical
            'identity.height',
            'identity.weight',
            
            # Brand
            'brand.instagram_followers',
            'brand.twitter_followers',
            'brand.youtube_subscribers',
            'brand.endorsement_count',
            'brand.media_mentions'
        ]
        
        self.feature_columns = [f for f in feature_candidates if f in train_df.columns]
        
        # Prepare data
        X = train_df[self.feature_columns].fillna(0)
        y = train_df[target]
        
        # Log transform target (contract values are highly skewed)
        y_log = np.log1p(y)
        
        # Split
        X_train, X_val, y_train, y_val = train_test_split(X, y_log, test_size=0.2, random_state=42)
        y_val_original = train_df.loc[y_val.index, target]  # Original scale for metrics
        
        # Train XGBoost
        self.model = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric='mae'
        )
        
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        
        # Evaluate
        y_pred_log = self.model.predict(X_val)
        y_pred = np.expm1(y_pred_log)  # Convert back to original scale
        
        self.performance_metrics = {
            'mae': mean_absolute_error(y_val_original, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_val_original, y_pred)),
            'mape': mean_absolute_percentage_error(y_val_original, y_pred) * 100,
            'samples': len(train_df),
            'target': target
        }
        
        # Feature importance
        self.feature_importance = dict(zip(self.feature_columns, self.model.feature_importances_))
        self.trained_date = datetime.now().isoformat()
        
        logger.info(f"✅ Contract predictor trained: MAPE={self.performance_metrics['mape']:.1f}%")
        
        return self.performance_metrics
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Override to handle log transform"""
        X_prepared = self._prepare_features(X)
        y_pred_log = self.model.predict(X_prepared)
        return np.expm1(y_pred_log)  # Convert back to original scale


# ============================================================================
# PERFORMANCE TREND PREDICTOR
# ============================================================================

class PerformanceTrendPredictor(BasePredictor):
    """
    Predict performance trend (improving/stable/declining)
    
    Features:
    - Year-over-year stat changes
    - Age and career stage
    - Injury history
    - Recent performance indicators
    """
    
    def __init__(self, model_path: str = "models/prediction/performance_predictor.pkl"):
        super().__init__(model_path)
    
    def train(self, df: pd.DataFrame, **kwargs):
        """Train performance trend classifier"""
        
        if not SKLEARN_AVAILABLE:
            raise ImportError("sklearn and xgboost required")
        
        # Create performance trend labels from velocity data
        df = df.copy()
        
        # Define trend based on velocity.performance_trend
        if 'velocity.performance_trend' in df.columns:
            target_col = 'velocity.performance_trend'
        else:
            # Create trend from YoY change
            logger.info("Creating performance trend labels from velocity data...")
            df = self._create_trend_labels(df)
            target_col = 'performance_trend_label'
        
        train_df = df[df[target_col].notna()].copy()
        
        if len(train_df) < 50:
            raise ValueError(f"Insufficient training data: {len(train_df)} samples")
        
        logger.info(f"Training performance trend predictor on {len(train_df)} players")
        
        # Select features
        feature_candidates = [
            # Current performance
            'proof.current_season_points',
            'proof.current_season_yards',
            'proof.points_per_game',
            'proof.yards_per_game',
            
            # Career stats (for context)
            'proof.career_points',
            'proof.career_yards',
            
            # Age/Experience
            'identity.age',
            'identity.years_in_league',
            
            # Injury
            'risk.games_missed_last_season',
            'risk.games_missed_career',
            'risk.injury_risk_score',
            
            # Velocity indicators
            'velocity.year_over_year_change',
            'velocity.momentum_score',
            
            # Physical
            'identity.height',
            'identity.weight'
        ]
        
        self.feature_columns = [f for f in feature_candidates if f in train_df.columns]
        
        # Prepare data
        X = train_df[self.feature_columns].fillna(0)
        y = train_df[target_col]
        
        # Encode labels
        self.label_encoder = LabelEncoder()
        y_encoded = self.label_encoder.fit_transform(y.astype(str))
        
        # Split
        X_train, X_val, y_train, y_val = train_test_split(
            X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
        )
        
        # Train XGBoost Classifier
        self.model = xgb.XGBClassifier(
            n_estimators=150,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric='mlogloss'
        )
        
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        
        # Evaluate
        y_pred = self.model.predict(X_val)
        
        self.performance_metrics = {
            'accuracy': accuracy_score(y_val, y_pred),
            'f1_score': f1_score(y_val, y_pred, average='weighted'),
            'samples': len(train_df),
            'classes': list(self.label_encoder.classes_)
        }
        
        # Feature importance
        self.feature_importance = dict(zip(self.feature_columns, self.model.feature_importances_))
        self.trained_date = datetime.now().isoformat()
        
        logger.info(f"✅ Performance trend predictor trained: Accuracy={self.performance_metrics['accuracy']:.2%}")
        
        return self.performance_metrics
    
    def _create_trend_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create trend labels from available data"""
        
        # Simple heuristic based on velocity or year-over-year change
        conditions = []
        labels = []
        
        if 'velocity.year_over_year_change' in df.columns:
            yoy = df['velocity.year_over_year_change'].fillna(0)
            conditions = [
                yoy > 10,
                (yoy >= -5) & (yoy <= 10),
                yoy < -5
            ]
            labels = ['improving', 'stable', 'declining']
        
        if conditions:
            df['performance_trend_label'] = np.select(conditions, labels, default='stable')
        else:
            df['performance_trend_label'] = 'stable'
        
        return df


# ============================================================================
# INJURY RISK PREDICTOR
# ============================================================================

class InjuryRiskPredictor(BasePredictor):
    """
    Predict injury risk category (low/medium/high)
    
    Features:
    - Injury history
    - Age and wear
    - Position
    - Playing style indicators
    - Games played trends
    """
    
    def __init__(self, model_path: str = "models/prediction/injury_predictor.pkl"):
        super().__init__(model_path)
    
    def train(self, df: pd.DataFrame, target: str = 'risk.injury_risk_score', **kwargs):
        """Train injury risk classifier"""
        
        if not SKLEARN_AVAILABLE:
            raise ImportError("sklearn and xgboost required")
        
        # Convert injury risk score to categories
        df = df.copy()
        
        if target in df.columns and df[target].notna().sum() > 0:
            # Categorize risk score
            df['injury_risk_category'] = pd.cut(
                df[target],
                bins=[0, 30, 60, 100],
                labels=['low', 'medium', 'high']
            )
            target_col = 'injury_risk_category'
        else:
            # Create categories from injury history
            logger.info("Creating injury risk categories from injury history...")
            df = self._create_risk_categories(df)
            target_col = 'injury_risk_category'
        
        train_df = df[df[target_col].notna()].copy()
        
        if len(train_df) < 50:
            raise ValueError(f"Insufficient training data: {len(train_df)} samples")
        
        logger.info(f"Training injury risk predictor on {len(train_df)} players")
        
        # Select features
        feature_candidates = [
            # Injury history
            'risk.games_missed_career',
            'risk.games_missed_last_season',
            'risk.injury_history_count',
            
            # Age/Wear
            'identity.age',
            'identity.years_in_league',
            
            # Physical
            'identity.height',
            'identity.weight',
            
            # Playing style (contact indicators)
            'proof.career_sacks',
            'proof.career_tackles',
            'proof.career_rushing_attempts',
            
            # Usage/Load
            'proof.games_played',
            'proof.minutes_per_game',
            'proof.touches_per_game'
        ]
        
        self.feature_columns = [f for f in feature_candidates if f in train_df.columns]
        
        # Prepare data
        X = train_df[self.feature_columns].fillna(0)
        y = train_df[target_col]
        
        # Encode labels
        self.label_encoder = LabelEncoder()
        y_encoded = self.label_encoder.fit_transform(y.astype(str))
        
        # Split
        X_train, X_val, y_train, y_val = train_test_split(
            X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
        )
        
        # Train XGBoost Classifier
        self.model = xgb.XGBClassifier(
            n_estimators=150,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric='mlogloss'
        )
        
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        
        # Evaluate
        y_pred = self.model.predict(X_val)
        
        self.performance_metrics = {
            'accuracy': accuracy_score(y_val, y_pred),
            'f1_score': f1_score(y_val, y_pred, average='weighted'),
            'samples': len(train_df),
            'classes': list(self.label_encoder.classes_)
        }
        
        # Feature importance
        self.feature_importance = dict(zip(self.feature_columns, self.model.feature_importances_))
        self.trained_date = datetime.now().isoformat()
        
        logger.info(f"✅ Injury risk predictor trained: Accuracy={self.performance_metrics['accuracy']:.2%}")
        
        return self.performance_metrics
    
    def _create_risk_categories(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create risk categories from available data"""
        
        conditions = []
        labels = []
        
        if 'risk.games_missed_career' in df.columns:
            games_missed = df['risk.games_missed_career'].fillna(0)
            conditions = [
                games_missed < 5,
                (games_missed >= 5) & (games_missed < 15),
                games_missed >= 15
            ]
            labels = ['low', 'medium', 'high']
        
        if conditions:
            df['injury_risk_category'] = np.select(conditions, labels, default='low')
        else:
            df['injury_risk_category'] = 'low'
        
        return df


# ============================================================================
# MARKET VALUE PREDICTOR
# ============================================================================

class MarketValuePredictor(BasePredictor):
    """
    Predict overall market value score (combining all factors)
    
    Features:
    - All brand metrics
    - All proof metrics
    - All velocity indicators
    - Risk factors
    """
    
    def __init__(self, model_path: str = "models/prediction/market_value_predictor.pkl"):
        super().__init__(model_path)
    
    def train(self, df: pd.DataFrame, target: str = 'gravity_score', **kwargs):
        """Train market value predictor"""
        
        if not SKLEARN_AVAILABLE:
            raise ImportError("sklearn and xgboost required")
        
        # Use existing gravity_score as target
        train_df = df[df[target].notna()].copy()
        train_df = train_df[train_df[target] > 0]
        
        if len(train_df) < 50:
            raise ValueError(f"Insufficient training data: {len(train_df)} samples")
        
        logger.info(f"Training market value predictor on {len(train_df)} players")
        
        # Select comprehensive features
        feature_candidates = [
            # Brand
            'brand.instagram_followers',
            'brand.twitter_followers',
            'brand.tiktok_followers',
            'brand.youtube_subscribers',
            'brand.endorsement_count',
            'brand.media_mentions',
            'brand.total_social_followers',
            
            # Proof
            'proof.career_points',
            'proof.career_yards',
            'proof.career_touchdowns',
            'proof.pro_bowls',
            'proof.all_pro_selections',
            'proof.all_star_selections',
            'proof.championships',
            'proof.awards_count',
            
            # Velocity
            'velocity.year_over_year_change',
            'velocity.momentum_score',
            'velocity.performance_level',
            'velocity.career_trajectory',
            
            # Risk
            'risk.injury_risk_score',
            'risk.controversy_risk_score',
            'risk.reputation_score',
            'risk.games_missed_career',
            
            # Identity
            'identity.age',
            'identity.years_in_league',
            'identity.contract_value',
            'identity.draft_round'
        ]
        
        self.feature_columns = [f for f in feature_candidates if f in train_df.columns]
        
        # Prepare data
        X = train_df[self.feature_columns].fillna(0)
        y = train_df[target]
        
        # Split
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Train XGBoost
        self.model = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric='mae'
        )
        
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        
        # Evaluate
        y_pred = self.model.predict(X_val)
        
        self.performance_metrics = {
            'mae': mean_absolute_error(y_val, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_val, y_pred)),
            'mape': mean_absolute_percentage_error(y_val, y_pred) * 100,
            'samples': len(train_df),
            'target': target
        }
        
        # Feature importance
        self.feature_importance = dict(zip(self.feature_columns, self.model.feature_importances_))
        self.trained_date = datetime.now().isoformat()
        
        logger.info(f"✅ Market value predictor trained: MAE={self.performance_metrics['mae']:.2f}")
        
        return self.performance_metrics


# ============================================================================
# MODEL FACTORY
# ============================================================================

class ModelFactory:
    """Factory for creating and managing prediction models"""
    
    @staticmethod
    def create_model(model_type: str, model_path: Optional[str] = None) -> BasePredictor:
        """
        Create a prediction model
        
        Args:
            model_type: Type of model ('draft', 'contract', 'performance', 'injury', 'market')
            model_path: Optional custom path for model file
            
        Returns:
            Predictor instance
        """
        models = {
            'draft': DraftPositionPredictor,
            'contract': ContractValuePredictor,
            'performance': PerformanceTrendPredictor,
            'injury': InjuryRiskPredictor,
            'market': MarketValuePredictor
        }
        
        if model_type not in models:
            raise ValueError(f"Unknown model type: {model_type}. Choose from {list(models.keys())}")
        
        model_class = models[model_type]
        
        if model_path:
            return model_class(model_path)
        else:
            return model_class()
    
    @staticmethod
    def load_all_models(models_dir: str = "models/prediction") -> Dict[str, BasePredictor]:
        """Load all available trained models"""
        models = {}
        models_path = Path(models_dir)
        
        if not models_path.exists():
            logger.warning(f"Models directory {models_dir} not found")
            return models
        
        model_types = {
            'draft_predictor.pkl': 'draft',
            'contract_predictor.pkl': 'contract',
            'performance_predictor.pkl': 'performance',
            'injury_predictor.pkl': 'injury',
            'market_value_predictor.pkl': 'market'
        }
        
        for filename, model_type in model_types.items():
            model_file = models_path / filename
            if model_file.exists():
                try:
                    model = ModelFactory.create_model(model_type, str(model_file))
                    model.load()
                    models[model_type] = model
                    logger.info(f"✅ Loaded {model_type} model")
                except Exception as e:
                    logger.error(f"Failed to load {model_type} model: {e}")
        
        return models


if __name__ == '__main__':
    print("""
ML Prediction Models
====================

Available models:
- DraftPositionPredictor: Predict draft round/pick for college players
- ContractValuePredictor: Predict contract APY for professional players
- PerformanceTrendPredictor: Predict performance trend (improving/stable/declining)
- InjuryRiskPredictor: Predict injury risk category (low/medium/high)
- MarketValuePredictor: Predict overall market value score

Example usage:
    from gravity.ml_models import DraftPositionPredictor
    
    # Train
    predictor = DraftPositionPredictor()
    predictor.train(training_df)
    predictor.save()
    
    # Predict
    predictor.load()
    predictions = predictor.predict(new_players_df)
    """)

