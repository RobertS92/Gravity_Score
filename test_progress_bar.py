#!/usr/bin/env python3
"""
Quick test script to verify progress bars work correctly
Tests both NFL and NBA scrapers in test mode (one player per team)
"""

import os
import sys

print("="*70)
print("PROGRESS BAR TEST")
print("="*70)
print("\n🧪 This will test the progress bars by collecting one player per team")
print("   NFL: 32 players (one per team)")
print("   NBA: 30 players (one per team)")
print("\n⏱️  Estimated time: 5-10 minutes total")
print("\n" + "="*70)

# Set minimal workers for easier testing
os.environ['MAX_CONCURRENT_PLAYERS'] = '3'
os.environ['MAX_CONCURRENT_DATA_COLLECTORS'] = '4'

choice = input("\nSelect test:\n1. Test NFL progress bar\n2. Test NBA progress bar\n3. Both\n\nChoice (1-3): ").strip()

if choice == '1' or choice == '3':
    print("\n" + "="*70)
    print("TESTING NFL SCRAPER PROGRESS BAR")
    print("="*70)
    sys.argv = ['test_progress_bar.py', 'test']
    from gravity.nfl_scraper import main as nfl_main
    nfl_main()

if choice == '2' or choice == '3':
    print("\n" + "="*70)
    print("TESTING NBA SCRAPER PROGRESS BAR")
    print("="*70)
    sys.argv = ['test_progress_bar.py', 'test']
    from gravity.nba_scraper import main as nba_main
    nba_main()

print("\n" + "="*70)
print("✅ PROGRESS BAR TEST COMPLETE")
print("="*70)
print("\nCheck the progress bars above - they should show:")
print("  ✅ Player count (N/Total)")
print("  ✅ Progress bar")
print("  ✅ Elapsed time")
print("  ✅ Accurate ETA (estimated time remaining)")
print("  ✅ Success/Failed counts")
print("  ✅ Average time per player")
print("\n" + "="*70)

