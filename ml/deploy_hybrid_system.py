#!/usr/bin/env python3
"""
Deploy and Validate Hybrid Ensemble System
==========================================
Deploys the hybrid ensemble and validates against rule-based scoring
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
import torch

from ml.hybrid_ensemble import HybridEnsemble

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_hybrid_system(sport: str, data_file: str, device: str = 'cpu'):
    """
    Deploy hybrid ensemble and validate against rule-based scoring
    
    Args:
        sport: 'nfl', 'nba', or 'cfb'
        data_file: CSV file with player data
        device: 'cpu' or 'cuda'
    """
    logger.info(f"\n{'='*100}")
    logger.info(f"🚀 DEPLOYING HYBRID ENSEMBLE FOR {sport.upper()}")
    logger.info(f"{'='*100}\n")
    
    # Load data
    logger.info(f"📂 Loading {data_file}...")
    df = pd.read_csv(data_file)
    logger.info(f"   Loaded {len(df)} players")
    
    # Initialize hybrid ensemble
    logger.info("🔧 Initializing hybrid ensemble...")
    ensemble = HybridEnsemble(sport=sport, device=device)
    
    # Load trained models (if available)
    try:
        ensemble.load_models(model_dir='models/')
    except FileNotFoundError:
        logger.warning("⚠️  Trained models not found. Using untrained models.")
        logger.warning("   Run train_all_models.py first for best results.")
    
    # Predict with hybrid system
    logger.info("🔮 Running hybrid predictions...")
    df_hybrid = ensemble.predict(df, use_rule_based=True)
    
    # Compare with rule-based only
    from gravity.data_pipeline import GravityScoreCalculator
    calculator = GravityScoreCalculator()
    df_rule_based = calculator.calculate_gravity_scores(df)
    
    # Merge results for comparison
    comparison = pd.DataFrame({
        'player_name': df['player_name'],
        'hybrid_score': df_hybrid['hybrid_gravity_score'],
        'rule_based_score': df_rule_based['gravity_score'],
        'difference': df_hybrid['hybrid_gravity_score'] - df_rule_based['gravity_score'],
        'nn_weight': df_hybrid['nn_weight'],
        'rule_weight': df_hybrid['rule_weight']
    })
    
    # Statistics
    logger.info(f"\n{'='*100}")
    logger.info(f"📊 VALIDATION RESULTS")
    logger.info(f"{'='*100}\n")
    
    logger.info(f"Score Comparison:")
    logger.info(f"   Hybrid Average: {comparison['hybrid_score'].mean():.2f}")
    logger.info(f"   Rule-Based Average: {comparison['rule_based_score'].mean():.2f}")
    logger.info(f"   Average Difference: {comparison['difference'].mean():.2f}")
    logger.info(f"   Correlation: {comparison['hybrid_score'].corr(comparison['rule_based_score']):.3f}")
    
    logger.info(f"\nWeight Distribution:")
    logger.info(f"   Average NN Weight: {comparison['nn_weight'].mean():.3f}")
    logger.info(f"   Average Rule Weight: {comparison['rule_weight'].mean():.3f}")
    logger.info(f"   Players using >50% NN: {(comparison['nn_weight'] > 0.5).sum()} ({(comparison['nn_weight'] > 0.5).sum()/len(comparison)*100:.1f}%)")
    
    # Top players comparison
    logger.info(f"\n🏆 Top 10 Players (Hybrid vs Rule-Based):")
    top_hybrid = comparison.nlargest(10, 'hybrid_score')
    for i, (_, row) in enumerate(top_hybrid.iterrows(), 1):
        logger.info(f"   {i:2d}. {row['player_name']:25s} Hybrid: {row['hybrid_score']:6.2f} | "
                   f"Rule: {row['rule_based_score']:6.2f} | Diff: {row['difference']:+6.2f}")
    
    # Save results
    output_file = f'final_scores/{sport.upper()}_HYBRID_FINAL.csv'
    df_hybrid.to_csv(output_file, index=False)
    logger.info(f"\n💾 Saved hybrid results to {output_file}")
    
    # Save comparison
    comparison_file = f'final_scores/{sport.upper()}_HYBRID_COMPARISON.csv'
    comparison.to_csv(comparison_file, index=False)
    logger.info(f"💾 Saved comparison to {comparison_file}")
    
    logger.info(f"\n{'='*100}")
    logger.info(f"✅ DEPLOYMENT COMPLETE!")
    logger.info(f"{'='*100}\n")
    
    return df_hybrid, comparison


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python deploy_hybrid_system.py sport data.csv [device]")
        print("Example: python deploy_hybrid_system.py nfl final_scores/NFL_COMPLETE_FIXED.csv cpu")
        sys.exit(1)
    
    sport = sys.argv[1]
    data_file = sys.argv[2]
    device = sys.argv[3] if len(sys.argv) > 3 else 'cpu'
    
    validate_hybrid_system(sport, data_file, device)

