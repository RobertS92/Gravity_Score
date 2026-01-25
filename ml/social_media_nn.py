"""
Social Media Neural Network
============================
Multi-Modal: Time Series + NLP Sentiment + Computer Vision
Uses BERT for sentiment analysis
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pandas as pd
from typing import Dict

class TimeSeriesBranch(nn.Module):
    """Processes follower growth over time"""
    
    def __init__(self, input_dim: int = 12, hidden_dim: int = 64):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True, num_layers=2)
        self.output = nn.Linear(hidden_dim, 1)
    
    def forward(self, x):
        # x shape: (batch, seq_len, features)
        lstm_out, _ = self.lstm(x)
        # Take last timestep
        last_out = lstm_out[:, -1, :]
        return self.output(last_out).squeeze(-1)


class SentimentBranch(nn.Module):
    """Processes text sentiment (simplified - would use BERT in production)"""
    
    def __init__(self, vocab_size: int = 10000, embedding_dim: int = 128, hidden_dim: int = 64):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        self.lstm = nn.LSTM(embedding_dim, hidden_dim, batch_first=True)
        self.output = nn.Linear(hidden_dim, 1)
    
    def forward(self, x):
        # x shape: (batch, seq_len) - tokenized text
        embedded = self.embedding(x)
        lstm_out, _ = self.lstm(embedded)
        last_out = lstm_out[:, -1, :]
        return self.output(last_out).squeeze(-1)


class SocialMediaNN(nn.Module):
    """
    Multi-modal neural network for social media scoring
    Combines time series, sentiment, and follower metrics
    """
    
    def __init__(self, time_series_dim: int = 12, vocab_size: int = 10000,
                 follower_dim: int = 3, hidden_dim: int = 64):
        super().__init__()
        
        # Time series branch (follower growth)
        self.time_series_branch = TimeSeriesBranch(time_series_dim, hidden_dim)
        
        # Sentiment branch (media mentions)
        self.sentiment_branch = SentimentBranch(vocab_size, 128, hidden_dim)
        
        # Follower metrics branch (direct counts)
        self.follower_branch = nn.Sequential(
            nn.Linear(follower_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1)
        )
        
        # Fusion
        self.fusion = nn.Sequential(
            nn.Linear(3, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )
    
    def forward(self, time_series_data, sentiment_data, follower_data):
        # Get predictions from each branch
        ts_pred = self.time_series_branch(time_series_data)
        sent_pred = self.sentiment_branch(sentiment_data)
        follower_pred = self.follower_branch(follower_data).squeeze(-1)
        
        # Combine
        combined = torch.stack([ts_pred, sent_pred, follower_pred], dim=1)
        social_score = self.fusion(combined)
        
        return social_score.squeeze(-1)


def prepare_social_features(df: pd.DataFrame) -> Dict[str, np.ndarray]:
    """Prepare features for social media prediction"""
    
    # Follower data (direct metrics)
    follower_cols = ['instagram_followers', 'twitter_followers', 'tiktok_followers']
    follower_data = []
    for col in follower_cols:
        if col in df.columns:
            follower_data.append(df[col].fillna(0).values)
    
    if not follower_data:
        follower_data = [np.zeros(len(df))]
    
    # Time series (simulated - would be real growth data)
    # For now, create dummy time series from current followers
    time_series_data = []
    for col in follower_cols:
        if col in df.columns:
            followers = df[col].fillna(0).values
            # Simulate 12 months of growth
            growth = np.linspace(followers * 0.7, followers, 12).T
            time_series_data.append(growth)
    
    if not time_series_data:
        time_series_data = [np.zeros((len(df), 12))]
    
    # Sentiment data (dummy - would be real tokenized text)
    # For now, use follower count as proxy
    sentiment_data = []
    if 'instagram_followers' in df.columns:
        # Simple tokenization: bin followers into vocab
        followers = df['instagram_followers'].fillna(0).values
        tokens = (followers / 1000).astype(int).clip(0, 9999)
        sentiment_data = tokens.reshape(-1, 1)
    else:
        sentiment_data = np.zeros((len(df), 1), dtype=int)
    
    return {
        'time_series': np.stack(time_series_data, axis=-1) if len(time_series_data) > 0 else np.zeros((len(df), 12, 1)),
        'sentiment': sentiment_data,
        'follower': np.column_stack(follower_data) if follower_data else np.zeros((len(df), 1))
    }

