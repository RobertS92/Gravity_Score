
"""
Test Google News Integration with Real Data Collector
"""

import logging
from real_data_collector import RealDataCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_news_integration():
    """Test the Google News integration with the real data collector."""
    
    print("=== TESTING GOOGLE NEWS INTEGRATION ===")
    
    collector = RealDataCollector()
    
    # Test with a well-known player
    test_player = "Patrick Mahomes"
    test_team = "chiefs"
    
    print(f"Testing Google News extraction for {test_player} ({test_team})")
    
    try:
        # Collect comprehensive data including news
        player_data = collector.collect_comprehensive_data(test_player, test_team)
        
        print(f"\n📰 Google News Results for {test_player}:")
        print(f"Headlines found: {player_data.get('news_headline_count', 0)}")
        print(f"Bio snippets: {len(player_data.get('news_bio_snippets', []))}")
        
        # Display recent headlines
        headlines = player_data.get('recent_headlines', [])
        if headlines:
            print(f"\nRecent Headlines ({len(headlines)}):")
            for i, headline in enumerate(headlines[:5], 1):
                print(f"  {i}. {headline}")
        
        # Display bio snippets
        bio_snippets = player_data.get('news_bio_snippets', [])
        if bio_snippets:
            print(f"\nBio Snippets ({len(bio_snippets)}):")
            for i, snippet in enumerate(bio_snippets[:3], 1):
                print(f"  {i}. {snippet[:100]}...")
        
        # Display Google News URL
        news_url = player_data.get('google_news_url')
        if news_url:
            print(f"\nGoogle News URL: {news_url}")
        
        # Overall data quality
        print(f"\nOverall Data Quality: {player_data.get('data_quality_score', 0)}/5.0")
        print(f"Data Sources: {player_data.get('data_sources', [])}")
        
        return True
        
    except Exception as e:
        print(f"Error testing Google News integration: {e}")
        return False

if __name__ == "__main__":
    success = test_news_integration()
    if success:
        print("\n✅ Google News integration test completed successfully!")
    else:
        print("\n❌ Google News integration test failed!")
