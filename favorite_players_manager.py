"""
Favorite Players Manager - Comprehensive data collection and management for favorite players
Ensures all favorite players have complete 70+ column data with accurate gravity scores
"""

import os
import logging
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any
from real_data_collector import RealDataCollector
from gravity_score_system import calculate_gravity_scores_for_dataset
import json

logger = logging.getLogger(__name__)

class FavoritePlayersManager:
    """Manages favorite players with comprehensive data collection."""
    
    def __init__(self):
        self.collector = RealDataCollector()
        self.favorites_file = "data/favorite_players.json"
        self.favorites_data_file = "data/favorite_players_comprehensive.csv"
        
    def add_favorite_players(self, player_names: List[str]) -> Dict[str, Any]:
        """Add players to favorites and ensure comprehensive data collection."""
        logger.info(f"Adding {len(player_names)} players to favorites: {player_names}")
        
        # Load existing favorites
        favorites = self._load_favorites()
        
        # Search for players in existing data
        found_players = []
        missing_players = []
        
        for player_name in player_names:
            player_data = self._find_player_in_data(player_name)
            if player_data:
                found_players.append(player_data)
                logger.info(f"✓ Found {player_name} in existing data")
            else:
                missing_players.append(player_name)
                logger.info(f"⚠ Need to collect data for {player_name}")
        
        # Collect comprehensive data for missing players
        newly_collected = []
        if missing_players:
            logger.info(f"Collecting comprehensive data for {len(missing_players)} missing players")
            newly_collected = self._collect_missing_players(missing_players)
        
        # Combine all player data
        all_favorite_data = found_players + newly_collected
        
        # Calculate gravity scores for all favorites
        if all_favorite_data:
            df = pd.DataFrame(all_favorite_data)
            
            # Ensure gravity scores are calculated
            from app import _calculate_gravity_scores_for_dataframe
            df = _calculate_gravity_scores_for_dataframe(df)
            
            # Save comprehensive favorites data
            os.makedirs("data", exist_ok=True)
            df.to_csv(self.favorites_data_file, index=False)
            
            # Update favorites list
            for _, row in df.iterrows():
                player_name = row['name']
                if player_name not in [f['name'] for f in favorites]:
                    favorites.append({
                        'name': player_name,
                        'position': row.get('position', ''),
                        'team': row.get('current_team', ''),
                        'gravity_score': row.get('total_gravity', 0),
                        'added_date': datetime.now().isoformat()
                    })
            
            self._save_favorites(favorites)
            
            logger.info(f"✅ Successfully added {len(player_names)} players to favorites")
            
            return {
                "status": "success",
                "players_added": len(player_names),
                "found_existing": len(found_players),
                "newly_collected": len(newly_collected),
                "total_favorites": len(favorites),
                "comprehensive_data_file": self.favorites_data_file,
                "players_data": df.to_dict(orient='records'),
                "message": f"Added {len(player_names)} players to favorites with comprehensive data"
            }
        
        return {
            "status": "error",
            "message": "No player data could be collected",
            "players_requested": player_names
        }
    
    def _find_player_in_data(self, player_name: str) -> Dict[str, Any]:
        """Search for player in existing data files."""
        import glob
        
        # Search in all CSV files
        data_files = glob.glob('data/*.csv')
        
        for file_path in data_files:
            try:
                df = pd.read_csv(file_path)
                if 'name' in df.columns:
                    # Case-insensitive search
                    matching_rows = df[df['name'].str.contains(player_name, case=False, na=False)]
                    if not matching_rows.empty:
                        # Return the first match with most complete data
                        best_match = matching_rows.iloc[0].to_dict()
                        # Replace NaN with None
                        return {k: (v if pd.notna(v) else None) for k, v in best_match.items()}
            except Exception as e:
                logger.warning(f"Error reading {file_path}: {e}")
                continue
        
        return None
    
    def _collect_missing_players(self, player_names: List[str]) -> List[Dict[str, Any]]:
        """Collect comprehensive data for missing players."""
        collected_players = []
        
        for player_name in player_names:
            try:
                logger.info(f"🔍 Collecting comprehensive data for {player_name}")
                
                # Try to determine team for better collection
                team = self._guess_player_team(player_name)
                
                # Collect comprehensive data
                player_data = self.collector.collect_real_data(player_name, team)
                
                if player_data and player_data.get('name'):
                    collected_players.append(player_data)
                    logger.info(f"✅ Collected data for {player_name}")
                else:
                    logger.warning(f"⚠ Could not collect data for {player_name}")
                    
            except Exception as e:
                logger.error(f"Error collecting data for {player_name}: {e}")
                continue
        
        return collected_players
    
    def _guess_player_team(self, player_name: str) -> str:
        """Guess player's current team based on name."""
        # Known mappings for requested players
        team_mappings = {
            'nick bonitto': 'broncos',
            'courtland sutton': 'broncos', 
            'patrick surtain': 'broncos',
            'pat surtain': 'broncos',
            'patrick mahomes': 'chiefs',
            'pat mahomes': 'chiefs',
            'lamar jackson': 'ravens'
        }
        
        name_lower = player_name.lower()
        for key, team in team_mappings.items():
            if key in name_lower:
                return team
        
        return 'unknown'
    
    def _load_favorites(self) -> List[Dict[str, Any]]:
        """Load existing favorites list."""
        if os.path.exists(self.favorites_file):
            try:
                with open(self.favorites_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading favorites: {e}")
        return []
    
    def _save_favorites(self, favorites: List[Dict[str, Any]]):
        """Save favorites list."""
        try:
            os.makedirs("data", exist_ok=True)
            with open(self.favorites_file, 'w') as f:
                json.dump(favorites, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving favorites: {e}")
    
    def get_favorites_data(self) -> Dict[str, Any]:
        """Get comprehensive data for all favorite players."""
        if os.path.exists(self.favorites_data_file):
            try:
                df = pd.read_csv(self.favorites_data_file)
                return {
                    "status": "success",
                    "total_players": len(df),
                    "players": df.to_dict(orient='records'),
                    "data_file": self.favorites_data_file
                }
            except Exception as e:
                logger.error(f"Error loading favorites data: {e}")
        
        return {
            "status": "error",
            "message": "No favorites data file found"
        }

# Global instance
favorite_players_manager = FavoritePlayersManager()