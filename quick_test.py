#!/usr/bin/env python3
"""
Quick test of NFL Gravity Pipeline - Just roster scraping
"""

from nfl_gravity_pipeline import NFLGravityPipeline
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def quick_test():
    """Quick test showing basic functionality."""
    print("🏈 NFL Gravity Pipeline - Quick Demo")
    print("=" * 50)
    
    # Initialize pipeline
    pipeline = NFLGravityPipeline()
    
    # Test with just one team
    print("Testing roster scraping for Arizona Cardinals...")
    
    try:
        df = pipeline.scrape_team_roster("arizona-cardinals")
        
        print(f"\n✅ Successfully scraped {len(df)} players")
        
        if not df.empty:
            print("\n📋 Sample player data:")
            print(df[['Player', 'Team_Full', 'Jersey']].head(10))
            
            print(f"\n📊 Total columns available: {len(df.columns)}")
            print(f"Columns: {list(df.columns)}")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logging.error(f"Test failed: {e}")

if __name__ == "__main__":
    quick_test()