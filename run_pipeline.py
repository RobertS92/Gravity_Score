#!/usr/bin/env python3
"""
Gravity Score Pipeline Runner
==============================

Command-line tool to run the complete Gravity Score data pipeline:
1. Flatten nested player data
2. Impute missing values
3. Extract features
4. Calculate Gravity Scores

Usage:
    python run_pipeline.py input.csv output.csv
    python run_pipeline.py input.json output.json
    python run_pipeline.py --scrape cfb --output scores.csv  # disabled: use external scrapers + --input

Author: Gravity Score Team
"""

import sys
import os
import logging
import argparse
from datetime import datetime
import pandas as pd

# Add gravity module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gravity'))

from gravity.data_pipeline import GravityPipeline
from gravity.output_manager import OutputManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize output manager
output_manager = OutputManager()


def main():
    parser = argparse.ArgumentParser(
        description='Gravity Score Pipeline - Process player data and calculate Gravity Scores',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process existing CSV
  python run_pipeline.py players.csv output.csv
  
  # Process JSON data
  python run_pipeline.py data.json output.json
  
  # Keep more historical years (default: 3)
  python run_pipeline.py input.csv output.csv --max-years 5
  
  # Show top players by Gravity Score
  python run_pipeline.py input.csv output.csv --show-top 10
        """
    )
    
    parser.add_argument('input', nargs='?', help='Input file (CSV or JSON)')
    parser.add_argument('output', nargs='?', help='Output file (CSV or JSON) - positional argument')
    parser.add_argument('--output', dest='output_file', metavar='FILE',
                       help='Output file path (alternative to positional output argument)')
    parser.add_argument('--scrape', choices=['wnba', 'cfb', 'ncaab', 'wncaab'],
                       help='Disabled: use external scrapers repo; pass --input instead')
    parser.add_argument('--scrape-mode', default='test',
                       help='Scraping mode: test, team, all, player (default: test)')
    parser.add_argument('--max-years', type=int, default=3,
                       help='Maximum historical years to keep (default: 3)')
    parser.add_argument('--show-top', type=int, metavar='N',
                       help='Show top N players by Gravity Score')
    parser.add_argument('--filter-position', help='Filter by position (e.g., QB, WR)')
    parser.add_argument('--filter-team', help='Filter by team')
    parser.add_argument('--output-format', choices=['csv', 'json', 'excel'], default='csv',
                       help='Output format (default: csv)')
    
    args = parser.parse_args()
    
    # Use --output flag if provided, otherwise use positional output
    if args.output_file:
        args.output = args.output_file
    
    # Validate arguments
    if not args.scrape and not args.input:
        parser.error("Either provide input file or use --scrape option")
    
    if not args.output:
        # Generate output filename with auto-incrementing counter
        if args.scrape:
            # Determine file extension from output format
            ext = args.output_format if args.output_format else 'csv'
            args.output = output_manager.get_next_filename(args.scrape.upper(), ext)
            logger.info(f"📁 Auto-generated output path: {args.output}")
        else:
            parser.error("Output file is required when using input file")
    
    # ========================================================================
    # STEP 1: LOAD OR SCRAPE DATA
    # ========================================================================
    
    if args.scrape:
        logger.info(f"🏈 Scraping fresh {args.scrape.upper()} data...")
        input_data = scrape_data(args.scrape, args.scrape_mode)
        
        if not input_data:
            logger.error("❌ Scraping failed or returned no data")
            return 1
        
        logger.info(f"✅ Scraped {len(input_data)} players")
    else:
        logger.info(f"📂 Loading data from {args.input}...")
        
        if not os.path.exists(args.input):
            logger.error(f"❌ Input file not found: {args.input}")
            return 1
        
        input_data = args.input
    
    # ========================================================================
    # STEP 2: RUN PIPELINE
    # ========================================================================
    
    try:
        logger.info("🚀 Starting Gravity Score Pipeline...")
        
        pipeline = GravityPipeline(max_years=args.max_years)
        df = pipeline.process(input_data, output_format='dataframe')
        
        # Apply filters if specified
        if args.filter_position:
            position_col = 'position' if 'position' in df.columns else 'identity.position'
            if position_col in df.columns:
                original_count = len(df)
                df = df[df[position_col] == args.filter_position.upper()]
                logger.info(f"🔍 Filtered to {args.filter_position}: {len(df)}/{original_count} players")
        
        if args.filter_team:
            team_col = 'team' if 'team' in df.columns else 'identity.team'
            if team_col in df.columns:
                original_count = len(df)
                df = df[df[team_col].str.contains(args.filter_team, case=False, na=False)]
                logger.info(f"🔍 Filtered to {args.filter_team}: {len(df)}/{original_count} players")
        
        # ====================================================================
        # STEP 3: DISPLAY TOP PLAYERS
        # ====================================================================
        
        if args.show_top:
            logger.info(f"\n{'='*80}")
            logger.info(f"🏆 TOP {args.show_top} PLAYERS BY GRAVITY SCORE")
            logger.info(f"{'='*80}\n")
            
            top_players = df.nlargest(args.show_top, 'gravity_score')
            
            for i, (idx, player) in enumerate(top_players.iterrows(), 1):
                name = player.get('player_name', player.get('identity.name', 'Unknown'))
                position = player.get('position', player.get('identity.position', '?'))
                team = player.get('team', player.get('identity.team', '?'))
                score = player['gravity_score']
                tier = player['gravity_tier']
                percentile = player['gravity_percentile']
                
                logger.info(f"{i:2d}. {name:25s} {position:3s} {team:20s}")
                logger.info(f"    Gravity Score: {score:5.1f}/100  [{tier}]  (Top {100-percentile:.0f}%)")
                logger.info(f"    Performance: {player['gravity.performance_score']:4.1f} | "
                           f"Market: {player['gravity.market_score']:4.1f} | "
                           f"Social: {player['gravity.social_score']:4.1f} | "
                           f"Velocity: {player['gravity.velocity_score']:4.1f} | "
                           f"Risk: {player['gravity.risk_score']:4.1f}")
                logger.info("")
        
        # ====================================================================
        # STEP 4: SAVE OUTPUT
        # ====================================================================
        
        logger.info(f"💾 Saving results to {args.output}...")
        
        if args.output.endswith('.csv'):
            df.to_csv(args.output, index=False)
        elif args.output.endswith('.json'):
            df.to_json(args.output, orient='records', indent=2)
        elif args.output.endswith('.xlsx'):
            df.to_excel(args.output, index=False, engine='openpyxl')
        else:
            # Default to CSV
            df.to_csv(args.output, index=False)
        
        logger.info(f"✅ Pipeline complete!")
        logger.info(f"   📊 {len(df)} players processed")
        logger.info(f"   📈 Gravity Scores: {df['gravity_score'].min():.1f} - {df['gravity_score'].max():.1f}")
        logger.info(f"   🎯 Average Score: {df['gravity_score'].mean():.1f}")
        logger.info(f"   💾 Output: {args.output}")
        
        # Show tier distribution
        logger.info(f"\n📊 TIER DISTRIBUTION:")
        tier_counts = df['gravity_tier'].value_counts()
        for tier, count in tier_counts.items():
            pct = (count / len(df)) * 100
            logger.info(f"   {tier:12s}: {count:4d} players ({pct:5.1f}%)")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def scrape_data(sport: str, mode: str = 'test') -> list:
    """Scraping is not in this repo; use the external scrapers repository or pass a CSV/JSON file."""
    _ = mode
    logger.error(
        "run_pipeline --scrape is disabled here. Use external scrapers or --input file (%s).",
        sport,
    )
    return []


if __name__ == '__main__':
    sys.exit(main())

