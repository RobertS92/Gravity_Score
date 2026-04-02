#!/usr/bin/env python3
"""
Score All Sports - Commercial Value
====================================

Runs the commercial value gravity score formula on college (and optional custom CSV) data.

Usage:
    python score_all_sports.py

Author: Gravity Score Team
"""

import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from gravity.data_pipeline import GravityScoreCalculator, DataImputer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def score_sport_data(input_file: str, output_file: str, sport_name: str):
    """
    Score a single sport's data
    
    Args:
        input_file: Input CSV path
        output_file: Output CSV path
        sport_name: Sport name for logging
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"🏆 SCORING {sport_name.upper()}")
    logger.info(f"{'='*80}")
    
    try:
        # Load data
        df = pd.read_csv(input_file)
        logger.info(f"  Loaded {len(df)} players")
        
        # Apply imputation (fills missing values)
        logger.info(f"  Imputing missing values...")
        imputer = DataImputer()
        df = imputer.impute_data(df)
        
        # Calculate commercial value scores
        logger.info(f"  Calculating commercial value scores...")
        calculator = GravityScoreCalculator()
        df = calculator.calculate_gravity_scores(df)
        
        # Create output directory
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save results
        df.to_csv(output_file, index=False)
        
        # Summary stats
        score_range = (df['gravity_score'].min(), df['gravity_score'].max())
        avg_score = df['gravity_score'].mean()
        
        logger.info(f"\n  ✅ {sport_name} Scoring Complete!")
        logger.info(f"     Players scored: {len(df)}")
        logger.info(f"     Score range: {score_range[0]:.1f} to {score_range[1]:.1f}")
        logger.info(f"     Average score: {avg_score:.1f}")
        logger.info(f"     Output: {output_file}")
        
        # Show top 5
        logger.info(f"\n  🏆 Top 5 {sport_name} Players by Commercial Value:")
        top5 = df.nlargest(5, 'gravity_score')[['player_name', 'position', 'team', 'gravity_score', 'gravity_tier']]
        for i, (idx, row) in enumerate(top5.iterrows(), 1):
            logger.info(f"     {i}. {row['player_name']:25s} ({row['position']:3s}) - {row['gravity_score']:.1f}")
        
        return True
        
    except Exception as e:
        logger.error(f"  ❌ Failed to score {sport_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main execution"""
    import sys
    
    print("\n" + "="*80)
    print("🚀 COMMERCIAL VALUE SCORING - ALL SPORTS")
    print("="*80)
    print("\nScoring college/player CSVs with the commercial value formula:")
    print("  • Performance (20%): Current season priority")
    print("  • Market (25%): Endorsement-heavy")
    print("  • Social (30%): Celebrity effect included")
    print("  • Velocity (15%): Growth trajectory")
    print("  • Risk (10%): Severity-scaled scandals")
    print("\n" + "="*80)
    
    # Check for command-line arguments (single sport mode)
    if len(sys.argv) >= 3:
        # Single sport mode: python score_all_sports.py input.csv output.csv sport
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        sport_name = sys.argv[3] if len(sys.argv) > 3 else 'NFL'
        
        success = score_sport_data(input_file, output_file, sport_name)
        return
    
    # Default: college data only (adjust paths to your latest scrapes)
    sports_data = [
        {
            'name': 'CFB',
            'input': 'scrapes/CFB/20251203_233730/cfb_power5_players_20251204_193153.csv',
            'output': 'final_scores/CFB_Commercial_Value_Final.csv',
        },
    ]
    
    # Process each sport
    results = {}
    for sport in sports_data:
        success = score_sport_data(sport['input'], sport['output'], sport['name'])
        results[sport['name']] = success
    
    # Final summary
    print("\n" + "="*80)
    print("📊 FINAL SUMMARY")
    print("="*80)
    
    for sport_name, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {sport_name}: {'Complete' if success else 'Failed'}")
    
    if all(results.values()):
        print("\n🎉 ALL SPORTS SCORED SUCCESSFULLY!")
        print("\nFinal datasets saved to final_scores/ directory:")
        for sport in sports_data:
            print(f"  • {sport['output']}")
    
    print("="*80)


if __name__ == '__main__':
    main()

