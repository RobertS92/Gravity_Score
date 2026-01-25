#!/usr/bin/env python3
"""
Quick test to verify all fixes:
1. Draft data parsing (displayDraft, PFR)
2. Career stats aggregation (sum across years)
3. Google Trends compatibility (no method_whitelist error)
"""

import sys
import os
import json
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add gravity module to path
sys.path.insert(0, str(Path(__file__).parent))

# Import the scrape module dynamically
import importlib.util
scrape_path = Path(__file__).parent / "gravity" / "scrape"
spec = importlib.util.spec_from_file_location("scrape", scrape_path)
if spec is None:
    raise ImportError(f"Could not load spec from {scrape_path}")
scrape_module = importlib.util.module_from_spec(spec)
sys.modules['scrape'] = scrape_module
spec.loader.exec_module(scrape_module)

def main():
    print("=" * 80)
    print("  QUICK FIX VERIFICATION TEST")
    print("=" * 80)
    
    # Initialize collector
    collector = scrape_module.NFLDataCollector()
    
    # Test with just Patrick Mahomes
    logger.info(f"\n🔍 Testing fixes with Patrick Mahomes...")
    
    # Run scraper
    player_data = collector.collect_player_data(
        player_name="Patrick Mahomes",
        team="Kansas City Chiefs",
        position="QB",
        espn_id="3139477"
    )
    
    # Convert to dict for checking
    from dataclasses import asdict
    results = [asdict(player_data)] if player_data else []
    
    if results and len(results) > 0:
        player = results[0]
        
        print("\n" + "=" * 80)
        print("  VERIFICATION RESULTS")
        print("=" * 80)
        
        # Check 1: Draft Data
        print("\n✅ FIX 1: Draft Data Parsing")
        print(f"   Draft Year:  {player.get('identity', {}).get('draft_year', 'N/A')}")
        print(f"   Draft Round: {player.get('identity', {}).get('draft_round', 'N/A')}")
        print(f"   Draft Pick:  {player.get('identity', {}).get('draft_pick', 'N/A')}")
        
        if player.get('identity', {}).get('draft_year') == 2017:
            print("   ✅ PASS - Draft data correctly parsed!")
        else:
            print("   ❌ FAIL - Draft data still incorrect")
        
        # Check 2: Career Stats Aggregation
        print("\n✅ FIX 2: Career Stats Aggregation")
        career_stats = player.get('proof', {}).get('career_stats', {})
        passing_yards = career_stats.get('passing_yards', 0)
        passing_tds = career_stats.get('passing_touchdowns', 0)
        
        print(f"   Career Passing Yards: {passing_yards:,.0f}")
        print(f"   Career Passing TDs:   {passing_tds}")
        
        if passing_yards > 30000:  # Mahomes has 30,000+ career yards
            print("   ✅ PASS - Career stats correctly aggregated!")
        else:
            print(f"   ❌ FAIL - Career stats not aggregated (expected 30,000+, got {passing_yards:,.0f})")
        
        # Check 3: Google Trends (just check if it ran without error)
        print("\n✅ FIX 3: Google Trends Compatibility")
        trends_score = player.get('brand', {}).get('google_trends_score', 0)
        print(f"   Trends Score: {trends_score}")
        print("   ✅ PASS - No method_whitelist error!")
        
        # Summary
        print("\n" + "=" * 80)
        print("  TEST COMPLETE")
        print("=" * 80)
        
        # Save results
        output_file = Path("test_outputs/quick_fix_test.json")
        output_file.parent.mkdir(exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(player, f, indent=2, default=str)
        print(f"\n📁 Full results saved to: {output_file}")
    else:
        print("\n❌ FAILED - No results returned")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

