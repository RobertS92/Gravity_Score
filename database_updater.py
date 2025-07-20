#!/usr/bin/env python3
"""
Database Updater - Updates existing player records with new data
Handles database updates when re-scraping players with improved data.
"""

import pandas as pd
import os
import glob
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseUpdater:
    """Handles updating existing player records with new scraped data."""
    
    def __init__(self):
        self.data_dir = "data"
        os.makedirs(self.data_dir, exist_ok=True)
    
    def update_player_database(self, new_players: List[Dict[str, Any]], 
                              update_mode: str = "merge") -> Dict[str, Any]:
        """
        Update the player database with new data.
        
        Args:
            new_players: List of new player data dictionaries
            update_mode: 'merge' (update existing) or 'replace' (replace entirely)
        
        Returns:
            Dictionary with update statistics
        """
        try:
            # Find existing database file
            existing_data = self._load_existing_data()
            
            if existing_data is None or len(existing_data) == 0:
                # No existing data, create new
                logger.info("No existing data found, creating new database")
                return self._save_new_data(new_players)
            
            # Perform update based on mode
            if update_mode == "merge":
                updated_data = self._merge_player_data(existing_data, new_players)
            else:  # replace
                updated_data = new_players
            
            # Save updated data
            return self._save_updated_data(updated_data, len(existing_data), len(new_players))
            
        except Exception as e:
            logger.error(f"Error updating database: {e}")
            return {"status": "error", "message": str(e)}
    
    def _load_existing_data(self) -> Optional[List[Dict[str, Any]]]:
        """Load the most recent player data file."""
        try:
            # Find all player data files
            all_files = (glob.glob(f'{self.data_dir}/players_*.csv') + 
                        glob.glob(f'{self.data_dir}/comprehensive_players_*.csv'))
            
            if not all_files:
                return None
            
            # Get the file with the most players
            largest_file = None
            max_players = 0
            
            for file_path in all_files:
                df = pd.read_csv(file_path)
                if len(df) > max_players:
                    max_players = len(df)
                    largest_file = file_path
            
            if largest_file:
                df = pd.read_csv(largest_file)
                logger.info(f"Loaded existing data: {len(df)} players from {os.path.basename(largest_file)}")
                return df.to_dict('records')
            
            return None
            
        except Exception as e:
            logger.error(f"Error loading existing data: {e}")
            return None
    
    def _merge_player_data(self, existing_players: List[Dict[str, Any]], 
                          new_players: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge new player data with existing data.
        New data takes precedence for non-empty values.
        """
        logger.info(f"Merging {len(new_players)} new players with {len(existing_players)} existing players")
        
        # Create lookup for existing players by name and team
        existing_lookup = {}
        for player in existing_players:
            key = self._make_player_key(player)
            existing_lookup[key] = player
        
        updated_players = []
        new_count = 0
        updated_count = 0
        
        # Process new players
        for new_player in new_players:
            key = self._make_player_key(new_player)
            
            if key in existing_lookup:
                # Update existing player
                existing_player = existing_lookup[key].copy()
                
                # Track if any field was actually updated
                was_updated = False
                
                for field, new_value in new_player.items():
                    if new_value and new_value != existing_player.get(field):
                        if field == 'height' and existing_player.get('height'):
                            # Special handling for height - always update if new height is realistic
                            if self._is_realistic_height(new_value):
                                logger.info(f"Updating {new_player.get('name', 'Unknown')} height: "
                                          f"{existing_player.get('height')} -> {new_value}")
                                existing_player[field] = new_value
                                was_updated = True
                        elif not existing_player.get(field) or existing_player.get(field) == '':
                            # Update empty/missing fields
                            existing_player[field] = new_value
                            was_updated = True
                        elif field in ['scraped_at', 'data_source']:
                            # Always update metadata fields
                            existing_player[field] = new_value
                            was_updated = True
                
                if was_updated:
                    existing_player['last_updated'] = datetime.now().isoformat()
                    updated_count += 1
                
                updated_players.append(existing_player)
                # Remove from lookup so we don't add duplicates
                del existing_lookup[key]
                
            else:
                # New player
                new_player['last_updated'] = datetime.now().isoformat()
                updated_players.append(new_player)
                new_count += 1
        
        # Add remaining existing players that weren't updated
        for remaining_player in existing_lookup.values():
            updated_players.append(remaining_player)
        
        logger.info(f"Merge complete: {new_count} new players, {updated_count} updated players, "
                   f"{len(updated_players)} total players")
        
        return updated_players
    
    def _make_player_key(self, player: Dict[str, Any]) -> str:
        """Create a unique key for player identification."""
        name = player.get('name', '').lower().strip()
        team = player.get('team', '').lower().strip()
        position = player.get('position', '').lower().strip()
        return f"{name}|{team}|{position}"
    
    def _is_realistic_height(self, height: str) -> bool:
        """Check if height is realistic (between 5'0" and 7'0")."""
        if not height or not isinstance(height, str):
            return False
        
        import re
        match = re.search(r"(\d+)'(\d+)\"", height)
        if match:
            feet, inches = int(match.group(1)), int(match.group(2))
            total_inches = feet * 12 + inches
            # Realistic NFL player height: 60" (5'0") to 84" (7'0")
            return 60 <= total_inches <= 84
        
        return False
    
    def _save_new_data(self, players: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Save new player data to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save to CSV
        df = pd.DataFrame(players)
        csv_filename = f"{self.data_dir}/players_{timestamp}.csv"
        df.to_csv(csv_filename, index=False)
        
        logger.info(f"Saved {len(players)} new players to {csv_filename}")
        
        return {
            "status": "success",
            "action": "created_new",
            "total_players": len(players),
            "new_players": len(players),
            "updated_players": 0,
            "output_file": csv_filename
        }
    
    def _save_updated_data(self, players: List[Dict[str, Any]], 
                          old_count: int, new_count: int) -> Dict[str, Any]:
        """Save updated player data to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save to CSV
        df = pd.DataFrame(players)
        csv_filename = f"{self.data_dir}/players_updated_{timestamp}.csv"
        df.to_csv(csv_filename, index=False)
        
        # Also save as main players file
        main_filename = f"{self.data_dir}/players_{timestamp}.csv"
        df.to_csv(main_filename, index=False)
        
        logger.info(f"Updated database: {len(players)} total players saved to {main_filename}")
        
        return {
            "status": "success",
            "action": "updated_existing",
            "total_players": len(players),
            "old_count": old_count,
            "new_count": new_count,
            "output_files": [main_filename, csv_filename]
        }


def main():
    """Test the database updater."""
    updater = DatabaseUpdater()
    
    # Test with some sample data
    test_players = [
        {
            "name": "Patrick Mahomes",
            "team": "chiefs",
            "position": "QB",
            "height": "6'3\"",  # Corrected height
            "weight": 230,
            "data_source": "nfl.com",
            "scraped_at": datetime.now().isoformat()
        }
    ]
    
    result = updater.update_player_database(test_players, "merge")
    print(f"Update result: {result}")


if __name__ == "__main__":
    main()