#!/usr/bin/env python3
"""
Comprehensive demo of the NFL Gravity Pipeline
"""

from nfl_gravity_pipeline import NFLGravityPipeline
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def demo_pipeline():
    """Demonstrate the pipeline capabilities."""
    print("🏈 NFL Gravity Pipeline - Comprehensive Demo")
    print("=" * 60)
    
    # Initialize pipeline
    pipeline = NFLGravityPipeline()
    
    print("📋 Pipeline Features:")
    print("• Scrapes all 32 NFL team rosters")
    print("• Discovers social media URLs for each player")
    print("• Extracts Wikipedia biographical data")
    print("• Analyzes social media engagement metrics")
    print("• Collects news presence data")
    print("• Exports to CSV with comprehensive analytics")
    print()
    
    # Test roster scraping for multiple teams
    print("🔍 Testing roster scraping for 3 teams...")
    
    teams_to_test = ["arizona-cardinals", "kansas-city-chiefs", "new-england-patriots"]
    all_players = []
    
    for team in teams_to_test:
        print(f"\nScraping {team.replace('-', ' ').title()}...")
        df = pipeline.scrape_team_roster(team)
        print(f"Found {len(df)} players")
        all_players.extend(df['Player'].tolist())
    
    print(f"\n📊 Total players found: {len(all_players)}")
    print(f"Sample players: {all_players[:10]}")
    
    # Test Wikipedia parsing
    print("\n🔍 Testing Wikipedia data extraction...")
    test_players = ["Kyler Murray", "Patrick Mahomes", "Mac Jones"]
    
    for player in test_players:
        print(f"\nTesting {player}:")
        wiki_data = pipeline.parse_wikipedia(player)
        print(f"  Age: {wiki_data.get('Age', 'Not found')}")
        print(f"  Position: {wiki_data.get('Position', 'Not found')}")
        print(f"  College: {wiki_data.get('College', 'Not found')}")
        print(f"  Draft Year: {wiki_data.get('DraftYear', 'Not found')}")
    
    # Test social media discovery
    print("\n🔍 Testing social media URL discovery...")
    
    for player in test_players:
        print(f"\nDiscovering social media for {player}:")
        social_urls = pipeline.discover_social_urls(player)
        for platform, url in social_urls.items():
            if url:
                print(f"  {platform}: {url}")
    
    # Test news count
    print("\n🔍 Testing news presence analysis...")
    
    for player in test_players:
        news_count = pipeline.get_news_count(player)
        print(f"{player}: {news_count} news articles found")
    
    print("\n" + "=" * 60)
    print("✅ Demo completed successfully!")
    print("\nTo run full pipeline:")
    print("1. python nfl_gravity_pipeline.py (interactive)")
    print("2. Modify max_players parameter for testing")
    print("3. Full pipeline processes all ~2,700 NFL players")
    print("4. Outputs comprehensive CSV with all metrics")

if __name__ == "__main__":
    demo_pipeline()