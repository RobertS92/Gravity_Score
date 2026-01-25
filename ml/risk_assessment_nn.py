"""
Risk Assessment Neural Network
===============================
Multi-Task: Injury Risk + Controversy Risk + Overall Risk
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pandas as pd

class RiskAssessmentNN(nn.Module):
    """
    Multi-task neural network for risk assessment
    Predicts injury risk, controversy risk, and overall risk simultaneously
    """
    
    def __init__(self, input_dim: int = 30, hidden_dim: int = 128):
        super().__init__()
        
        # Shared encoder
        self.shared_encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2)
        )
        
        # Task-specific heads
        self.injury_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid()  # Risk probability 0-1
        )
        
        self.controversy_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid()  # Risk probability 0-1
        )
        
        self.overall_risk_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid()  # Overall risk 0-1
        )
    
    def forward(self, x):
        # Shared encoding
        encoded = self.shared_encoder(x)
        
        # Task-specific predictions
        injury_risk = self.injury_head(encoded).squeeze(-1)
        controversy_risk = self.controversy_head(encoded).squeeze(-1)
        overall_risk = self.overall_risk_head(encoded).squeeze(-1)
        
        return {
            'injury_risk': injury_risk,
            'controversy_risk': controversy_risk,
            'overall_risk': overall_risk
        }


def prepare_risk_features(df: pd.DataFrame) -> np.ndarray:
    """Prepare features for risk assessment"""
    
    features = []
    
    # Injury history
    injury_cols = ['games_missed_career', 'games_missed_last_season', 'injury_history']
    for col in injury_cols:
        if col in df.columns:
            features.append(df[col].fillna(0).values)
    
    # Controversy history
    controversy_cols = ['controversies', 'suspensions', 'fines', 'arrests']
    for col in controversy_cols:
        if col in df.columns:
            features.append(df[col].fillna(0).values)
    
    # Age (risk factor)
    if 'age' in df.columns:
        features.append(df['age'].fillna(25).values)
    
    # Position (some positions more injury-prone)
    if 'position' in df.columns:
        # One-hot encode position
        positions = df['position'].fillna('Unknown')
        position_dummies = pd.get_dummies(positions, prefix='pos')
        for col in position_dummies.columns:
            features.append(position_dummies[col].values)
    
    if features:
        feature_matrix = np.column_stack(features)
    else:
        # Fallback
        numeric_cols = df.select_dtypes(include=[np.number]).columns[:30]
        feature_matrix = df[numeric_cols].fillna(0).values
    
    return feature_matrix

