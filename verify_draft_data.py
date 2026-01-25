#!/usr/bin/env python3
"""
Quick Draft Data Verification
==============================

Checks if draft data is being collected properly or if it's just saying "Undrafted".

Usage:
    python verify_draft_data.py latest_scrape.csv

Author: Gravity Score Team
"""

import pandas as pd
import sys

def verify_draft_data(csv_file: str):
    """Verify draft data quality"""
    
    print("=" * 80)
    print("🔍 DRAFT DATA VERIFICATION")
    print("=" * 80)
    print(f"\nAnalyzing: {csv_file}\n")
    
    # Load data
    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return
    
    # Check draft columns
    draft_cols = []
    for col in ['draft_year', 'identity.draft_year']:
        if col in df.columns:
            draft_year_col = col
            draft_cols.append(col)
            break
    else:
        print("❌ No draft_year column found!")
        return
    
    for col in ['draft_round', 'identity.draft_round']:
        if col in df.columns:
            draft_round_col = col
            draft_cols.append(col)
            break
    else:
        print("❌ No draft_round column found!")
        return
    
    for col in ['draft_pick', 'identity.draft_pick']:
        if col in df.columns:
            draft_pick_col = col
            draft_cols.append(col)
            break
    else:
        print("❌ No draft_pick column found!")
        return
    
    print(f"Found draft columns: {draft_cols}\n")
    
    # Analyze draft data
    total = len(df)
    
    # Count "Undrafted"
    undrafted_year = (df[draft_year_col] == "Undrafted").sum()
    undrafted_round = (df[draft_round_col] == "Undrafted").sum()
    undrafted_pick = (df[draft_pick_col] == "Undrafted").sum()
    
    # Count None/NaN
    none_year = df[draft_year_col].isna().sum()
    none_round = df[draft_round_col].isna().sum()
    none_pick = df[draft_pick_col].isna().sum()
    
    # Count valid data
    valid_year = df[draft_year_col].notna() & (df[draft_year_col] != "Undrafted")
    valid_round = df[draft_round_col].notna() & (df[draft_round_col] != "Undrafted")
    valid_pick = df[draft_pick_col].notna() & (df[draft_pick_col] != "Undrafted")
    
    valid_year_count = valid_year.sum()
    valid_round_count = valid_round.sum()
    valid_pick_count = valid_pick.sum()
    
    # Print results
    print("📊 DRAFT DATA BREAKDOWN")
    print("=" * 80)
    print(f"\nTotal Players: {total}\n")
    
    print(f"Draft Year ({draft_year_col}):")
    print(f"  ✓ Valid data:     {valid_year_count:4d} ({valid_year_count/total*100:5.1f}%)")
    print(f"  ⚠ 'Undrafted':    {undrafted_year:4d} ({undrafted_year/total*100:5.1f}%)")
    print(f"  ❌ None/Missing:  {none_year:4d} ({none_year/total*100:5.1f}%)")
    
    print(f"\nDraft Round ({draft_round_col}):")
    print(f"  ✓ Valid data:     {valid_round_count:4d} ({valid_round_count/total*100:5.1f}%)")
    print(f"  ⚠ 'Undrafted':    {undrafted_round:4d} ({undrafted_round/total*100:5.1f}%)")
    print(f"  ❌ None/Missing:  {none_round:4d} ({none_round/total*100:5.1f}%)")
    
    print(f"\nDraft Pick ({draft_pick_col}):")
    print(f"  ✓ Valid data:     {valid_pick_count:4d} ({valid_pick_count/total*100:5.1f}%)")
    print(f"  ⚠ 'Undrafted':    {undrafted_pick:4d} ({undrafted_pick/total*100:5.1f}%)")
    print(f"  ❌ None/Missing:  {none_pick:4d} ({none_pick/total*100:5.1f}%)")
    
    # Sample "Undrafted" players
    if undrafted_year > 0:
        print("\n" + "=" * 80)
        print("⚠️  SAMPLE 'UNDRAFTED' PLAYERS (first 10):")
        print("=" * 80)
        
        undrafted_players = df[df[draft_year_col] == "Undrafted"]
        
        for idx, row in undrafted_players.head(10).iterrows():
            player_name = row.get('player_name', 'Unknown')
            team = row.get('team', row.get('identity.team', 'Unknown'))
            position = row.get('position', row.get('identity.position', 'Unknown'))
            print(f"  {player_name} ({team}, {position})")
    
    # Recommendations
    print("\n" + "=" * 80)
    print("💡 RECOMMENDATIONS")
    print("=" * 80)
    
    if undrafted_year > total * 0.1:  # More than 10% marked as undrafted
        print("\n⚠️  HIGH 'Undrafted' Rate Detected!")
        print(f"   {undrafted_year} players ({undrafted_year/total*100:.1f}%) marked as 'Undrafted'")
        print("\n   Recommended actions:")
        print("   1. Run draft data validator to check if these are truly undrafted:")
        print(f"      python draft_data_validator.py {csv_file} validated.csv")
        print("\n   2. This will:")
        print("      - Check Pro Football Reference for actual draft data")
        print("      - Correct players who were actually drafted")
        print("      - Take ~30 seconds for one-time setup")
    
    if valid_year_count / total > 0.85:
        print("\n✅ Draft data looks good!")
        print(f"   {valid_year_count/total*100:.1f}% of players have valid draft data")
    
    if undrafted_year < total * 0.05:
        print("\n✅ 'Undrafted' rate is reasonable")
        print("   Most players have draft data from ESPN")
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python verify_draft_data.py <csv_file>")
        print("\nExample:")
        print("  python verify_draft_data.py scrapes/NFL/latest/nfl_players_*.csv")
        sys.exit(1)
    
    verify_draft_data(sys.argv[1])

