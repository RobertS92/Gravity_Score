#!/usr/bin/env python3
"""
Example: Gravity Score Pipeline Usage
======================================

Quick examples showing how to use the Gravity Score pipeline.
"""

import sys
import os

# Add gravity to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gravity'))

from gravity.data_pipeline import GravityPipeline
import pandas as pd


def example_1_process_csv():
    """Example 1: Process existing CSV file"""
    print("\n" + "="*80)
    print("EXAMPLE 1: Process Existing CSV")
    print("="*80 + "\n")
    
    # Initialize pipeline
    pipeline = GravityPipeline(max_years=3)
    
    # Process CSV file
    input_file = 'scrapes/nfl_players.csv'  # Your CSV file
    
    if os.path.exists(input_file):
        df = pipeline.process(input_file, output_format='dataframe')
        
        # Show results
        print(f"✅ Processed {len(df)} players")
        print(f"   Top Score: {df['gravity_score'].max():.1f}")
        print(f"   Avg Score: {df['gravity_score'].mean():.1f}")
        
        # Save output
        df.to_csv('output_with_gravity_scores.csv', index=False)
        print(f"   Saved to: output_with_gravity_scores.csv")
    else:
        print(f"⚠️  File not found: {input_file}")
        print("   Run a scraper first to generate player data")


def example_2_show_top_players():
    """Example 2: Show top players by Gravity Score"""
    print("\n" + "="*80)
    print("EXAMPLE 2: Show Top 10 Players")
    print("="*80 + "\n")
    
    # Load processed data
    if os.path.exists('output_with_gravity_scores.csv'):
        df = pd.read_csv('output_with_gravity_scores.csv')
        
        # Get top 10
        top_10 = df.nlargest(10, 'gravity_score')
        
        print(f"🏆 TOP 10 PLAYERS BY GRAVITY SCORE\n")
        
        for i, (_, player) in enumerate(top_10.iterrows(), 1):
            name = player.get('player_name', player.get('identity.name', 'Unknown'))
            position = player.get('position', player.get('identity.position', '?'))
            team = player.get('team', player.get('identity.team', '?'))
            score = player['gravity_score']
            tier = player['gravity_tier']
            
            print(f"{i:2d}. {name:25s} {position:3s} {team:20s}")
            print(f"    Gravity: {score:5.1f}/100  [{tier}]")
            print(f"    Performance: {player['gravity.performance_score']:4.1f} | "
                  f"Market: {player['gravity.market_score']:4.1f} | "
                  f"Social: {player['gravity.social_score']:4.1f}")
            print()
    else:
        print("⚠️  No processed data found. Run Example 1 first.")


def example_3_filter_by_position():
    """Example 3: Filter and analyze by position"""
    print("\n" + "="*80)
    print("EXAMPLE 3: Analyze Quarterbacks Only")
    print("="*80 + "\n")
    
    if os.path.exists('output_with_gravity_scores.csv'):
        df = pd.read_csv('output_with_gravity_scores.csv')
        
        # Filter to QBs
        position_col = 'position' if 'position' in df.columns else 'identity.position'
        qbs = df[df[position_col] == 'QB']
        
        print(f"📊 Quarterback Analysis ({len(qbs)} QBs)\n")
        
        # Top 5 QBs
        top_qbs = qbs.nlargest(5, 'gravity_score')
        
        print("Top 5 QBs by Gravity Score:")
        for i, (_, player) in enumerate(top_qbs.iterrows(), 1):
            name = player.get('player_name', player.get('identity.name', 'Unknown'))
            score = player['gravity_score']
            print(f"  {i}. {name:25s} - {score:5.1f}")
        
        # Stats
        print(f"\nQB Stats:")
        print(f"  Avg Gravity Score: {qbs['gravity_score'].mean():.1f}")
        print(f"  Median: {qbs['gravity_score'].median():.1f}")
        print(f"  Top Score: {qbs['gravity_score'].max():.1f}")
        
        # Tier distribution
        print(f"\nTier Distribution:")
        tier_counts = qbs['gravity_tier'].value_counts()
        for tier, count in tier_counts.items():
            print(f"  {tier:12s}: {count:3d} players")
    else:
        print("⚠️  No processed data found. Run Example 1 first.")


