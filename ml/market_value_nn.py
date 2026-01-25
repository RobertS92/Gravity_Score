"""
Market Value Neural Network
===========================
Ensemble of specialized sub-networks for contract, endorsement, and social-to-market conversion
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pandas as pd

class ContractBranch(nn.Module):
    """Predicts contract value from performance and position"""
    
    def __init__(self, input_dim: int = 30, hidden_dim: int = 64):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1)  # Contract value prediction
        )
    
    def forward(self, x):
        return self.network(x).squeeze(-1)


class EndorsementBranch(nn.Module):
    """Predicts endorsement value from social reach and performance"""
    
    def __init__(self, input_dim: int = 20, hidden_dim: int = 64):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1)  # Endorsement value prediction
        )
    
    def forward(self, x):
        return self.network(x).squeeze(-1)


class SocialToMarketBranch(nn.Module):
    """Converts social media metrics to market value potential"""
    
    def __init__(self, input_dim: int = 10, hidden_dim: int = 32):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)  # Market potential score
        )
    
    def forward(self, x):
        return self.network(x).squeeze(-1)


class MarketValueNN(nn.Module):
    """
    Ensemble neural network for market value prediction
    Combines contract, endorsement, and social-to-market branches
    """
    
    def __init__(self, contract_input_dim: int = 30, endorsement_input_dim: int = 20,
                 social_input_dim: int = 10, hidden_dim: int = 64):
        super().__init__()
        
        # Specialized branches
        self.contract_branch = ContractBranch(contract_input_dim, hidden_dim)
        self.endorsement_branch = EndorsementBranch(endorsement_input_dim, hidden_dim)
        self.social_branch = SocialToMarketBranch(social_input_dim, hidden_dim // 2)
        
        # Fusion layer
        self.fusion = nn.Sequential(
            nn.Linear(3, hidden_dim // 2),  # 3 branch outputs
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1)  # Final market score
        )
    
    def forward(self, contract_features, endorsement_features, social_features):
        # Get predictions from each branch
        contract_pred = self.contract_branch(contract_features)
        endorsement_pred = self.endorsement_branch(endorsement_features)
        social_pred = self.social_branch(social_features)
        
        # Combine
        combined = torch.stack([contract_pred, endorsement_pred, social_pred], dim=1)
        market_score = self.fusion(combined)
        
        return market_score.squeeze(-1), {
            'contract': contract_pred,
            'endorsement': endorsement_pred,
            'social': social_pred
        }


def prepare_market_features(df: pd.DataFrame) -> Dict[str, np.ndarray]:
    """Prepare features for market value prediction"""
    
    # Contract branch features (performance-based)
    contract_features = []
    perf_cols = ['career_touchdowns', 'career_yards', 'pro_bowls', 'all_pro_selections', 'age']
    for col in perf_cols:
        if col in df.columns:
            contract_features.append(df[col].fillna(0).values)
    
    if not contract_features:
        contract_features = [df.select_dtypes(include=[np.number]).iloc[:, 0].fillna(0).values]
    
    # Endorsement branch features (social + performance)
    endorsement_features = []
    social_cols = ['instagram_followers', 'twitter_followers', 'tiktok_followers']
    for col in social_cols:
        if col in df.columns:
            endorsement_features.append(df[col].fillna(0).values)
    
    # Social branch features (just social metrics)
    social_features = []
    for col in social_cols:
        if col in df.columns:
            social_features.append(df[col].fillna(0).values)
    
    return {
        'contract': np.column_stack(contract_features) if contract_features else np.zeros((len(df), 1)),
        'endorsement': np.column_stack(endorsement_features) if endorsement_features else np.zeros((len(df), 1)),
        'social': np.column_stack(social_features) if social_features else np.zeros((len(df), 1))
    }

