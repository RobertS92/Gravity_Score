#!/usr/bin/env python3
"""
Test Enhanced Social Media Collector
=====================================
Quick test to verify:
1. Wikidata integration
2. Enhanced DuckDuckGo searches
3. Handle saving (not just followers)
4. Validation by position
5. Cross-reference from Twitter
"""

import sys
import logging
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent))

from gravity.enhanced_social_collector import EnhancedSocialCollector

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_player(player_name, position):
    """Test enhanced collector for one player"""
    print("\n" + "="*80)
    print(f"  TESTING: {player_name} ({position})")
    print("="*80)
    
    collector = EnhancedSocialCollector()
    
    results = collector.collect_all_handles(player_name, position)
    
    print("\n📊 RESULTS:")
    print("-" * 80)
    
    for platform, data in results.items():
        handle = data.get('handle', 'N/A')
        followers = data.get('followers', 'N/A')
        source = data.get('source', 'unknown')
        validated = data.get('validated', 'N/A')
        
        if isinstance(followers, int):
            followers_str = f"{followers:,}"
        else:
            followers_str = str(followers)
        
        status = "✅" if validated == True else "⚠️" if validated == False else "❓"
        
        print(f"{status} {platform.upper():12} @{handle:25} {followers_str:>12} followers  [{source}]")
    
    # Summary
    total = len(results)
    validated_count = sum(1 for d in results.values() if d.get('validated') == True)
    
    print("-" * 80)
    print(f"TOTAL: {total}/4 platforms found, {validated_count} validated")
    
    return results

def main():
    """Test with 3 NFL players of different positions"""
    
    print("\n" + "="*80)
    print("  ENHANCED SOCIAL MEDIA COLLECTOR - TEST")
    print("="*80)
    
    test_players = [
        ("Patrick Mahomes", "QB"),
        ("Travis Kelce", "TE"),
        ("Justin Jefferson", "WR")
    ]
    
    all_results = {}
    
    for player_name, position in test_players:
        results = test_player(player_name, position)
        all_results[player_name] = results
    
    # Final Summary
    print("\n" + "="*80)
    print("  FINAL SUMMARY")
    print("="*80)
    
    for player_name, results in all_results.items():
        found = len(results)
        validated = sum(1 for d in results.values() if d.get('validated') == True)
        
        sources = set(d.get('source', 'unknown') for d in results.values())
        
        print(f"{player_name:20} {found}/4 found, {validated} validated  Sources: {', '.join(sources)}")
    
    print("\n✅ Test complete!")

if __name__ == "__main__":
    main()

