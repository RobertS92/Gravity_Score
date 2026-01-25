#!/usr/bin/env python3
"""Quick test of news collection improvements"""

import sys
from pathlib import Path
import logging

# Add paths
script_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(script_dir))

from gravity.news_collector import NewsCollector

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TEST_PLAYER = "Patrick Mahomes"
ESPN_ID = "3139477"  # Patrick Mahomes ESPN ID

def run_test():
    logger.info(f"\n{'='*70}")
    logger.info(f"TESTING NEWS COLLECTION FOR: {TEST_PLAYER}")
    logger.info(f"{'='*70}\n")
    
    collector = NewsCollector()
    
    # Test news collection with ESPN ID
    news_data = collector.collect_news_data(TEST_PLAYER, ESPN_ID)
    
    logger.info(f"\n{'='*70}")
    logger.info(f"NEWS COLLECTION RESULTS:")
    logger.info(f"{'='*70}")
    logger.info(f"30-day headline count: {news_data.get('news_headline_count_30d', 0)}")
    logger.info(f"7-day headline count: {news_data.get('news_headline_count_7d', 0)}")
    logger.info(f"Media sentiment: {news_data.get('media_sentiment', 0.0):.3f}")
    logger.info(f"Mention velocity: {news_data.get('mention_velocity', 0.0):.2f} mentions/day")
    logger.info(f"Trending: {news_data.get('trending', False)}")
    
    recent_headlines = news_data.get('recent_headlines', [])
    if recent_headlines:
        logger.info(f"\nRecent Headlines (showing first 5):")
        for i, headline in enumerate(recent_headlines[:5], 1):
            logger.info(f"  {i}. {headline.get('headline', 'N/A')}")
            logger.info(f"     Source: {headline.get('source', 'Unknown')}")
            logger.info(f"     Date: {headline.get('date', 'Unknown')}")
            logger.info(f"     Relevance: {headline.get('relevance', 0.0):.2f}")
    else:
        logger.warning("❌ No headlines found!")
    
    logger.info(f"\n{'='*70}\n")

if __name__ == "__main__":
    run_test()

