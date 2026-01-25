#!/usr/bin/env python3
"""Quick test of historical news collection"""

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
ESPN_ID = "3139477"

def run_test():
    logger.info(f"\n{'='*70}")
    logger.info(f"TESTING HISTORICAL NEWS COLLECTION FOR: {TEST_PLAYER}")
    logger.info(f"{'='*70}\n")
    
    collector = NewsCollector()
    
    # Test news collection with ESPN ID
    news_data = collector.collect_news_data(TEST_PLAYER, ESPN_ID)
    
    logger.info(f"\n{'='*70}")
    logger.info(f"HISTORICAL NEWS COLLECTION RESULTS:")
    logger.info(f"{'='*70}")
    logger.info(f"📊 HEADLINE COUNTS:")
    logger.info(f"   7 days:   {news_data.get('news_headline_count_7d', 0)}")
    logger.info(f"   30 days:  {news_data.get('news_headline_count_30d', 0)}")
    logger.info(f"   1 year:   {news_data.get('news_headline_count_365d', 0)}")
    logger.info(f"   3 years:  {news_data.get('news_headline_count_1095d', 0)}")
    
    logger.info(f"\n📈 SENTIMENT BY TIME PERIOD:")
    logger.info(f"   Overall:  {news_data.get('media_sentiment', 0.0):.3f}")
    logger.info(f"   7 days:   {news_data.get('media_sentiment_7d', 0.0):.3f}")
    logger.info(f"   30 days:  {news_data.get('media_sentiment_30d', 0.0):.3f}")
    logger.info(f"   1 year:   {news_data.get('media_sentiment_365d', 0.0):.3f}")
    logger.info(f"   3 years:  {news_data.get('media_sentiment_1095d', 0.0):.3f}")
    
    logger.info(f"\n📰 OTHER METRICS:")
    logger.info(f"   Mention velocity: {news_data.get('mention_velocity', 0.0):.2f} mentions/day")
    logger.info(f"   Trending: {news_data.get('trending', False)}")
    
    logger.info(f"\n{'='*70}\n")

if __name__ == "__main__":
    run_test()

