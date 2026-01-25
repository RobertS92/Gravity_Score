"""
Performance Scoring Neural Network
==================================
Multi-Head Attention + Dense Network for temporal performance sequences
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pandas as pd
from typing import Dict, List, Optional

class MultiHeadAttention(nn.Module):
    """Multi-head self-attention mechanism"""
    
    def __init__(self, d_model: int, num_heads: int = 8):
        super().__init__()
        assert d_model % num_heads == 0
        
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads
        
        self.W_q = nn.Linear(d_model, d_model)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.W_o = nn.Linear(d_model, d_model)
        
    def forward(self, x):
        batch_size = x.size(0)
        
        # Linear projections
        Q = self.W_q(x).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        K = self.W_k(x).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        V = self.W_v(x).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        
        # Scaled dot-product attention
        scores = torch.matmul(Q, K.transpose(-2, -1)) / np.sqrt(self.d_k)
        attention = F.softmax(scores, dim=-1)
        context = torch.matmul(attention, V)
        
        # Concatenate heads
        context = context.transpose(1, 2).contiguous().view(
            batch_size, -1, self.d_model
        )
        
        return self.W_o(context)


class PerformanceScoringNN(nn.Module):
    """
    Neural network for performance scoring
    Uses multi-head attention to process temporal sequences (year-over-year stats)
    """
    
    def __init__(self, input_dim: int = 50, hidden_dim: int = 128, num_heads: int = 8):
        super().__init__()
        
        # Input projection
        self.input_proj = nn.Linear(input_dim, hidden_dim)
        
        # Multi-head attention
        self.attention = MultiHeadAttention(hidden_dim, num_heads)
        
        # Feed-forward network
        self.ffn = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim * 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU()
        )
        
        # Layer normalization
        self.norm1 = nn.LayerNorm(hidden_dim)
        self.norm2 = nn.LayerNorm(hidden_dim)
        
        # Output layers
        self.output_layers = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim // 2, hidden_dim // 4),
            nn.ReLU(),
            nn.Linear(hidden_dim // 4, 1)  # Single output: performance score
        )
        
    def forward(self, x):
        # Input projection
        x = self.input_proj(x)
        
        # Self-attention
        attn_out = self.attention(x)
        x = self.norm1(x + attn_out)  # Residual connection
        
        # Feed-forward
        ffn_out = self.ffn(x)
        x = self.norm2(x + ffn_out)  # Residual connection
        
        # Global average pooling (if sequence)
        if len(x.shape) > 2:
            x = x.mean(dim=1)  # Average over sequence length
        
        # Output
        score = self.output_layers(x)
        return score.squeeze(-1)


def prepare_performance_features(df: pd.DataFrame, sport: str) -> np.ndarray:
    """
    Prepare features for performance scoring
    
    Args:
        df: DataFrame with player data
        sport: 'nfl', 'nba', or 'cfb'
        
    Returns:
        Feature matrix (n_samples, n_features)
    """
    features = []
    
    # Career stats
    career_cols = {
        'nfl': ['career_touchdowns', 'career_yards', 'career_receptions', 
                'career_completions', 'career_sacks', 'career_interceptions'],
        'nba': ['career_points', 'career_assists', 'career_rebounds', 
                'career_steals', 'career_blocks'],
        'cfb': ['career_touchdowns', 'career_yards', 'career_receptions']
    }
    
    for col in career_cols.get(sport, []):
        if col in df.columns:
            features.append(df[col].fillna(0).values)
    
    # Awards
    award_cols = ['pro_bowls', 'all_pro_selections', 'awards']
    for col in award_cols:
        if col in df.columns:
            features.append(df[col].fillna(0).values)
    
    # Age and experience
    if 'age' in df.columns:
        features.append(df['age'].fillna(25).values)
    if 'years_in_league' in df.columns:
        features.append(df['years_in_league'].fillna(3).values)
    
    # Stack features
    if features:
        feature_matrix = np.column_stack(features)
    else:
        # Fallback: use all numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns[:50]
        feature_matrix = df[numeric_cols].fillna(0).values
    
    return feature_matrix

