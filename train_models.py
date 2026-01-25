#!/usr/bin/env python3
"""
Automated Model Training Pipeline
==================================

Train all ML models on historical player data:
1. Load and prepare training data
2. Train imputation models
3. Train prediction models
4. Evaluate and save models
5. Generate performance reports

Usage:
    python train_models.py --data scrapes/NFL/*/nfl_players_*.csv
    python train_models.py --data training_data.csv --models all
    python train_models.py --data training_data.csv --models draft,contract

Author: Gravity Score Team
"""

import argparse
import logging
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
import json
from datetime import datetime
import glob

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from gravity.ml_imputer import MLImputer, create_training_dataset
from gravity.ml_models import ModelFactory
from gravity.ml_feature_engineering import MLFeatureEngineer, FeatureSelector
from gravity.data_pipeline import DataFlattener

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# TRAINING PIPELINE
# ============================================================================

class ModelTrainingPipeline:
    """
    Automated pipeline for training all ML models
    """
    
    def __init__(self, output_dir: str = "models"):
        """
        Initialize training pipeline
        
        Args:
            output_dir: Directory to save trained models and reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.imputation_dir = self.output_dir / "imputation"
        self.prediction_dir = self.output_dir / "prediction"
        self.reports_dir = self.output_dir / "reports"
        
        self.imputation_dir.mkdir(exist_ok=True)
        self.prediction_dir.mkdir(exist_ok=True)
        self.reports_dir.mkdir(exist_ok=True)
        
        self.training_results = {
            'timestamp': datetime.now().isoformat(),
            'imputation_models': {},
            'prediction_models': {},
            'data_stats': {}
        }
    
    def load_data(self, data_paths: List[str]) -> pd.DataFrame:
        """
        Load and combine training data from multiple sources
        
        Args:
            data_paths: List of CSV file paths (supports wildcards)
            
        Returns:
            Combined DataFrame
        """
        logger.info("=" * 80)
        logger.info("📂 LOADING TRAINING DATA")
        logger.info("=" * 80)
        
        all_files = []
        for pattern in data_paths:
            files = glob.glob(pattern)
            all_files.extend(files)
        
        if not all_files:
            raise ValueError(f"No files found matching patterns: {data_paths}")
        
        logger.info(f"Found {len(all_files)} data files")
        
        dfs = []
        for file_path in all_files:
            try:
                df = pd.read_csv(file_path)
                dfs.append(df)
                logger.info(f"  ✅ Loaded {len(df)} rows from {Path(file_path).name}")
            except Exception as e:
                logger.error(f"  ❌ Failed to load {file_path}: {e}")
        
        if not dfs:
            raise ValueError("No valid data files loaded")
        
        # Combine all data
        combined = pd.concat(dfs, ignore_index=True)
        
        # Remove duplicates
        if 'player_name' in combined.columns:
            before = len(combined)
            combined = combined.drop_duplicates(subset=['player_name'], keep='last')
            logger.info(f"  Removed {before - len(combined)} duplicate players")
        
        # Data statistics
        self.training_results['data_stats'] = {
            'total_players': len(combined),
            'total_files': len(all_files),
            'columns': len(combined.columns),
            'missing_percentage': combined.isna().sum().sum() / (len(combined) * len(combined.columns)) * 100
        }
        
        logger.info(f"\n✅ Loaded {len(combined)} total players")
        logger.info(f"   Columns: {len(combined.columns)}")
        logger.info(f"   Missing data: {self.training_results['data_stats']['missing_percentage']:.1f}%\n")
        
        return combined
    
    def flatten_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Flatten nested data structures
        
        Args:
            df: Raw DataFrame (may have nested JSON columns)
            
        Returns:
            Flattened DataFrame
        """
        logger.info("=" * 80)
        logger.info("🔄 FLATTENING DATA")
        logger.info("=" * 80)
        
        # Check if data is already flat or needs flattening
        nested_cols = [col for col in df.columns if '.' not in col and col not in [
            'player_name', 'team', 'position', 'collection_timestamp', 'data_quality_score'
        ]]
        
        if len(nested_cols) < 5:
            # Already flat
            logger.info("Data appears to be already flattened\n")
            return df
        
        # Need to flatten
        flattener = DataFlattener()
        
        # Check if we need to parse JSON columns
        json_cols = []
        for col in df.columns:
            if col in ['identity', 'brand', 'proof', 'proximity', 'velocity', 'risk']:
                if df[col].dtype == 'object':
                    # Try to parse as JSON
                    try:
                        df[col] = df[col].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
                        json_cols.append(col)
                    except:
                        pass
        
        if json_cols:
            logger.info(f"Parsed {len(json_cols)} JSON columns: {json_cols}")
            
            # Flatten each row
            flattened_rows = []
            for _, row in df.iterrows():
                flat_row = flattener.flatten_player_data(row.to_dict())
                flattened_rows.append(flat_row)
            
            df_flat = pd.DataFrame(flattened_rows)
            logger.info(f"✅ Flattened to {len(df_flat.columns)} columns\n")
            return df_flat
        else:
            logger.info("No nested structures found\n")
            return df
    
    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create engineered features
        
        Args:
            df: Flattened DataFrame
            
        Returns:
            DataFrame with engineered features
        """
        logger.info("=" * 80)
        logger.info("🔧 ENGINEERING FEATURES")
        logger.info("=" * 80)
        
        engineer = MLFeatureEngineer()
        df_engineered = engineer.engineer_features(df, include_all=True)
        
        n_new_features = len(engineer.get_feature_names())
        logger.info(f"✅ Created {n_new_features} engineered features\n")
        
        return df_engineered
    
    def train_imputation_models(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Train imputation models
        
        Args:
            df: Training data
            
        Returns:
            Training results
        """
        logger.info("=" * 80)
        logger.info("🤖 TRAINING IMPUTATION MODELS")
        logger.info("=" * 80)
        
        imputer = MLImputer(models_dir=str(self.imputation_dir))
        
        # Define targets to impute
        imputation_targets = [
            'identity.age',
            'identity.height',
            'identity.weight',
            'identity.contract_value',
            'identity.years_in_league',
            'brand.instagram_followers',
            'brand.twitter_followers',
            'proof.career_points',
            'proof.career_yards'
        ]
        
        # Filter to targets that exist and have enough data
        available_targets = [t for t in imputation_targets if t in df.columns 
                           and df[t].notna().sum() >= 50]
        
        logger.info(f"Training imputation models for {len(available_targets)} fields...\n")
        
        results = imputer.train_imputation_models(df, targets=available_targets)
        
        self.training_results['imputation_models'] = results
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ IMPUTATION MODELS TRAINED")
        logger.info("=" * 80)
        for target, result in results.items():
            if isinstance(result, dict):
                if 'error' not in result:
                    perf = result.get('performance', {})
                    logger.info(f"  {target}: {perf}")
                else:
                    logger.warning(f"  {target}: {result.get('error', 'Unknown error')}")
            else:
                logger.warning(f"  {target}: {result}")
        logger.info("")
        
        return results
    
    def train_prediction_models(
        self, 
        df: pd.DataFrame, 
        models_to_train: List[str] = None
    ) -> Dict[str, Any]:
        """
        Train prediction models
        
        Args:
            df: Training data (with imputed values and engineered features)
            models_to_train: List of model types to train (default: all)
            
        Returns:
            Training results
        """
        logger.info("=" * 80)
        logger.info("🎯 TRAINING PREDICTION MODELS")
        logger.info("=" * 80)
        
        if models_to_train is None:
            models_to_train = ['draft', 'contract', 'performance', 'injury', 'market']
        
        results = {}
        
        for model_type in models_to_train:
            logger.info(f"\n{'─' * 80}")
            logger.info(f"Training {model_type.upper()} predictor...")
            logger.info('─' * 80)
            
            try:
                model_path = self.prediction_dir / f"{model_type}_predictor.pkl"
                model = ModelFactory.create_model(model_type, str(model_path))
                
                # Train model (each model has its own logic for feature selection)
                if model_type == 'draft':
                    # Only train on college players with draft data
                    perf = model.train(df, target='identity.draft_round')
                elif model_type == 'contract':
                    perf = model.train(df, target='identity.contract_value')
                elif model_type == 'performance':
                    perf = model.train(df)
                elif model_type == 'injury':
                    perf = model.train(df)
                elif model_type == 'market':
                    # Need gravity_score in data
                    if 'gravity_score' in df.columns:
                        perf = model.train(df, target='gravity_score')
                    else:
                        logger.warning(f"  ⚠️  gravity_score not in data, skipping market predictor")
                        continue
                
                # Save model
                model.save()
                
                results[model_type] = {
                    'performance': perf,
                    'feature_count': len(model.feature_columns),
                    'top_features': model.get_feature_importance(top_n=10)
                }
                
                logger.info(f"✅ {model_type.upper()} predictor trained successfully")
                logger.info(f"   Performance: {perf}")
                logger.info(f"   Features used: {len(model.feature_columns)}")
                
            except ValueError as e:
                logger.warning(f"  ⚠️  Cannot train {model_type} predictor: {e}")
                results[model_type] = {'error': str(e)}
            except Exception as e:
                logger.error(f"  ❌ Failed to train {model_type} predictor: {e}")
                results[model_type] = {'error': str(e)}
        
        self.training_results['prediction_models'] = results
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ PREDICTION MODELS TRAINED")
        logger.info("=" * 80)
        for model_type, result in results.items():
            if 'error' not in result:
                logger.info(f"  {model_type}: ✓")
        logger.info("")
        
        return results
    
    def generate_report(self):
        """Generate training report"""
        logger.info("=" * 80)
        logger.info("📊 GENERATING TRAINING REPORT")
        logger.info("=" * 80)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.reports_dir / f"training_report_{timestamp}.json"
        
        with open(report_path, 'w') as f:
            json.dump(self.training_results, f, indent=2)
        
        logger.info(f"\n✅ Training report saved to: {report_path}")
        
        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("📈 TRAINING SUMMARY")
        logger.info("=" * 80)
        
        logger.info(f"\n📊 Data Statistics:")
        for key, value in self.training_results['data_stats'].items():
            logger.info(f"  {key}: {value}")
        
        logger.info(f"\n🤖 Imputation Models Trained: {len(self.training_results['imputation_models'])}")
        for target, result in self.training_results['imputation_models'].items():
            if 'error' not in result:
                logger.info(f"  ✓ {target}")
        
        logger.info(f"\n🎯 Prediction Models Trained: {len([m for m in self.training_results['prediction_models'].values() if 'error' not in m])}")
        for model_type, result in self.training_results['prediction_models'].items():
            if 'error' not in result:
                logger.info(f"  ✓ {model_type}")
        
        logger.info("\n" + "=" * 80)
        logger.info("🎉 TRAINING COMPLETE!")
        logger.info("=" * 80)
    
    def run_full_pipeline(
        self, 
        data_paths: List[str], 
        models_to_train: List[str] = None
    ):
        """
        Run complete training pipeline
        
        Args:
            data_paths: List of data file paths
            models_to_train: List of model types to train (default: all)
        """
        logger.info("\n" + "=" * 80)
        logger.info("🚀 STARTING MODEL TRAINING PIPELINE")
        logger.info("=" * 80)
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Timestamp: {self.training_results['timestamp']}\n")
        
        try:
            # 1. Load data
            df = self.load_data(data_paths)
            
            # 2. Flatten data
            df = self.flatten_data(df)
            
            # 3. Engineer features
            df = self.engineer_features(df)
            
            # 4. Train imputation models
            self.train_imputation_models(df)
            
            # 5. Apply imputation to training data
            logger.info("=" * 80)
            logger.info("🔄 APPLYING IMPUTATION TO TRAINING DATA")
            logger.info("=" * 80)
            imputer = MLImputer(models_dir=str(self.imputation_dir))
            imputer.load_models()
            df = imputer.impute_dataframe(df, use_ml=True)
            logger.info("✅ Imputation applied\n")
            
            # 6. Train prediction models
            self.train_prediction_models(df, models_to_train=models_to_train)
            
            # 7. Generate report
            self.generate_report()
            
            # 8. Update registry
            self.update_registry()
            
        except Exception as e:
            logger.error(f"\n❌ PIPELINE FAILED: {e}")
            raise
    
    def update_registry(self):
        """Update model registry with new models"""
        registry_path = self.output_dir / "registry.json"
        
        registry = {
            'last_updated': datetime.now().isoformat(),
            'imputation_models': {},
            'prediction_models': {}
        }
        
        # Add imputation models
        for target, result in self.training_results['imputation_models'].items():
            if 'error' not in result:
                model_name = target.replace('.', '_')
                registry['imputation_models'][model_name] = {
                    'version': '1.0.0',
                    'trained_on': self.training_results['timestamp'],
                    'samples': result['performance'].get('samples', 0),
                    'performance': result['performance'],
                    'path': f"imputation/{model_name}_imputer.pkl"
                }
        
        # Add prediction models
        for model_type, result in self.training_results['prediction_models'].items():
            if 'error' not in result:
                registry['prediction_models'][model_type] = {
                    'version': '1.0.0',
                    'trained_on': self.training_results['timestamp'],
                    'performance': result['performance'],
                    'feature_count': result['feature_count'],
                    'path': f"prediction/{model_type}_predictor.pkl"
                }
        
        with open(registry_path, 'w') as f:
            json.dump(registry, f, indent=2)
        
        logger.info(f"✅ Model registry updated: {registry_path}")


# ============================================================================
# CLI
# ============================================================================

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Train ML models for Gravity Score",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train all models on multiple CSV files
  python train_models.py --data "scrapes/NFL/*/nfl_players_*.csv"
  
  # Train specific models only
  python train_models.py --data training_data.csv --models draft,contract
  
  # Specify output directory
  python train_models.py --data training_data.csv --output models_v2
        """
    )
    
    parser.add_argument(
        '--data',
        type=str,
        nargs='+',
        required=True,
        help='Data file paths (supports wildcards)'
    )
    
    parser.add_argument(
        '--models',
        type=str,
        default='all',
        help='Comma-separated list of models to train (draft,contract,performance,injury,market) or "all"'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='models',
        help='Output directory for trained models (default: models)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Parse models
    if args.models == 'all':
        models_to_train = None  # Train all
    else:
        models_to_train = [m.strip() for m in args.models.split(',')]
    
    # Run pipeline
    pipeline = ModelTrainingPipeline(output_dir=args.output)
    pipeline.run_full_pipeline(args.data, models_to_train=models_to_train)


if __name__ == '__main__':
    main()

