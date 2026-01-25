#!/usr/bin/env python3
"""
Merge CFB NIL & Social Data
============================
Merge manually curated NIL and social media data with scraped CFB player data.
"""

import pandas as pd
import sys

def main():
    if len(sys.argv) < 4:
        print("Usage: python merge_cfb_nil_data.py players.csv nil_social_data.csv output.csv")
        sys.exit(1)
    
    players_file = sys.argv[1]
    nil_file = sys.argv[2]
    output_file = sys.argv[3]
    
    print(f"\n{'='*80}")
    print(f"🔄 MERGING CFB NIL & SOCIAL DATA")
    print(f"{'='*80}\n")
    
    # Load data
    print(f"📂 Loading {players_file}...")
    df_players = pd.read_csv(players_file)
    print(f"   Loaded {len(df_players)} players")
    
    print(f"📂 Loading {nil_file}...")
    df_nil = pd.read_csv(nil_file)
    print(f"   Loaded {len(df_nil)} NIL profiles")
    
    # Add columns if they don't exist
    for col in ['instagram_handle', 'instagram_followers', 'instagram_verified',
                'twitter_handle', 'twitter_followers', 'twitter_verified',
                'nil_valuation', 'contract_value', 'free_agency_year']:
        if col not in df_players.columns:
            df_players[col] = None
    
    # Merge based on player_name
    print(f"\n🔄 Merging data...")
    matches = 0
    for _, nil_row in df_nil.iterrows():
        player_name = nil_row['player_name']
        
        # Find matching player(s)
        mask = df_players['player_name'] == player_name
        if mask.any():
            matches += 1
            # Update social and NIL data
            for col in ['instagram_handle', 'instagram_followers', 'instagram_verified',
                       'twitter_handle', 'twitter_followers', 'twitter_verified',
                       'nil_valuation', 'contract_value', 'free_agency_year']:
                if col in nil_row and pd.notna(nil_row[col]):
                    df_players.loc[mask, col] = nil_row[col]
            
            print(f"   ✅ {player_name:30s} - Updated")
        else:
            print(f"   ⚠️  {player_name:30s} - Not found in player data")
    
    # Save
    print(f"\n💾 Saving to {output_file}...")
    df_players.to_csv(output_file, index=False)
    
    # Summary
    print(f"\n{'='*80}")
    print(f"✅ MERGE COMPLETE!")
    print(f"{'='*80}\n")
    print(f"📊 Results:")
    print(f"   Total Players: {len(df_players)}")
    print(f"   Matched: {matches}/{len(df_nil)}")
    print(f"   Players with Instagram: {df_players['instagram_followers'].notna().sum()}")
    print(f"   Players with Twitter: {df_players['twitter_followers'].notna().sum()}")
    print(f"   Players with NIL: {df_players['nil_valuation'].notna().sum()}")
    
    # Show top enriched
    print(f"\n🏆 Top 10 by Instagram:")
    top = df_players[df_players['instagram_followers'].notna()].nlargest(10, 'instagram_followers')
    for _, row in top.iterrows():
        print(f"   • {row['player_name']:30s} {int(row['instagram_followers']):,} followers")
    
    print(f"\n💰 Top 10 by NIL Valuation:")
    top_nil = df_players[df_players['nil_valuation'].notna()].nlargest(10, 'nil_valuation')
    for _, row in top_nil.iterrows():
        print(f"   • {row['player_name']:30s} ${int(row['nil_valuation']):,}")
    
    print(f"\n{'='*80}")
    print(f"💡 Next Step: Run scoring pipeline!")
    print(f"   python score_all_sports.py {output_file} final_scores/CFB_COMPLETE.csv cfb")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()

