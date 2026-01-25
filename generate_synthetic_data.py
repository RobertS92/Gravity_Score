#!/usr/bin/env python3
"""
Generate Synthetic Data for All Sports
======================================
Generates 300K synthetic players (100K each) using CTGAN
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import synthetic data generator
from ml.synthetic_data_generator import generate_synthetic_players

def main():
    print("\n" + "="*100)
    print("🎲 GENERATING SYNTHETIC DATA FOR ALL SPORTS")
    print("="*100 + "\n")
    
    # Define real data files for each sport
    sports_config = {
        'nfl': {
            'real_data_files': [
                'final_scores/NFL_COMPLETE_FIXED.csv',
                'scrapes/NFL/20251209_113136/nfl_players_20251209_123629.csv'
            ],
            'num_players': 100000,
            'output': 'synthetic_data/nfl_synthetic_100k.csv',
            'constraints': {'age_min': 20, 'age_max': 35}
        },
        'nba': {
            'real_data_files': [
                'final_scores/NBA_COMPLETE.csv',
                'scrapes/NBA/20251203_214612/nba_players_20251203_231046.csv'
            ],
            'num_players': 100000,
            'output': 'synthetic_data/nba_synthetic_100k.csv',
            'constraints': {'age_min': 19, 'age_max': 35}
        },
        'cfb': {
            'real_data_files': [
                'final_scores/CFB_COMPLETE.csv',
                'scrapes/CFB/20251203_233730/cfb_power5_players_20251204_193153.csv'
            ],
            'num_players': 100000,
            'output': 'synthetic_data/cfb_synthetic_100k.csv',
            'constraints': {'age_min': 18, 'age_max': 23}
        }
    }
    
    # Create output directory
    Path('synthetic_data').mkdir(exist_ok=True)
    
    # Generate for each sport
    for sport, config in sports_config.items():
        logger.info(f"\n{'='*100}")
        logger.info(f"🎲 GENERATING {config['num_players']:,} SYNTHETIC {sport.upper()} PLAYERS")
        logger.info(f"{'='*100}\n")
        
        # Filter real data files that exist
        existing_files = [f for f in config['real_data_files'] if Path(f).exists()]
        
        if not existing_files:
            logger.warning(f"⚠️  No real data files found for {sport}. Skipping...")
            continue
        
        try:
            generate_synthetic_players(
                sport=sport,
                num_players=config['num_players'],
                real_data_files=existing_files,
                output_file=config['output'],
                constraints=config['constraints']
            )
            logger.info(f"✅ {sport.upper()} synthetic data generation complete!")
        except Exception as e:
            logger.error(f"❌ Failed to generate {sport} synthetic data: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*100)
    print("✅ SYNTHETIC DATA GENERATION COMPLETE!")
    print("="*100 + "\n")
    print("📁 Generated files:")
    for sport, config in sports_config.items():
        if Path(config['output']).exists():
            print(f"   • {config['output']} ({config['num_players']:,} players)")
    print("="*100 + "\n")


if __name__ == '__main__':
    main()

