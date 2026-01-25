#!/usr/bin/env python3
"""Test NewsAPI.org integration with API key"""

import sys
import os
from pathlib import Path
import logging

# Add paths
script_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(script_dir))

# Set the API key
os.environ['NEWSAPI_KEY'] = 'bcc491d49a67441ca3fa05145ba2a8d4'

from gravity.news_collector import NewsCollector

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TEST_PLAYER = "Patrick Mahomes"
ESPN_ID = "3139477"

def run_test():
    logger.info(f"\n{'='*70}")
    logger.info(f"TESTING NEWSAPI.ORG INTEGRATION FOR: {TEST_PLAYER}")
    logger.info(f"{'='*70}\n")
    
    collector = NewsCollector()
    
    # Verify API key is detected
    if collector.newsapi_key:
        logger.info(f"✅ NewsAPI key detected: {collector.newsapi_key[:8]}...")
    else:
        logger.error("❌ NewsAPI key NOT detected!")
        return
    
    # Test news collection with ESPN ID and NewsAPI
    news_data = collector.collect_news_data(TEST_PLAYER, ESPN_ID)
    
    logger.info(f"\n{'='*70}")
    logger.info(f"NEWSAPI INTEGRATION RESULTS:")
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
    
    logger.info(f"\n📰 SOURCE BREAKDOWN:")
    recent_headlines = news_data.get('recent_headlines', [])
    sources = {}
    for headline in recent_headlines:
        source = headline.get('source', 'Unknown')
        sources[source] = sources.get(source, 0) + 1
    
    for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"   {source}: {count} articles")
    
    logger.info(f"\n📰 SAMPLE HEADLINES (first 5):")
    for i, headline in enumerate(recent_headlines[:5], 1):
        logger.info(f"   {i}. {headline.get('headline', 'N/A')}")
        logger.info(f"      Source: {headline.get('source', 'Unknown')}, Date: {headline.get('date', 'Unknown')}")
    
    logger.info(f"\n{'='*70}\n")

if __name__ == "__main__":
    run_test()

