#!/usr/bin/env python3
"""
Test script for Firecrawl comprehensive scraper
"""

import json
import logging
from firecrawl_comprehensive_scraper import FirecrawlComprehensiveScraper

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_firecrawl_scraper():
    """Test the Firecrawl comprehensive scraper"""
    
    try:
        scraper = FirecrawlComprehensiveScraper()
        
        # Test players
        test_players = [
            {"name": "Brock Purdy", "team": "49ers"},
            {"name": "Christian McCaffrey", "team": "49ers"},
            {"name": "Nick Bosa", "team": "49ers"}
        ]
        
        all_results = []
        
        for player in test_players:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing Firecrawl scraper for {player['name']} ({player['team']})")
            logger.info(f"{'='*60}")
            
            try:
                result = scraper.collect_comprehensive_player_data(
                    player_name=player['name'],
                    team=player['team']
                )
                
                all_results.append(result)
                
                # Print summary
                filled_fields = scraper._count_filled_fields(result)
                quality_score = result.get('data_quality_score', 0)
                sources = result.get('data_sources', [])
                
                print(f"\nPlayer: {player['name']} ({player['team']})")
                print(f"Fields filled: {filled_fields}/74")
                print(f"Quality score: {quality_score}/10")
                print(f"Sources used: {', '.join(sources)}")
                print(f"Collection time: {result.get('collection_duration', 0)}s")
                
                # Show key fields that were successfully collected
                key_fields = [
                    'age', 'height', 'weight', 'college', 'position', 'jersey_number',
                    'twitter_handle', 'instagram_handle', 'twitter_followers',
                    'current_salary', 'career_stats', 'awards', 'draft_year'
                ]
                
                print("\nSuccessfully collected fields:")
                for field in key_fields:
                    value = result.get(field)
                    if value is not None and value != '' and value != []:
                        print(f"  {field}: {value}")
                
            except Exception as e:
                logger.error(f"Error testing {player['name']}: {e}")
                continue
        
        # Save results
        with open('firecrawl_test_results.json', 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        
        print(f"\n{'='*60}")
        print(f"Firecrawl test completed for {len(all_results)} players")
        print("Results saved to firecrawl_test_results.json")
        print(f"{'='*60}")
        
    except Exception as e:
        logger.error(f"Failed to initialize Firecrawl scraper: {e}")
        print("Make sure FIRECRAWL_API_KEY is set in environment variables")

if __name__ == "__main__":
    test_firecrawl_scraper()