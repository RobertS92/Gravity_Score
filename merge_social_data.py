#!/usr/bin/env python3
"""
Merge Curated Social Data
===========================
Merge manually curated social media and contract data with scraped player data.
"""

import pandas as pd
import sys

def main():
    if len(sys.argv) < 4:
        print("Usage: python merge_social_data.py players.csv social_data.csv output.csv")
        sys.exit(1)
    
    players_file = sys.argv[1]
    social_file = sys.argv[2]
    output_file = sys.argv[3]
    
    print(f"\n{'='*80}")
    print(f"🔄 MERGING CURATED SOCIAL DATA")
    print(f"{'='*80}\n")
    
    # Load data
    print(f"📂 Loading {players_file}...")
    df_players = pd.read_csv(players_file)
    print(f"   Loaded {len(df_players)} players")
    
    print(f"📂 Loading {social_file}...")
    df_social = pd.read_csv(social_file)
    print(f"   Loaded {len(df_social)} social profiles")
    
    # Add social columns if they don't exist
    for col in ['instagram_handle', 'instagram_followers', 'instagram_verified',
                'twitter_handle', 'twitter_followers', 'twitter_verified',
                'contract_value', 'free_agency_year']:
        if col not in df_players.columns:
            df_players[col] = None
    
    # Merge based on player_name
    print(f"\n🔄 Merging data...")
    matches = 0
    for _, social_row in df_social.iterrows():
        player_name = social_row['player_name']
        
        # Find matching player(s)
        mask = df_players['player_name'] == player_name
        if mask.any():
            matches += 1
            # Update social data
            for col in ['instagram_handle', 'instagram_followers', 'instagram_verified',
                       'twitter_handle', 'twitter_followers', 'twitter_verified',
                       'contract_value', 'free_agency_year']:
                if col in social_row and pd.notna(social_row[col]):
                    df_players.loc[mask, col] = social_row[col]
            
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
    print(f"   Matched: {matches}/{len(df_social)}")
    print(f"   Players with Instagram: {df_players['instagram_followers'].notna().sum()}")
    print(f"   Players with Twitter: {df_players['twitter_followers'].notna().sum()}")
    print(f"   Players with Contract: {df_players['contract_value'].notna().sum()}")
    
    # Show top enriched
    print(f"\n🏆 Top 10 by Instagram:")
    top = df_players[df_players['instagram_followers'].notna()].nlargest(10, 'instagram_followers')
    for _, row in top.iterrows():
        print(f"   • {row['player_name']:30s} {int(row['instagram_followers']):,} followers")
    
    print(f"\n💰 Top 10 by Contract:")
    top_contract = df_players[df_players['contract_value'].notna()].nlargest(10, 'contract_value')
    for _, row in top_contract.iterrows():
        print(f"   • {row['player_name']:30s} ${int(row['contract_value']):,}")
    
    print(f"\n{'='*80}")
    print(f"💡 Next Step: Run scoring pipeline!")
    print(f"   python score_all_sports.py {output_file} final_scores/NFL_WITH_SOCIAL.csv nfl")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()

