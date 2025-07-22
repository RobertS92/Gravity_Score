#!/usr/bin/env python3
"""
Start All Teams Comprehensive Scraping
Launch comprehensive data collection for all 32 NFL teams
"""

import sys
import logging
from enhanced_scraping_system import enhanced_scraping_system
import pandas as pd
from datetime import datetime
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Start comprehensive scraping for all NFL teams."""
    
    # All 32 NFL teams
    all_teams = [
        'cardinals', 'falcons', 'ravens', 'bills', 'panthers', 'bears', 
        'bengals', 'browns', 'cowboys', 'broncos', 'lions', 'packers', 
        'texans', 'colts', 'jaguars', 'chiefs', 'raiders', 'chargers', 
        'rams', 'dolphins', 'vikings', 'patriots', 'saints', 'giants', 
        'jets', '49ers', 'seahawks', 'steelers', 'titans', 'commanders', 
        'buccaneers', 'eagles'
    ]
    
    logger.info(f"🚀 Starting comprehensive NFL data collection for all {len(all_teams)} teams")
    logger.info("This process will run to completion and collect authentic data for every player")
    
    try:
        # Run comprehensive scraping
        results = enhanced_scraping_system.scrape_all_teams_comprehensive(all_teams)
        
        # Save results to file
        if results["players_data"]:
            df = pd.DataFrame(results["players_data"])
            
            # Calculate gravity scores
            from gravity_score_system import _calculate_gravity_scores_for_dataframe
            df = _calculate_gravity_scores_for_dataframe(df)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data/all_teams_comprehensive_with_gravity_{timestamp}.csv"
            
            os.makedirs("data", exist_ok=True)
            df.to_csv(filename, index=False)
            
            logger.info(f"💾 Saved comprehensive data to: {filename}")
            logger.info(f"📊 Total players: {len(df)}")
            logger.info(f"✅ Teams successful: {results['teams_successful']}")
            logger.info(f"❌ Teams failed: {results['teams_failed']}")
            logger.info(f"📈 Average quality: {results['avg_quality_score']}")
            
            print(f"\n🎉 COMPREHENSIVE SCRAPING COMPLETED!")
            print(f"   Total Players: {len(df)}")
            print(f"   Successful Teams: {results['teams_successful']}/{results['teams_processed']}")
            print(f"   Data File: {filename}")
            print(f"   Average Quality Score: {results['avg_quality_score']}")
            
        else:
            logger.error("No player data collected")
            return 1
            
    except Exception as e:
        logger.error(f"💥 Scraping failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())