def example_4_scrape_and_process():
    """Example 4: Scrape fresh data and process"""
    print("\n" + "="*80)
    print("EXAMPLE 4: Scrape Fresh NFL Data & Calculate Scores")
    print("="*80 + "\n")
    
    print("This would normally scrape fresh data...")
    print("Run: python run_pipeline.py --scrape nfl --output scores.csv")
    print("\nFor this example, we'll use existing data if available.")
    
    # Check if we have existing data
    csv_files = [f for f in os.listdir('.') if f.endswith('_players.csv')]
    
    if csv_files:
        latest = csv_files[0]
        print(f"\n✅ Found: {latest}")
        print(f"   Processing...")
        
        pipeline = GravityPipeline(max_years=3)
        df = pipeline.process(latest, output_format='dataframe')
        
        print(f"✅ Complete!")
        print(f"   {len(df)} players scored")
    else:
        print("\n⚠️  No player CSV files found.")
        print("   Run a scraper first:")
        print("   python3 gravity/nfl_scraper.py test")


def example_5_compare_teams():
    """Example 5: Compare two teams"""
    print("\n" + "="*80)
    print("EXAMPLE 5: Compare Teams (Chiefs vs 49ers)")
    print("="*80 + "\n")
    
    if os.path.exists('output_with_gravity_scores.csv'):
        df = pd.read_csv('output_with_gravity_scores.csv')
        
        team_col = 'team' if 'team' in df.columns else 'identity.team'
        
        # Filter teams
        chiefs = df[df[team_col].str.contains('Chiefs', case=False, na=False)]
        niners = df[df[team_col].str.contains('49ers|Forty', case=False, na=False)]
        
        print("📊 Team Comparison\n")
        print(f"Kansas City Chiefs:")
        print(f"  Players: {len(chiefs)}")
        print(f"  Avg Gravity Score: {chiefs['gravity_score'].mean():.1f}")
        print(f"  Top Player: {chiefs.nlargest(1, 'gravity_score')['player_name'].iloc[0] if len(chiefs) > 0 else 'N/A'}")
        
        print(f"\nSan Francisco 49ers:")
        print(f"  Players: {len(niners)}")
        print(f"  Avg Gravity Score: {niners['gravity_score'].mean():.1f}")
        print(f"  Top Player: {niners.nlargest(1, 'gravity_score')['player_name'].iloc[0] if len(niners) > 0 else 'N/A'}")
        
        if len(chiefs) > 0 and len(niners) > 0:
            winner = "Chiefs" if chiefs['gravity_score'].mean() > niners['gravity_score'].mean() else "49ers"
            print(f"\n🏆 Higher avg Gravity Score: {winner}")
    else:
        print("⚠️  No processed data found. Run Example 1 first.")


def main():
    """Run all examples"""
    print("\n" + "="*80)
    print("  GRAVITY SCORE PIPELINE - USAGE EXAMPLES")
    print("="*80)
    
    # Run examples
    example_1_process_csv()
    example_2_show_top_players()
    example_3_filter_by_position()
    example_4_scrape_and_process()
    example_5_compare_teams()
    
    print("\n" + "="*80)
    print("  ✅ EXAMPLES COMPLETE")
    print("="*80 + "\n")
    
    print("Next Steps:")
    print("  1. Run: python run_pipeline.py --scrape nfl --output scores.csv")
    print("  2. Open scores.csv in Excel/Sheets")
    print("  3. Sort by 'gravity_score' column")
    print("  4. Analyze by 'gravity_tier' (Superstar, Elite, Impact, etc.)")
    print("\nFor help: python run_pipeline.py --help\n")


if __name__ == '__main__':
    main()

