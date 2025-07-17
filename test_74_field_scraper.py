#!/usr/bin/env python3
"""
Test script for the comprehensive 74-field scraper
Collects data for a few players to verify functionality
"""

import json
import logging
from comprehensive_74_field_scraper import Comprehensive74FieldScraper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_comprehensive_scraper():
    """Test the 74-field scraper with a few players"""
    
    scraper = Comprehensive74FieldScraper()
    
    # Test players from different teams
    test_players = [
        {"name": "Brock Purdy", "team": "49ers", "position": "QB"},
        {"name": "Christian McCaffrey", "team": "49ers", "position": "RB"},
        {"name": "Nick Bosa", "team": "49ers", "position": "DE"},
        {"name": "Josh Allen", "team": "Bills", "position": "QB"},
        {"name": "Patrick Mahomes", "team": "Chiefs", "position": "QB"}
    ]
    
    all_results = []
    
    for player in test_players:
        logger.info(f"Testing scraper for {player['name']} ({player['team']})")
        
        try:
            result = scraper.collect_all_fields(
                player_name=player['name'],
                team=player['team'],
                position=player['position']
            )
            
            all_results.append(result)
            
            # Print summary
            filled_fields = scraper._count_filled_fields(result)
            quality_score = result.get('data_quality_score', 0)
            sources = result.get('data_sources', [])
            
            print(f"\n{'='*60}")
            print(f"Player: {player['name']} ({player['team']})")
            print(f"Fields filled: {filled_fields}/74")
            print(f"Quality score: {quality_score}/10")
            print(f"Sources used: {', '.join(sources)}")
            print(f"Collection time: {result.get('collection_duration', 0)}s")
            
            # Show some key fields
            key_fields = [
                'age', 'height', 'weight', 'college', 'draft_year',
                'twitter_handle', 'instagram_handle', 'twitter_followers',
                'career_stats', 'awards', 'current_salary'
            ]
            
            print("\nKey fields:")
            for field in key_fields:
                value = result.get(field)
                if value is not None and value != '' and value != []:
                    print(f"  {field}: {value}")
            
        except Exception as e:
            logger.error(f"Error testing {player['name']}: {e}")
            continue
    
    # Save results to JSON for inspection
    with open('test_74_field_results.json', 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\n{'='*60}")
    print(f"Test completed for {len(all_results)} players")
    print("Results saved to test_74_field_results.json")
    print(f"{'='*60}")

if __name__ == "__main__":
    test_comprehensive_scraper()