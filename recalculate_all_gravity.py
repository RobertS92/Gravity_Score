#!/usr/bin/env python3
"""
Recalculate gravity scores for ALL players using the consistent updated methodology
Ensures all players in the system use the same calculation method as Ecos players
"""

import pandas as pd
import os
import logging
from datetime import datetime
from gravity_score_system import GravityScoreCalculator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_latest_comprehensive_data_file():
    """Find the latest comprehensive data file with the most players."""
    data_dir = "data"
    if not os.path.exists(data_dir):
        return None
    
    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv') and not f.startswith('ecos') and not f.startswith('my_players')]
    if not csv_files:
        return None
    
    # Find file with most rows
    best_file = None
    max_rows = 0
    
    for file in csv_files:
        try:
            file_path = os.path.join(data_dir, file)
            df = pd.read_csv(file_path)
            if len(df) > max_rows:
                max_rows = len(df)
                best_file = file_path
        except:
            continue
    
    return best_file

def recalculate_gravity_scores_for_all():
    """Recalculate gravity scores for all players using updated methodology."""
    
    # Find the best data file
    data_file = find_latest_comprehensive_data_file()
    if not data_file:
        logger.error("No data file found")
        return False
    
    logger.info(f"Recalculating gravity scores for: {data_file}")
    
    # Load the data
    try:
        df = pd.read_csv(data_file)
        logger.info(f"Loaded {len(df)} players from {data_file}")
    except Exception as e:
        logger.error(f"Error loading data file: {e}")
        return False
    
    # Initialize gravity calculator with consistent methodology
    gravity_calculator = GravityScoreCalculator()
    
    # Calculate gravity scores for all players
    gravity_scores = []
    for index, row in df.iterrows():
        player_data = row.to_dict()
        player_name = player_data.get('name', f'Player_{index}')
        
        try:
            components = gravity_calculator.calculate_total_gravity(player_data)
            gravity_scores.append({
                'brand_power': round(components.brand_power, 1),
                'proof': round(components.proof, 1),
                'proximity': round(components.proximity, 1),
                'velocity': round(components.velocity, 1),
                'risk': round(components.risk, 1),
                'total_gravity': round(components.total_gravity, 1)
            })
            
            if index % 100 == 0:
                logger.info(f"Processed {index + 1}/{len(df)} players...")
                
        except Exception as e:
            logger.error(f"Error calculating gravity for {player_name}: {e}")
            # Add zero scores for failed calculations
            gravity_scores.append({
                'brand_power': 0.0,
                'proof': 0.0,
                'proximity': 0.0,
                'velocity': 0.0,
                'risk': 0.0,
                'total_gravity': 0.0
            })
    
    # Add gravity scores to dataframe
    gravity_df = pd.DataFrame(gravity_scores)
    enhanced_df = pd.concat([df, gravity_df], axis=1)
    
    # Sort by total gravity score (descending)
    enhanced_df = enhanced_df.sort_values('total_gravity', ascending=False)
    
    # Save the updated dataset
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"data/comprehensive_players_with_gravity_{timestamp}.csv"
    enhanced_df.to_csv(output_file, index=False)
    
    logger.info(f"Saved updated gravity scores to: {output_file}")
    
    # Show top players
    top_10 = enhanced_df.head(10)[['name', 'position', 'current_team', 'total_gravity']]
    logger.info("Top 10 players by gravity score:")
    for _, player in top_10.iterrows():
        logger.info(f"  {player['name']} ({player['position']}, {player['current_team']}): {player['total_gravity']}")
    
    # Check specific target players
    target_players = ['Patrick Mahomes', 'Lamar Jackson', 'Patrick Surtain', 'Courtland Sutton', 'Nick Bonitto']
    logger.info("\nTarget players gravity scores:")
    for target in target_players:
        matches = enhanced_df[enhanced_df['name'].str.contains(target, na=False, case=False)]
        if not matches.empty:
            player = matches.iloc[0]
            logger.info(f"  {player['name']}: {player['total_gravity']}")
    
    return output_file

if __name__ == "__main__":
    result = recalculate_gravity_scores_for_all()
    if result:
        print(f"SUCCESS: Gravity scores recalculated and saved to {result}")
    else:
        print("FAILED: Could not recalculate gravity scores")