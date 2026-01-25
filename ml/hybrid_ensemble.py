"""
Hybrid Ensemble System
======================
Combines NN predictions with rule-based scoring using adaptive weighting
"""

import torch
import torch.nn as nn
import numpy as np
import pandas as pd
from typing import Dict, Optional
import logging

from ml.performance_nn import PerformanceScoringNN, prepare_performance_features
from ml.market_value_nn import MarketValueNN, prepare_market_features
from ml.social_media_nn import SocialMediaNN, prepare_social_features
from ml.velocity_nn import VelocityNN, prepare_velocity_features
from ml.risk_assessment_nn import RiskAssessmentNN, prepare_risk_features

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdaptiveWeightPredictor(nn.Module):
    """
    Predicts optimal weights for NN vs rule-based scoring
    Based on data quality/completeness
    """
    
    def __init__(self, input_dim: int = 10, hidden_dim: int = 32):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid()  # Output: weight for NN (0-1), rule-based gets (1-weight)
        )
    
    def forward(self, data_quality_features):
        nn_weight = self.network(data_quality_features)
        return nn_weight.squeeze(-1), 1 - nn_weight.squeeze(-1)


class HybridEnsemble:
    """
    Hybrid ensemble combining neural network predictions with rule-based scoring
    """
    
    def __init__(self, sport: str = 'nfl', device: str = 'cpu'):
        self.sport = sport
        self.device = device
        
        # Initialize neural networks
        self.performance_nn = PerformanceScoringNN().to(device)
        self.market_nn = MarketValueNN().to(device)
        self.social_nn = SocialMediaNN().to(device)
        self.velocity_nn = VelocityNN().to(device)
        self.risk_nn = RiskAssessmentNN().to(device)
        
        # Adaptive weight predictor
        self.weight_predictor = AdaptiveWeightPredictor().to(device)
        
        # Fusion layer
        self.fusion = nn.Sequential(
            nn.Linear(5, 64),  # 5 component scores
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1)  # Final gravity score
        ).to(device)
        
        # Set to eval mode
        self.performance_nn.eval()
        self.market_nn.eval()
        self.social_nn.eval()
        self.velocity_nn.eval()
        self.risk_nn.eval()
        self.weight_predictor.eval()
        self.fusion.eval()
    
    def load_models(self, model_dir: str = 'models/'):
        """Load trained model weights"""
        try:
            self.performance_nn.load_state_dict(
                torch.load(f'{model_dir}/performance_nn_{self.sport}.pth', map_location=self.device)
            )
            self.market_nn.load_state_dict(
                torch.load(f'{model_dir}/market_nn_{self.sport}.pth', map_location=self.device)
            )
            self.social_nn.load_state_dict(
                torch.load(f'{model_dir}/social_nn_{self.sport}.pth', map_location=self.device)
            )
            self.velocity_nn.load_state_dict(
                torch.load(f'{model_dir}/velocity_nn_{self.sport}.pth', map_location=self.device)
            )
            self.risk_nn.load_state_dict(
                torch.load(f'{model_dir}/risk_nn_{self.sport}.pth', map_location=self.device)
            )
            logger.info(f"✅ Loaded trained models for {self.sport.upper()}")
        except FileNotFoundError:
            logger.warning(f"⚠️  Model files not found. Using untrained models.")
    
    def calculate_data_quality(self, df: pd.DataFrame) -> np.ndarray:
        """Calculate data quality score for each player (0-1)"""
        quality_scores = []
        
        for _, row in df.iterrows():
            completeness = 0
            total_fields = 0
            
            # Check key fields
            key_fields = {
                'performance': ['career_touchdowns', 'career_yards', 'pro_bowls'],
                'market': ['contract_value', 'endorsement_value'],
                'social': ['instagram_followers', 'twitter_followers'],
                'velocity': ['age', 'years_in_league'],
                'risk': ['games_missed_career', 'controversies']
            }
            
            for category, fields in key_fields.items():
                for field in fields:
                    total_fields += 1
                    if field in row and pd.notna(row[field]) and row[field] != 0:
                        completeness += 1
            
            quality = completeness / total_fields if total_fields > 0 else 0.5
            quality_scores.append(quality)
        
        return np.array(quality_scores)
    
    def predict(self, df: pd.DataFrame, use_rule_based: bool = True) -> pd.DataFrame:
        """
        Predict gravity scores using hybrid ensemble
        
        Args:
            df: DataFrame with player data
            use_rule_based: Whether to use rule-based fallback
            
        Returns:
            DataFrame with predictions added
        """
        logger.info(f"🔮 Predicting gravity scores for {len(df)} {self.sport.upper()} players...")
        
        # Prepare features
        perf_features = prepare_performance_features(df, self.sport)
        market_features_dict = prepare_market_features(df)
        social_features_dict = prepare_social_features(df)
        velocity_features = prepare_velocity_features(df, self.sport)
        risk_features = prepare_risk_features(df)
        
        # Calculate data quality
        data_quality = self.calculate_data_quality(df)
        quality_features = data_quality.reshape(-1, 1)
        
        # Get adaptive weights
        with torch.no_grad():
            quality_tensor = torch.FloatTensor(quality_features).to(self.device)
            nn_weights, rule_weights = self.weight_predictor(quality_tensor)
            nn_weights = nn_weights.cpu().numpy()
            rule_weights = rule_weights.cpu().numpy()
        
        # NN predictions
        nn_scores = {}
        try:
            with torch.no_grad():
                # Performance
                perf_tensor = torch.FloatTensor(perf_features).to(self.device)
                if len(perf_tensor.shape) == 2:
                    perf_tensor = perf_tensor.unsqueeze(1)  # Add sequence dimension
                nn_scores['performance'] = self.performance_nn(perf_tensor).cpu().numpy()
                
                # Market
                market_tensors = {k: torch.FloatTensor(v).to(self.device) 
                                 for k, v in market_features_dict.items()}
                market_pred, _ = self.market_nn(
                    market_tensors['contract'],
                    market_tensors['endorsement'],
                    market_tensors['social']
                )
                nn_scores['market'] = market_pred.cpu().numpy()
                
                # Social
                social_tensors = {k: torch.FloatTensor(v).to(self.device) 
                                for k, v in social_features_dict.items()}
                nn_scores['social'] = self.social_nn(
                    social_tensors['time_series'],
                    social_tensors['sentiment'].long(),
                    social_tensors['follower']
                ).cpu().numpy()
                
                # Velocity
                vel_tensor = torch.FloatTensor(velocity_features).to(self.device)
                nn_scores['velocity'] = self.velocity_nn(vel_tensor).cpu().numpy()
                
                # Risk
                risk_tensor = torch.FloatTensor(risk_features).to(self.device)
                risk_preds = self.risk_nn(risk_tensor)
                nn_scores['risk'] = risk_preds['overall_risk'].cpu().numpy()
        except Exception as e:
            logger.warning(f"⚠️  NN prediction failed: {e}. Using rule-based only.")
            nn_scores = {k: np.zeros(len(df)) for k in ['performance', 'market', 'social', 'velocity', 'risk']}
            nn_weights = np.zeros(len(df))
            rule_weights = np.ones(len(df))
        
        # Rule-based scores (from existing pipeline)
        if use_rule_based:
            from gravity.data_pipeline import GravityScoreCalculator
            calculator = GravityScoreCalculator()
            rule_scores_df = calculator.calculate_gravity_scores(df)
            
            rule_scores = {
                'performance': rule_scores_df['gravity.performance_score'].values / 100.0,
                'market': rule_scores_df['gravity.market_score'].values / 100.0,
                'social': rule_scores_df['gravity.social_score'].values / 100.0,
                'velocity': rule_scores_df['gravity.velocity_score'].values / 100.0,
                'risk': rule_scores_df['gravity.risk_score'].values / 100.0
            }
        else:
            rule_scores = {k: np.zeros(len(df)) for k in nn_scores.keys()}
        
        # Combine with adaptive weights
        hybrid_scores = {}
        for component in ['performance', 'market', 'social', 'velocity', 'risk']:
            nn_score = nn_scores[component]
            rule_score = rule_scores[component]
            
            # Weighted combination
            hybrid = (nn_score * nn_weights) + (rule_score * rule_weights)
            hybrid_scores[component] = hybrid
        
        # Final fusion
        with torch.no_grad():
            component_tensor = torch.FloatTensor(
                np.column_stack([hybrid_scores[k] for k in ['performance', 'market', 'social', 'velocity', 'risk']])
            ).to(self.device)
            final_scores = self.fusion(component_tensor).cpu().numpy().squeeze()
        
        # Add to dataframe
        df_result = df.copy()
        df_result['hybrid_gravity_score'] = final_scores * 100  # Scale to 0-100
        df_result['hybrid_performance'] = hybrid_scores['performance'] * 100
        df_result['hybrid_market'] = hybrid_scores['market'] * 100
        df_result['hybrid_social'] = hybrid_scores['social'] * 100
        df_result['hybrid_velocity'] = hybrid_scores['velocity'] * 100
        df_result['hybrid_risk'] = hybrid_scores['risk'] * 100
        df_result['nn_weight'] = nn_weights
        df_result['rule_weight'] = rule_weights
        
        logger.info(f"✅ Hybrid predictions complete")
        logger.info(f"   Score range: {final_scores.min()*100:.1f} - {final_scores.max()*100:.1f}")
        logger.info(f"   Average NN weight: {nn_weights.mean():.2f}")
        logger.info(f"   Average rule weight: {rule_weights.mean():.2f}")
        
        return df_result

