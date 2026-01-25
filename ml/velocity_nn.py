"""
Velocity/Trajectory Neural Network
===================================
Transformer-based sequence model for predicting future trajectory
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pandas as pd
import math

class PositionalEncoding(nn.Module):
    """Positional encoding for transformer"""
    
    def __init__(self, d_model: int, max_len: int = 100):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        self.register_buffer('pe', pe)
    
    def forward(self, x):
        return x + self.pe[:, :x.size(1), :]


class TransformerBlock(nn.Module):
    """Transformer encoder block"""
    
    def __init__(self, d_model: int, nhead: int = 8, dim_feedforward: int = 256, dropout: float = 0.1):
        super().__init__()
        self.self_attn = nn.MultiheadAttention(d_model, nhead, dropout=dropout, batch_first=True)
        self.ffn = nn.Sequential(
            nn.Linear(d_model, dim_feedforward),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(dim_feedforward, d_model)
        )
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x):
        # Self-attention
        attn_out, _ = self.self_attn(x, x, x)
        x = self.norm1(x + self.dropout(attn_out))
        
        # Feed-forward
        ffn_out = self.ffn(x)
        x = self.norm2(x + self.dropout(ffn_out))
        
        return x


class VelocityNN(nn.Module):
    """
    Transformer-based neural network for velocity/trajectory prediction
    Predicts future performance trajectory from historical sequences
    """
    
    def __init__(self, input_dim: int = 20, d_model: int = 128, nhead: int = 8,
                 num_layers: int = 3, dim_feedforward: int = 256):
        super().__init__()
        
        # Input projection
        self.input_proj = nn.Linear(input_dim, d_model)
        self.pos_encoding = PositionalEncoding(d_model)
        
        # Transformer layers
        self.transformer_layers = nn.ModuleList([
            TransformerBlock(d_model, nhead, dim_feedforward)
            for _ in range(num_layers)
        ])
        
        # Output layers
        self.output = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(d_model // 2, 1)  # Velocity score
        )
    
    def forward(self, x):
        # Input projection
        x = self.input_proj(x)
        
        # Positional encoding
        x = self.pos_encoding(x)
        
        # Transformer layers
        for layer in self.transformer_layers:
            x = layer(x)
        
        # Global average pooling
        x = x.mean(dim=1)
        
        # Output
        velocity_score = self.output(x)
        return velocity_score.squeeze(-1)


def prepare_velocity_features(df: pd.DataFrame, sport: str) -> np.ndarray:
    """Prepare features for velocity prediction (year-over-year stats)"""
    
    features = []
    
    # Current vs previous year stats (simulated - would be real time series)
    stat_cols = {
        'nfl': ['career_touchdowns', 'career_yards', 'pro_bowls'],
        'nba': ['career_points', 'career_assists', 'career_rebounds'],
        'cfb': ['career_touchdowns', 'career_yards']
    }
    
    for col in stat_cols.get(sport, []):
        if col in df.columns:
            current = df[col].fillna(0).values
            # Simulate previous year (80% of current)
            previous = current * 0.8
            # Growth rate
            growth = (current - previous) / (previous + 1)
            features.extend([current, previous, growth])
    
    # Age and experience
    if 'age' in df.columns:
        features.append(df['age'].fillna(25).values)
    if 'years_in_league' in df.columns:
        features.append(df['years_in_league'].fillna(3).values)
    
    if features:
        feature_matrix = np.column_stack(features)
    else:
        feature_matrix = np.zeros((len(df), 20))
    
    # Reshape for sequence (batch, seq_len, features)
    # For now, create sequence from features
    seq_len = 5
    if feature_matrix.shape[1] >= seq_len:
        # Use first seq_len features as sequence
        feature_matrix = feature_matrix[:, :seq_len].reshape(len(df), seq_len, -1)
    else:
        # Pad or repeat
        feature_matrix = np.repeat(feature_matrix[:, np.newaxis, :], seq_len, axis=1)
    
    return feature_matrix

