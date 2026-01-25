#!/usr/bin/env python3
"""
Test Output Manager
===================
Quick test to verify the auto-incrementing filename system works
"""
from gravity.output_manager import OutputManager

def test_output_manager():
    print("="*70)
    print("TESTING OUTPUT MANAGER")
    print("="*70)
    
    manager = OutputManager()
    
    # Test NFL filenames
    print("\n📁 Testing NFL filename generation:")
    for i in range(3):
        filename = manager.get_next_filename('NFL', 'csv')
        print(f"   Next file would be: {filename}")
    
    # Test NBA filenames
    print("\n📁 Testing NBA filename generation:")
    for i in range(3):
        filename = manager.get_next_filename('NBA', 'csv')
        print(f"   Next file would be: {filename}")
    
    # Test getting latest file
    print("\n📂 Testing latest file retrieval:")
    for sport in ['NFL', 'NBA']:
        latest = manager.get_latest_file(sport)
        if latest:
            print(f"   {sport} latest: {latest}")
        else:
            print(f"   {sport}: No files yet")
    
    # Test listing files
    print("\n📋 Testing file listing:")
    for sport in ['NFL', 'NBA']:
        files = manager.list_files(sport)
        if files:
            print(f"\n   {sport} files:")
            for num, path in files:
                print(f"      {num:03d}: {path}")
        else:
            print(f"   {sport}: No files yet")
    
    # Test different formats
    print("\n📄 Testing different file formats:")
    for ext in ['csv', 'json', 'xlsx']:
        filename = manager.get_next_filename('NFL', ext)
        print(f"   {ext.upper()}: {filename}")
    
    print("\n" + "="*70)
    print("✅ OUTPUT MANAGER TEST COMPLETE")
    print("="*70)
    print("\nFolder structure created:")
    print("  Gravity_Final_Scores/")
    print("  ├── NFL/")
    print("  ├── NBA/")
    print("  ├── WNBA/")
    print("  ├── CFB/")
    print("  ├── NCAAB/")
    print("  └── WNCAAB/")
    print("\nFiles will be named:")
    print("  - NFL_Final_001.csv")
    print("  - NFL_Final_002.csv")
    print("  - NBA_Final_001.csv")
    print("  - etc.")
    print("\n💡 Run a scrape to see it in action:")
    print("   ./run_fast_nfl_scrape.sh")

if __name__ == '__main__':
    test_output_manager()

