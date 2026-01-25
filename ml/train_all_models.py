#!/usr/bin/env python3
"""
Train All Neural Networks
=========================
Training pipeline for all 5 specialized neural networks
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import pandas as pd
import logging
from pathlib import Path
from typing import Dict, Tuple
from tqdm import tqdm
import json

from ml.performance_nn import PerformanceScoringNN, prepare_performance_features
from ml.market_value_nn import MarketValueNN, prepare_market_features
from ml.social_media_nn import SocialMediaNN, prepare_social_features
from ml.velocity_nn import VelocityNN, prepare_velocity_features
from ml.risk_assessment_nn import RiskAssessmentNN, prepare_risk_features

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlayerDataset(Dataset):
    """Dataset for player data"""
    
    def __init__(self, features, targets):
        self.features = torch.FloatTensor(features)
        self.targets = torch.FloatTensor(targets)
    
    def __len__(self):
        return len(self.features)
    
    def __getitem__(self, idx):
        return self.features[idx], self.targets[idx]


def train_model(model, train_loader, val_loader, epochs: int = 10, 
                device: str = 'cpu', model_name: str = 'model'):
    """Train a neural network model"""
    
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=3)
    
    best_val_loss = float('inf')
    train_losses = []
    val_losses = []
    
    logger.info(f"\n🎓 Training {model_name}...")
    logger.info(f"   Epochs: {epochs}")
    logger.info(f"   Device: {device}")
    logger.info(f"   Training samples: {len(train_loader.dataset)}")
    logger.info(f"   Validation samples: {len(val_loader.dataset)}")
    
    for epoch in range(epochs):
        # Training
        model.train()
        train_loss = 0.0
        for features, targets in tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}"):
            features = features.to(device)
            targets = targets.to(device)
            
            optimizer.zero_grad()
            outputs = model(features)
            if isinstance(outputs, dict):
                outputs = outputs['overall_risk']
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
        
        train_loss /= len(train_loader)
        train_losses.append(train_loss)
        
        # Validation
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for features, targets in val_loader:
                features = features.to(device)
                targets = targets.to(device)
                
                outputs = model(features)
                if isinstance(outputs, dict):
                    outputs = outputs['overall_risk']
                loss = criterion(outputs, targets)
                val_loss += loss.item()
        
        val_loss /= len(val_loader)
        val_losses.append(val_loss)
        
        scheduler.step(val_loss)
        
        logger.info(f"   Epoch {epoch+1}: Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}")
        
        # Save best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            model_path = f'models/{model_name}.pth'
            Path('models').mkdir(exist_ok=True)
            torch.save(model.state_dict(), model_path)
            logger.info(f"   ✅ Saved best model (val_loss: {val_loss:.4f})")
    
    logger.info(f"✅ Training complete! Best val loss: {best_val_loss:.4f}")
    return train_losses, val_losses


def train_performance_nn(df: pd.DataFrame, sport: str, device: str = 'cpu'):
    """Train performance scoring neural network"""
    logger.info("\n" + "="*100)
    logger.info("🏀 TRAINING PERFORMANCE SCORING NN")
    logger.info("="*100)
    
    # Prepare features
    features = prepare_performance_features(df, sport)
    
    # Create targets (use existing performance scores or calculate from stats)
    if 'gravity.performance_score' in df.columns:
        targets = df['gravity.performance_score'].values / 100.0  # Normalize to 0-1
    else:
        # Calculate from stats
        targets = np.zeros(len(df))
        if 'career_touchdowns' in df.columns:
            targets += df['career_touchdowns'].fillna(0).values / 100.0
        if 'pro_bowls' in df.columns:
            targets += df['pro_bowls'].fillna(0).values / 10.0
        targets = np.clip(targets, 0, 1)
    
    # Split data
    split_idx = int(len(features) * 0.8)
    train_features, val_features = features[:split_idx], features[split_idx:]
    train_targets, val_targets = targets[:split_idx], targets[split_idx:]
    
    # Create datasets
    train_dataset = PlayerDataset(train_features, train_targets)
    val_dataset = PlayerDataset(val_features, val_targets)
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)
    
    # Create model
    model = PerformanceScoringNN(input_dim=train_features.shape[-1]).to(device)
    
    # Train
    train_losses, val_losses = train_model(model, train_loader, val_loader, 
                                          epochs=10, device=device, 
                                          model_name=f'performance_nn_{sport}')
    
    return model, train_losses, val_losses


def train_market_nn(df: pd.DataFrame, sport: str, device: str = 'cpu'):
    """Train market value neural network"""
    logger.info("\n" + "="*100)
    logger.info("💰 TRAINING MARKET VALUE NN")
    logger.info("="*100)
    
    # Prepare features
    market_features = prepare_market_features(df)
    
    # Create targets
    if 'gravity.market_score' in df.columns:
        targets = df['gravity.market_score'].values / 100.0
    else:
        # Calculate from contract/endorsement
        targets = np.zeros(len(df))
        if 'contract_value' in df.columns:
            targets += (df['contract_value'].fillna(0).values / 100_000_000).clip(0, 1)
        targets = targets.clip(0, 1)
    
    # Split data
    split_idx = int(len(df) * 0.8)
    
    # Create custom dataset for multi-input model
    class MarketDataset(Dataset):
        def __init__(self, features_dict, targets, indices):
            self.contract = torch.FloatTensor(features_dict['contract'][indices])
            self.endorsement = torch.FloatTensor(features_dict['endorsement'][indices])
            self.social = torch.FloatTensor(features_dict['social'][indices])
            self.targets = torch.FloatTensor(targets[indices])
        
        def __len__(self):
            return len(self.targets)
        
        def __getitem__(self, idx):
            return (self.contract[idx], self.endorsement[idx], self.social[idx]), self.targets[idx]
    
    train_indices = np.arange(split_idx)
    val_indices = np.arange(split_idx, len(df))
    
    train_dataset = MarketDataset(market_features, targets, train_indices)
    val_dataset = MarketDataset(market_features, targets, val_indices)
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)
    
    # Create model
    model = MarketValueNN(
        contract_input_dim=market_features['contract'].shape[1],
        endorsement_input_dim=market_features['endorsement'].shape[1],
        social_input_dim=market_features['social'].shape[1]
    ).to(device)
    
    # Custom training loop for multi-input model
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    best_val_loss = float('inf')
    for epoch in range(10):
        model.train()
        train_loss = 0.0
        for (contract, endorsement, social), targets in tqdm(train_loader, desc=f"Epoch {epoch+1}/10"):
            contract = contract.to(device)
            endorsement = endorsement.to(device)
            social = social.to(device)
            targets = targets.to(device)
            
            optimizer.zero_grad()
            outputs, _ = model(contract, endorsement, social)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
        
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for (contract, endorsement, social), targets in val_loader:
                contract = contract.to(device)
                endorsement = endorsement.to(device)
                social = social.to(device)
                targets = targets.to(device)
                
                outputs, _ = model(contract, endorsement, social)
                loss = criterion(outputs, targets)
                val_loss += loss.item()
        
        val_loss /= len(val_loader)
        logger.info(f"   Epoch {epoch+1}: Train Loss: {train_loss/len(train_loader):.4f}, Val Loss: {val_loss:.4f}")
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), f'models/market_nn_{sport}.pth')
            logger.info(f"   ✅ Saved best model")
    
    return model


def train_social_nn(df: pd.DataFrame, sport: str, device: str = 'cpu'):
    """Train social media neural network"""
    logger.info("\n" + "="*100)
    logger.info("📱 TRAINING SOCIAL MEDIA NN")
    logger.info("="*100)
    
    # Prepare features
    social_features = prepare_social_features(df)
    
    # Create targets
    if 'gravity.social_score' in df.columns:
        targets = df['gravity.social_score'].values / 100.0
    else:
        # Calculate from followers
        targets = np.zeros(len(df))
        if 'instagram_followers' in df.columns:
            targets += np.log10(df['instagram_followers'].fillna(0).values + 1) / 8.0
        targets = targets.clip(0, 1)
    
    # Split and create datasets (similar to market NN)
    split_idx = int(len(df) * 0.8)
    
    class SocialDataset(Dataset):
        def __init__(self, features_dict, targets, indices):
            self.time_series = torch.FloatTensor(features_dict['time_series'][indices])
            self.sentiment = torch.LongTensor(features_dict['sentiment'][indices])
            self.follower = torch.FloatTensor(features_dict['follower'][indices])
            self.targets = torch.FloatTensor(targets[indices])
        
        def __len__(self):
            return len(self.targets)
        
        def __getitem__(self, idx):
            return (self.time_series[idx], self.sentiment[idx], self.follower[idx]), self.targets[idx]
    
    train_indices = np.arange(split_idx)
    val_indices = np.arange(split_idx, len(df))
    
    train_dataset = SocialDataset(social_features, targets, train_indices)
    val_dataset = SocialDataset(social_features, targets, val_indices)
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)
    
    # Create model
    model = SocialMediaNN(
        time_series_dim=social_features['time_series'].shape[-1],
        follower_dim=social_features['follower'].shape[1]
    ).to(device)
    
    # Train
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    best_val_loss = float('inf')
    for epoch in range(10):
        model.train()
        train_loss = 0.0
        for (ts, sent, fol), targets in tqdm(train_loader, desc=f"Epoch {epoch+1}/10"):
            ts = ts.to(device)
            sent = sent.to(device)
            fol = fol.to(device)
            targets = targets.to(device)
            
            optimizer.zero_grad()
            outputs = model(ts, sent, fol)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
        
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for (ts, sent, fol), targets in val_loader:
                ts = ts.to(device)
                sent = sent.to(device)
                fol = fol.to(device)
                targets = targets.to(device)
                
                outputs = model(ts, sent, fol)
                loss = criterion(outputs, targets)
                val_loss += loss.item()
        
        val_loss /= len(val_loader)
        logger.info(f"   Epoch {epoch+1}: Train Loss: {train_loss/len(train_loader):.4f}, Val Loss: {val_loss:.4f}")
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), f'models/social_nn_{sport}.pth')
            logger.info(f"   ✅ Saved best model")
    
    return model


def train_velocity_nn(df: pd.DataFrame, sport: str, device: str = 'cpu'):
    """Train velocity/trajectory neural network"""
    logger.info("\n" + "="*100)
    logger.info("📈 TRAINING VELOCITY NN")
    logger.info("="*100)
    
    # Prepare features
    features = prepare_velocity_features(df, sport)
    
    # Create targets
    if 'gravity.velocity_score' in df.columns:
        targets = df['gravity.velocity_score'].values / 100.0
    else:
        # Calculate from age and performance trend
        targets = np.ones(len(df)) * 0.5  # Default
        if 'age' in df.columns:
            age = df['age'].fillna(25).values
            # Optimal age: 24-29
            targets = 1.0 - np.abs(age - 26.5) / 20.0
        targets = targets.clip(0, 1)
    
    # Split data
    split_idx = int(len(features) * 0.8)
    train_features, val_features = features[:split_idx], features[split_idx:]
    train_targets, val_targets = targets[:split_idx], targets[split_idx:]
    
    # Create datasets - velocity features are sequences (batch, seq_len, features)
    class VelocityDataset(Dataset):
        def __init__(self, features, targets):
            self.features = torch.FloatTensor(features)
            self.targets = torch.FloatTensor(targets)
        
        def __len__(self):
            return len(self.features)
        
        def __getitem__(self, idx):
            return self.features[idx], self.targets[idx]
    
    train_dataset = VelocityDataset(train_features, train_targets)
    val_dataset = VelocityDataset(val_features, val_targets)
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)
    
    # Create model
    model = VelocityNN(input_dim=train_features.shape[-1]).to(device)
    
    # Train
    train_losses, val_losses = train_model(model, train_loader, val_loader,
                                          epochs=10, device=device,
                                          model_name=f'velocity_nn_{sport}')
    
    return model


def train_risk_nn(df: pd.DataFrame, sport: str, device: str = 'cpu'):
    """Train risk assessment neural network"""
    logger.info("\n" + "="*100)
    logger.info("⚠️  TRAINING RISK ASSESSMENT NN")
    logger.info("="*100)
    
    # Prepare features
    features = prepare_risk_features(df)
    
    # Create targets (multi-task)
    if 'gravity.risk_score' in df.columns:
        risk_targets = df['gravity.risk_score'].values / 100.0
    else:
        risk_targets = np.ones(len(df)) * 0.8  # Default low risk
    
    # Injury risk targets
    if 'games_missed_career' in df.columns:
        injury_targets = (df['games_missed_career'].fillna(0).values / 50.0).clip(0, 1)
    else:
        injury_targets = np.zeros(len(df))
    
    # Controversy risk targets
    if 'controversies' in df.columns:
        controversy_targets = (df['controversies'].fillna(0).values / 5.0).clip(0, 1)
    else:
        controversy_targets = np.zeros(len(df))
    
    # Split data
    split_idx = int(len(features) * 0.8)
    train_features, val_features = features[:split_idx], features[split_idx:]
    train_risk, val_risk = risk_targets[:split_idx], risk_targets[split_idx:]
    train_injury, val_injury = injury_targets[:split_idx], injury_targets[split_idx:]
    train_controversy, val_controversy = controversy_targets[:split_idx], controversy_targets[split_idx:]
    
    # Create datasets
    class RiskDataset(Dataset):
        def __init__(self, features, risk, injury, controversy):
            self.features = torch.FloatTensor(features)
            self.risk = torch.FloatTensor(risk)
            self.injury = torch.FloatTensor(injury)
            self.controversy = torch.FloatTensor(controversy)
        
        def __len__(self):
            return len(self.features)
        
        def __getitem__(self, idx):
            return self.features[idx], (self.risk[idx], self.injury[idx], self.controversy[idx])
    
    train_dataset = RiskDataset(train_features, train_risk, train_injury, train_controversy)
    val_dataset = RiskDataset(val_features, val_risk, val_injury, val_controversy)
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)
    
    # Create model
    model = RiskAssessmentNN(input_dim=train_features.shape[1]).to(device)
    
    # Train with multi-task loss
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    best_val_loss = float('inf')
    for epoch in range(10):
        model.train()
        train_loss = 0.0
        for features, (risk, injury, controversy) in tqdm(train_loader, desc=f"Epoch {epoch+1}/10"):
            features = features.to(device)
            risk = risk.to(device)
            injury = injury.to(device)
            controversy = controversy.to(device)
            
            optimizer.zero_grad()
            outputs = model(features)
            
            # Multi-task loss
            loss = (criterion(outputs['overall_risk'], risk) +
                   criterion(outputs['injury_risk'], injury) +
                   criterion(outputs['controversy_risk'], controversy)) / 3.0
            
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
        
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for features, (risk, injury, controversy) in val_loader:
                features = features.to(device)
                risk = risk.to(device)
                injury = injury.to(device)
                controversy = controversy.to(device)
                
                outputs = model(features)
                loss = (criterion(outputs['overall_risk'], risk) +
                       criterion(outputs['injury_risk'], injury) +
                       criterion(outputs['controversy_risk'], controversy)) / 3.0
                val_loss += loss.item()
        
        val_loss /= len(val_loader)
        logger.info(f"   Epoch {epoch+1}: Train Loss: {train_loss/len(train_loader):.4f}, Val Loss: {val_loss:.4f}")
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), f'models/risk_nn_{sport}.pth')
            logger.info(f"   ✅ Saved best model")
    
    return model


def train_all_models(sport: str, data_file: str, device: str = 'cpu'):
    """
    Train all 5 neural networks for a sport
    
    Args:
        sport: 'nfl', 'nba', or 'cfb'
        data_file: CSV file with player data
        device: 'cpu' or 'cuda'
    """
    logger.info(f"\n{'='*100}")
    logger.info(f"🎓 TRAINING ALL NEURAL NETWORKS FOR {sport.upper()}")
    logger.info(f"{'='*100}\n")
    
    # Load data
    logger.info(f"📂 Loading {data_file}...")
    df = pd.read_csv(data_file)
    logger.info(f"   Loaded {len(df)} players")
    
    # Create models directory
    Path('models').mkdir(exist_ok=True)
    
    # Train each model
    try:
        train_performance_nn(df, sport, device)
        train_market_nn(df, sport, device)
        train_social_nn(df, sport, device)
        train_velocity_nn(df, sport, device)
        train_risk_nn(df, sport, device)
        
        logger.info(f"\n{'='*100}")
        logger.info(f"✅ ALL MODELS TRAINED SUCCESSFULLY!")
        logger.info(f"{'='*100}\n")
        logger.info(f"📁 Models saved to models/ directory:")
        logger.info(f"   • performance_nn_{sport}.pth")
        logger.info(f"   • market_nn_{sport}.pth")
        logger.info(f"   • social_nn_{sport}.pth")
        logger.info(f"   • velocity_nn_{sport}.pth")
        logger.info(f"   • risk_nn_{sport}.pth")
        
    except Exception as e:
        logger.error(f"❌ Training failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python train_all_models.py sport data.csv [device]")
        print("Example: python train_all_models.py nfl final_scores/NFL_COMPLETE_FIXED.csv cuda")
        sys.exit(1)
    
    sport = sys.argv[1]
    data_file = sys.argv[2]
    device = sys.argv[3] if len(sys.argv) > 3 else 'cpu'
    
    train_all_models(sport, data_file, device)

