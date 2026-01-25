#!/usr/bin/env python3
"""Quick test to verify draft data fix for Patrick Mahomes"""

import sys
import json
from pathlib import Path
import logging

# Set up logging to see debug messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add gravity module to path
script_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(script_dir))

# Import dynamically
import importlib.util
scrape_path = script_dir / "gravity" / "scrape"
spec = importlib.util.spec_from_file_location("scrape_module", scrape_path)
scrape_module = importlib.util.module_from_spec(spec)
sys.modules['scrape_module'] = scrape_module
spec.loader.exec_module(scrape_module)

print("=" * 80)
print("  TESTING DRAFT DATA FIX")
print("=" * 80)

# Initialize collector
collector = scrape_module.NFLDataCollector()

# Test with Patrick Mahomes
player_name = "Patrick Mahomes"
print(f"\n🔍 Collecting data for {player_name}...")

player_data = collector.collect_player_data(
    player_name=player_name,
    team="Kansas City Chiefs",
    position="QB",
    espn_id="3139477"
)

# Check draft data
print("\n" + "=" * 80)
print("  DRAFT DATA RESULTS")
print("=" * 80)

if player_data and player_data.identity:
    draft_year = player_data.identity.draft_year
    draft_round = player_data.identity.draft_round
    draft_pick = player_data.identity.draft_pick
    
    print(f"Draft Year:  {draft_year}")
    print(f"Draft Round: {draft_round}")
    print(f"Draft Pick:  {draft_pick}")
    
    # Verify
    if draft_year == 2017 and draft_round == 1 and draft_pick == 10:
        print("\n✅ SUCCESS! Draft data correctly parsed!")
        print(f"   Patrick Mahomes was drafted in 2017, Round 1, Pick 10")
    elif draft_year == "Undrafted":
        print("\n❌ FAILED! Still showing 'Undrafted'")
        print("   Expected: 2017, Round 1, Pick 10")
    else:
        print(f"\n⚠️  PARTIAL: Got {draft_year}, Rd {draft_round}, Pk {draft_pick}")
        print("   Expected: 2017, Round 1, Pick 10")
else:
    print("\n❌ FAILED! No player data returned")

print("=" * 80)

