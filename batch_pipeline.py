#!/usr/bin/env python3
"""
Batch ML Pipeline
=================

Process CSV files in batch mode with ML imputation and predictions:
1. Load player data from CSV
2. Flatten nested structures
3. Apply ML imputation
4. Engineer features
5. Run ML predictions
6. Calculate rule-based gravity score
7. Ensemble ML + rule-based scores
8. Export scored results

Usage:
    python batch_pipeline.py input.csv output.csv
    python batch_pipeline.py "scrapes/NFL/latest/*.csv" scored/
    python batch_pipeline.py input.csv output.csv --impute --predict --ensemble

Author: Gravity Score Team
"""

import argparse
import logging
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
import glob
from datetime import datetime
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from gravity.data_pipeline import DataFlattener, DataImputer, FeatureExtractor, GravityScoreCalculator
from gravity.ml_imputer import MLImputer
from gravity.ml_models import ModelFactory
from gravity.ml_feature_engineering import MLFeatureEngineer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# BATCH PIPELINE
# ============================================================================

class BatchMLPipeline:
    """
    Batch processing pipeline with ML integration
    """
    
    def __init__(
        self, 
        use_ml_imputation: bool = True,
        use_ml_predictions: bool = True,
        use_ensemble: bool = True,
        models_dir: str = "models"
    ):
        """
        Initialize batch pipeline
        
        Args:
            use_ml_imputation: Use ML-based imputation
            use_ml_predictions: Generate ML predictions
            use_ensemble: Combine ML predictions with rule-based score
            models_dir: Directory containing trained models
        """
        self.use_ml_imputation = use_ml_imputation
        self.use_ml_predictions = use_ml_predictions
        self.use_ensemble = use_ensemble
        self.models_dir = Path(models_dir)
        
        # Initialize components
        self.flattener = DataFlattener()
        self.rule_based_imputer = DataImputer()
        self.feature_extractor = FeatureExtractor()
        self.gravity_calculator = GravityScoreCalculator()
        
        # ML components
        self.ml_imputer = None
        self.ml_feature_engineer = None
        self.prediction_models = {}
        
        # Load ML models if available
        if self.use_ml_imputation or self.use_ml_predictions:
            self._load_ml_models()
    
    def _load_ml_models(self):
        """Load trained ML models"""
        logger.info("🤖 Loading ML models...")
        
        # Load imputation models
        if self.use_ml_imputation:
            imputation_dir = self.models_dir / "imputation"
            if imputation_dir.exists():
                try:
                    self.ml_imputer = MLImputer(models_dir=str(imputation_dir))
                    self.ml_imputer.load_models()
                    logger.info(f"  ✅ Loaded {len(self.ml_imputer.trained_models)} imputation models")
                except Exception as e:
                    logger.warning(f"  ⚠️  Failed to load imputation models: {e}")
                    self.ml_imputer = None
            else:
                logger.warning(f"  ⚠️  Imputation models directory not found: {imputation_dir}")
                self.ml_imputer = None
        
        # Load prediction models
        if self.use_ml_predictions:
            prediction_dir = self.models_dir / "prediction"
            if prediction_dir.exists():
                try:
                    self.prediction_models = ModelFactory.load_all_models(str(prediction_dir))
                    logger.info(f"  ✅ Loaded {len(self.prediction_models)} prediction models")
                except Exception as e:
                    logger.warning(f"  ⚠️  Failed to load prediction models: {e}")
            else:
                logger.warning(f"  ⚠️  Prediction models directory not found: {prediction_dir}")
        
        # Initialize feature engineer
        if self.use_ml_predictions or self.use_ml_imputation:
            self.ml_feature_engineer = MLFeatureEngineer()
    
    def process_file(self, input_path: str, output_path: str):
        """
        Process a single CSV file
        
        Args:
            input_path: Input CSV file path
            output_path: Output CSV file path
        """
        logger.info("=" * 80)
        logger.info(f"📂 Processing: {input_path}")
        logger.info("=" * 80)
        
        # Load data
        df = pd.read_csv(input_path)
        logger.info(f"Loaded {len(df)} players")
        
        # Process
        df_scored = self.process_dataframe(df)
        
        # Save
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        df_scored.to_csv(output_file, index=False)
        
        logger.info(f"✅ Saved {len(df_scored)} scored players to {output_file}")
        
        return df_scored
    
    def process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process DataFrame through full pipeline
        
        Args:
            df: Input DataFrame
            
        Returns:
            Scored DataFrame with ML predictions and gravity scores
        """
        logger.info("\n🔄 PIPELINE STEPS:")
        
        # 1. Flatten nested structures
        logger.info("\n1️⃣  Flattening data...")
        df = self._flatten_if_needed(df)
        
        # 2. Impute missing values
        logger.info("\n2️⃣  Imputing missing values...")
        if self.use_ml_imputation and self.ml_imputer:
            logger.info("   Using ML imputation")
            df = self.ml_imputer.impute_dataframe(df, use_ml=True)
        else:
            logger.info("   Using rule-based imputation")
            df = self.rule_based_imputer.impute_data(df)
        
        # 3. Engineer features
        logger.info("\n3️⃣  Engineering features...")
        if self.ml_feature_engineer:
            df = self.ml_feature_engineer.engineer_features(df, include_all=True)
        
        # Extract standard features for gravity score
        df = self.feature_extractor.extract_features(df)
        
        # 4. ML Predictions
        if self.use_ml_predictions and self.prediction_models:
            logger.info("\n4️⃣  Running ML predictions...")
            df = self._run_ml_predictions(df)
        
        # 5. Calculate rule-based gravity score
        logger.info("\n5️⃣  Calculating gravity scores...")
        df = self.gravity_calculator.calculate_gravity_scores(df)
        
        # 6. Ensemble scoring
        if self.use_ensemble and self.use_ml_predictions and 'ml_market_value' in df.columns:
            logger.info("\n6️⃣  Creating ensemble score...")
            df = self._create_ensemble_score(df)
        
        logger.info("\n✅ Pipeline complete!")
        
        return df
    
    def _flatten_if_needed(self, df: pd.DataFrame) -> pd.DataFrame:
        """Flatten data if it contains nested structures"""
        # Check if data has nested JSON columns
        nested_cols = ['identity', 'brand', 'proof', 'proximity', 'velocity', 'risk']
        has_nested = any(col in df.columns for col in nested_cols)
        
        if has_nested:
            # Parse JSON columns
            for col in nested_cols:
                if col in df.columns and df[col].dtype == 'object':
                    try:
                        df[col] = df[col].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
                    except:
                        pass
            
            # Flatten
            flattened_rows = []
            for _, row in df.iterrows():
                flat_row = self.flattener.flatten_player_data(row.to_dict())
                flattened_rows.append(flat_row)
            
            df = pd.DataFrame(flattened_rows)
            logger.info(f"   Flattened to {len(df.columns)} columns")
        else:
            logger.info("   Data already flat")
        
        return df
    
    def _run_ml_predictions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run all ML prediction models"""
        
        for model_type, model in self.prediction_models.items():
            try:
                logger.info(f"   Running {model_type} predictor...")
                
                # Generate predictions
                predictions = model.predict(df)
                
                # Add to DataFrame
                col_name = f"ml_{model_type}_prediction"
                df[col_name] = predictions
                
                # Add confidence scores if available
                if hasattr(model, 'predict_proba'):
                    try:
                        probas = model.predict_proba(df)
                        confidence = np.max(probas, axis=1)
                        df[f"ml_{model_type}_confidence"] = confidence
                    except:
                        pass
                
                logger.info(f"     ✅ {model_type} predictions added")
                
            except Exception as e:
                logger.warning(f"     ⚠️  {model_type} prediction failed: {e}")
        
        # Special handling for market value predictor
        if 'market' in self.prediction_models:
            df['ml_market_value'] = df.get('ml_market_prediction', df.get('gravity_score', 0))
        
        return df
    
    def _create_ensemble_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create ensemble score combining ML predictions and rule-based score
        
        Strategy:
        - Weight ML predictions (60%) and rule-based score (40%)
        - Adjust weights based on data quality and model confidence
        """
        logger.info("   Creating weighted ensemble...")
        
        # Get scores
        ml_score = df.get('ml_market_value', df.get('ml_market_prediction', 0))
        rule_score = df.get('gravity_score', 0)
        
        # Base weights
        ml_weight = 0.6
        rule_weight = 0.4
        
        # Adjust based on confidence if available
        if 'ml_market_confidence' in df.columns:
            confidence = df['ml_market_confidence']
            # Higher confidence -> higher ML weight
            ml_weight = 0.4 + (confidence * 0.4)  # Range: 0.4 to 0.8
            rule_weight = 1.0 - ml_weight
        
        # Calculate ensemble
        df['ensemble_score'] = (ml_score * ml_weight) + (rule_score * rule_weight)
        
        # Normalize to 0-100 range
        if df['ensemble_score'].max() > 0:
            df['ensemble_score'] = (df['ensemble_score'] / df['ensemble_score'].max()) * 100
        
        logger.info(f"     ML weight: {ml_weight:.2f}, Rule weight: {rule_weight:.2f}")
        
        return df
    
    def process_multiple_files(
        self, 
        input_patterns: List[str], 
        output_dir: str,
        combine: bool = False
    ):
        """
        Process multiple files
        
        Args:
            input_patterns: List of file patterns (supports wildcards)
            output_dir: Output directory
            combine: If True, combine all outputs into single file
        """
        # Find all matching files
        all_files = []
        for pattern in input_patterns:
            files = glob.glob(pattern)
            all_files.extend(files)
        
        if not all_files:
            raise ValueError(f"No files found matching patterns: {input_patterns}")
        
        logger.info(f"Found {len(all_files)} files to process")
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        processed_dfs = []
        
        for i, input_file in enumerate(all_files, 1):
            logger.info(f"\n{'=' * 80}")
            logger.info(f"Processing file {i}/{len(all_files)}: {Path(input_file).name}")
            logger.info('=' * 80)
            
            try:
                # Process file
                df = pd.read_csv(input_file)
                df_scored = self.process_dataframe(df)
                
                if combine:
                    processed_dfs.append(df_scored)
                else:
                    # Save individual file
                    output_file = output_path / f"scored_{Path(input_file).name}"
                    df_scored.to_csv(output_file, index=False)
                    logger.info(f"✅ Saved to {output_file}")
                
            except Exception as e:
                logger.error(f"❌ Failed to process {input_file}: {e}")
        
        # Combine if requested
        if combine and processed_dfs:
            logger.info(f"\n{'=' * 80}")
            logger.info("Combining all results...")
            logger.info('=' * 80)
            
            combined = pd.concat(processed_dfs, ignore_index=True)
            
            # Remove duplicates
            if 'player_name' in combined.columns:
                combined = combined.drop_duplicates(subset=['player_name'], keep='last')
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = output_path / f"scored_combined_{timestamp}.csv"
            combined.to_csv(output_file, index=False)
            
            logger.info(f"✅ Combined {len(combined)} players saved to {output_file}")
        
        logger.info(f"\n{'=' * 80}")
        logger.info(f"✅ BATCH PROCESSING COMPLETE")
        logger.info('=' * 80)


# ============================================================================
# CLI
# ============================================================================

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Batch ML Pipeline for Gravity Score",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process single file
  python batch_pipeline.py input.csv output.csv
  
  # Process multiple files (wildcard)
  python batch_pipeline.py "scrapes/NFL/*/nfl_players_*.csv" scored/
  
  # Process with ML imputation and predictions
  python batch_pipeline.py input.csv output.csv --impute --predict --ensemble
  
  # Process multiple files and combine results
  python batch_pipeline.py "scrapes/NFL/*/nfl_players_*.csv" scored/ --combine
  
  # Use only rule-based scoring (no ML)
  python batch_pipeline.py input.csv output.csv --no-impute --no-predict
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        nargs='+',
        help='Input CSV file(s) or pattern(s)'
    )
    
    parser.add_argument(
        'output',
        type=str,
        help='Output CSV file or directory'
    )
    
    parser.add_argument(
        '--impute',
        dest='use_ml_imputation',
        action='store_true',
        default=True,
        help='Use ML imputation (default: True)'
    )
    
    parser.add_argument(
        '--no-impute',
        dest='use_ml_imputation',
        action='store_false',
        help='Use only rule-based imputation'
    )
    
    parser.add_argument(
        '--predict',
        dest='use_ml_predictions',
        action='store_true',
        default=True,
        help='Run ML predictions (default: True)'
    )
    
    parser.add_argument(
        '--no-predict',
        dest='use_ml_predictions',
        action='store_false',
        help='Skip ML predictions'
    )
    
    parser.add_argument(
        '--ensemble',
        dest='use_ensemble',
        action='store_true',
        default=True,
        help='Create ensemble score (default: True)'
    )
    
    parser.add_argument(
        '--no-ensemble',
        dest='use_ensemble',
        action='store_false',
        help='Skip ensemble scoring'
    )
    
    parser.add_argument(
        '--models-dir',
        type=str,
        default='models',
        help='Directory containing trained models (default: models)'
    )
    
    parser.add_argument(
        '--combine',
        action='store_true',
        help='Combine multiple input files into single output'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize pipeline
    pipeline = BatchMLPipeline(
        use_ml_imputation=args.use_ml_imputation,
        use_ml_predictions=args.use_ml_predictions,
        use_ensemble=args.use_ensemble,
        models_dir=args.models_dir
    )
    
    # Process files
    if len(args.input) == 1 and not '*' in args.input[0]:
        # Single file
        pipeline.process_file(args.input[0], args.output)
    else:
        # Multiple files
        pipeline.process_multiple_files(
            args.input,
            args.output,
            combine=args.combine
        )


if __name__ == '__main__':
    main()

