
#!/usr/bin/env python3
"""
Recalculate gravity scores for all players with the fixed algorithm
"""

import pandas as pd
import os
from datetime import datetime
from gravity_score_system import calculate_gravity_scores_for_dataset

def recalculate_all_gravity_scores():
    """Recalculate gravity scores for the latest dataset"""
    
    # Find the latest comprehensive dataset
    data_files = [
        'data/comprehensive_players_with_gravity_20250721_161823.csv',
        'data/comprehensive_players_20250720_155913.csv',
        'data/comprehensive_players_20250720_024215.csv'
    ]
    
    latest_file = None
    for file_path in data_files:
        if os.path.exists(file_path):
            latest_file = file_path
            break
    
    if not latest_file:
        print("❌ No comprehensive dataset found")
        return
    
    print(f"🔄 Recalculating gravity scores using: {latest_file}")
    
    try:
        # Load the dataset
        df = pd.read_csv(latest_file)
        print(f"📊 Loaded {len(df)} players")
        
        # Remove old gravity score columns if they exist
        gravity_columns = ['brand_power', 'proof', 'proximity', 'velocity', 'risk', 'total_gravity']
        df = df.drop(columns=[col for col in gravity_columns if col in df.columns], errors='ignore')
        
        # Recalculate gravity scores with fixed algorithm
        enhanced_df = calculate_gravity_scores_for_dataset(latest_file)
        
        # Save the corrected dataset
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"data/corrected_gravity_scores_{timestamp}.csv"
        enhanced_df.to_csv(output_file, index=False)
        
        print(f"💾 Corrected gravity scores saved to: {output_file}")
        
        # Show corrected scores for our test players
        test_players = ['Courtland Sutton', 'Pat Surtain II']
        
        print(f"\n📋 Corrected Gravity Scores:")
        print("=" * 70)
        
        for player_name in test_players:
            player_row = enhanced_df[enhanced_df['name'].str.contains(player_name, case=False, na=False)]
            
            if not player_row.empty:
                player = player_row.iloc[0]
                print(f"\n🏈 {player['name']} ({player.get('position', 'N/A')})")
                print(f"   Brand Power:  {player.get('brand_power', 0):5.1f}/100")
                print(f"   Proof:        {player.get('proof', 0):5.1f}/100")
                print(f"   Proximity:    {player.get('proximity', 0):5.1f}/100")
                print(f"   Velocity:     {player.get('velocity', 0):5.1f}/100")
                print(f"   Risk:         {player.get('risk', 0):5.1f}/100")
                print(f"   TOTAL GRAVITY: {player.get('total_gravity', 0):5.1f}/100")
            else:
                print(f"\n❌ {player_name} not found in dataset")
        
        # Show top 10 players by total gravity
        top_players = enhanced_df.nlargest(10, 'total_gravity')[['name', 'position', 'current_team', 'total_gravity']]
        print(f"\n🏆 Top 10 Players by Gravity Score:")
        print("=" * 50)
        for i, (_, player) in enumerate(top_players.iterrows(), 1):
            print(f"{i:2d}. {player['name']:20s} ({player.get('position', 'N/A'):2s}) - {player['total_gravity']:5.1f}")
        
        return output_file
        
    except Exception as e:
        print(f"❌ Error recalculating gravity scores: {e}")
        return None

if __name__ == "__main__":
    recalculate_all_gravity_scores()
