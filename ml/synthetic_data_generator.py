#!/usr/bin/env python3
"""
Synthetic Data Generator for Gravity Score
==========================================
Generates 300K synthetic players (100K each sport) using CTGAN for training neural networks.
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List
import warnings
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from sdv.single_table import CTGANSynthesizer
    from sdv.metadata import SingleTableMetadata
    CTGAN_AVAILABLE = True
except ImportError:
    CTGAN_AVAILABLE = False
    logger.warning("⚠️  CTGAN not available. Install with: pip install sdv")


class SyntheticDataGenerator:
    """Generate synthetic player data using CTGAN"""
    
    def __init__(self, sport: str = 'nfl'):
        self.sport = sport
        self.synthesizer = None
        self.metadata = None
        
    def prepare_training_data(self, real_data_files: List[str]) -> pd.DataFrame:
        """
        Load and combine real player data from all scrapes
        
        Args:
            real_data_files: List of CSV file paths with real player data
            
        Returns:
            Combined DataFrame with all real players
        """
        logger.info(f"📂 Loading real {self.sport.upper()} data for training...")
        
        all_data = []
        for file_path in real_data_files:
            try:
                df = pd.read_csv(file_path)
                logger.info(f"   Loaded {len(df)} players from {Path(file_path).name}")
                all_data.append(df)
            except FileNotFoundError:
                logger.warning(f"   ⚠️  File not found: {file_path}")
        
        if not all_data:
            raise ValueError("No real data files found!")
        
        # Combine all data
        combined = pd.concat(all_data, ignore_index=True)
        logger.info(f"✅ Combined {len(combined)} total {self.sport.upper()} players")
        
        # Select relevant columns for training (numeric + categorical)
        numeric_cols = combined.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = combined.select_dtypes(include=['object']).columns.tolist()
        
        # Remove columns with too many unique values (like player_name)
        categorical_cols = [c for c in categorical_cols if combined[c].nunique() < 100]
        
        # Combine
        training_cols = numeric_cols + categorical_cols[:20]  # Limit categorical to top 20
        training_data = combined[training_cols].copy()
        
        logger.info(f"   Using {len(training_cols)} features for training")
        
        return training_data
    
    def train_synthesizer(self, training_data: pd.DataFrame, epochs: int = 3):
        """
        Train CTGAN synthesizer on real data
        
        Args:
            training_data: DataFrame with real player data
            epochs: Number of training epochs
        """
        if not CTGAN_AVAILABLE:
            raise ImportError("CTGAN not available. Install with: pip install sdv")
        
        logger.info(f"🎓 Training CTGAN synthesizer for {self.sport.upper()}...")
        logger.info(f"   Training data: {len(training_data)} players, {len(training_data.columns)} features")
        
        # Create metadata
        self.metadata = SingleTableMetadata()
        self.metadata.detect_from_dataframe(training_data)
        
        # Create synthesizer
        self.synthesizer = CTGANSynthesizer(
            metadata=self.metadata,
            epochs=epochs,
            verbose=True
        )
        
        # Train
        self.synthesizer.fit(training_data)
        
        logger.info(f"✅ Synthesizer trained successfully")
    
    def generate_players(self, num_players: int, constraints: Dict = None) -> pd.DataFrame:
        """
        Generate synthetic players
        
        Args:
            num_players: Number of synthetic players to generate
            constraints: Optional constraints to apply (age ranges, etc.)
            
        Returns:
            DataFrame with synthetic player data
        """
        if not self.synthesizer:
            raise ValueError("Synthesizer not trained! Call train_synthesizer() first.")
        
        logger.info(f"🎲 Generating {num_players:,} synthetic {self.sport.upper()} players...")
        
        # Generate synthetic data
        synthetic_data = self.synthesizer.sample(num_rows=num_players)
        
        logger.info(f"✅ Generated {len(synthetic_data)} synthetic players")
        
        # Apply constraints if provided
        if constraints:
            synthetic_data = self._apply_constraints(synthetic_data, constraints)
        
        return synthetic_data
    
    def _apply_constraints(self, df: pd.DataFrame, constraints: Dict) -> pd.DataFrame:
        """Apply sport-specific constraints to synthetic data"""
        logger.info("🔧 Applying constraints...")
        
        # Age constraints
        if 'age_min' in constraints and 'age_max' in constraints:
            if 'age' in df.columns:
                df = df[(df['age'] >= constraints['age_min']) & (df['age'] <= constraints['age_max'])]
                logger.info(f"   Applied age constraint: {constraints['age_min']}-{constraints['age_max']}")
        
        # Position constraints (if needed)
        if 'positions' in constraints and 'position' in df.columns:
            df = df[df['position'].isin(constraints['positions'])]
            logger.info(f"   Applied position constraint: {len(constraints['positions'])} positions")
        
        return df
    
    def save_synthetic_data(self, synthetic_data: pd.DataFrame, output_file: str):
        """Save synthetic data to CSV"""
        synthetic_data.to_csv(output_file, index=False)
        logger.info(f"💾 Saved synthetic data to {output_file}")


def generate_synthetic_players(sport: str, num_players: int, real_data_files: List[str], 
                                output_file: str, constraints: Dict = None):
    """
    Complete workflow: Load real data, train synthesizer, generate synthetic players
    
    Args:
        sport: 'nfl', 'nba', or 'cfb'
        num_players: Number of synthetic players to generate
        real_data_files: List of CSV files with real player data
        output_file: Output CSV path
        constraints: Optional constraints dict
    """
    print(f"\n{'='*100}")
    print(f"🎲 GENERATING {num_players:,} SYNTHETIC {sport.upper()} PLAYERS")
    print(f"{'='*100}\n")
    
    generator = SyntheticDataGenerator(sport=sport)
    
    # Load real data
    training_data = generator.prepare_training_data(real_data_files)
    
    # Train synthesizer
    generator.train_synthesizer(training_data, epochs=3)
    
    # Generate synthetic players
    synthetic_data = generator.generate_players(num_players, constraints)
    
    # Save
    generator.save_synthetic_data(synthetic_data, output_file)
    
    print(f"\n{'='*100}")
    print(f"✅ SYNTHETIC DATA GENERATION COMPLETE!")
    print(f"{'='*100}\n")
    print(f"📊 Summary:")
    print(f"   Sport: {sport.upper()}")
    print(f"   Real training data: {len(training_data):,} players")
    print(f"   Synthetic players generated: {len(synthetic_data):,}")
    print(f"   Output: {output_file}")
    print(f"{'='*100}\n")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 4:
        print("Usage: python synthetic_data_generator.py sport num_players output.csv [real_data1.csv] [real_data2.csv] ...")
        sys.exit(1)
    
    sport = sys.argv[1]
    num_players = int(sys.argv[2])
    output_file = sys.argv[3]
    real_data_files = sys.argv[4:] if len(sys.argv) > 4 else []
    
    # Default constraints by sport
    constraints = {
        'nfl': {'age_min': 20, 'age_max': 35},
        'nba': {'age_min': 19, 'age_max': 35},
        'cfb': {'age_min': 18, 'age_max': 23}
    }
    
    generate_synthetic_players(sport, num_players, real_data_files, output_file, 
                              constraints.get(sport))

