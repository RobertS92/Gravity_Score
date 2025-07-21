#!/usr/bin/env python3
"""
Update gravity scores with the improved risk calculation
"""

import pandas as pd
import glob
from gravity_score_system import GravityScoreCalculator

def find_best_dataset():
    """Find the most recent and complete dataset"""
    csv_files = glob.glob('./data/*.csv')
    csv_files.sort(key=lambda x: x.split('_')[-1], reverse=True)  # Sort by timestamp
    
    for file in csv_files:
        if 'gravity' not in file and any(keyword in file for keyword in ['players', 'enhanced']):
            try:
                df = pd.read_csv(file)
                if len(df) > 100 and 'position' in df.columns:  # Good dataset
                    print(f"Using dataset: {file} ({len(df)} players)")
                    return file, df
            except:
                continue
    
    return None, None

def update_gravity_scores():
    """Update gravity scores with improved calculation"""
    file_path, df = find_best_dataset()
    
    if df is None:
        print("No suitable dataset found")
        return
    
    print(f"Updating gravity scores for {len(df)} players...")
    
    calculator = GravityScoreCalculator()
    
    # Calculate new gravity scores
    gravity_data = []
    for index, row in df.iterrows():
        player_data = row.to_dict()
        
        try:
            components = calculator.calculate_total_gravity(player_data)
            gravity_data.append({
                'brand_power': components.brand_power,
                'proof': components.proof,
                'proximity': components.proximity,
                'velocity': components.velocity,
                'risk': components.risk,
                'total_gravity': components.total_gravity
            })
        except Exception as e:
            print(f"Error calculating gravity for {player_data.get('name', 'Unknown')}: {e}")
            gravity_data.append({
                'brand_power': 0, 'proof': 0, 'proximity': 0, 
                'velocity': 0, 'risk': 0, 'total_gravity': 0
            })
    
    # Add gravity scores to dataframe
    gravity_df = pd.DataFrame(gravity_data)
    result_df = pd.concat([df, gravity_df], axis=1)
    
    # Save updated dataset
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'./data/players_with_updated_gravity_{timestamp}.csv'
    result_df.to_csv(output_file, index=False)
    
    print(f"Updated gravity scores saved to: {output_file}")
    
    # Show sample of new risk scores
    print("\nSample of new risk scores:")
    sample_data = result_df[['name', 'position', 'age', 'jersey_number', 'risk']].head(10)
    print(sample_data.to_string(index=False))
    
    return output_file

if __name__ == "__main__":
    update_gravity_scores()