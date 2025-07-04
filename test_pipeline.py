#!/usr/bin/env python3
"""
Test script for NFL Gravity Pipeline
"""

from nfl_gravity_pipeline import NFLGravityPipeline
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_pipeline():
    """Test the NFL Gravity pipeline with a small sample."""
    print("🏈 NFL Gravity Pipeline - Test Mode")
    print("=" * 50)
    
    # Initialize pipeline
    pipeline = NFLGravityPipeline()
    
    # Test with just 3 players
    print("Testing with 3 players...")
    
    try:
        df = pipeline.run_pipeline(max_players=3)
        
        print(f"\n✅ Test completed successfully!")
        print(f"📊 Processed {len(df)} players")
        
        if not df.empty:
            print("\n📋 Sample of collected data:")
            print(df[['Player', 'Team_Full', 'Position', 'Age', 'News_Headlines_Count']].head())
            
            print("\n📊 Column summary:")
            print(f"Total columns: {len(df.columns)}")
            print(f"Non-null values per column:")
            for col in df.columns:
                non_null = df[col].notna().sum()
                print(f"  {col}: {non_null}/{len(df)}")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logging.error(f"Test failed: {e}")

if __name__ == "__main__":
    test_pipeline()