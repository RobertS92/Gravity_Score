#!/usr/bin/env python3
"""
Draft Data Validator
====================

Validates and supplements draft data from Pro Football Reference.
Checks if players marked as "Undrafted" actually were drafted.

Usage:
    python draft_data_validator.py input.csv output.csv
    python draft_data_validator.py nfl_players.csv validated.csv --years 2020-2024

Author: Gravity Score Team
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Optional
import time
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# DRAFT DATA VALIDATOR
# ============================================================================

class DraftDataValidator:
    """Validate and supplement draft data from Pro Football Reference"""
    
    def __init__(self):
        """Initialize validator"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.draft_cache = {}
    
    def load_draft_data(self, start_year: int = 2000, end_year: int = 2024):
        """
        Load draft data from Pro Football Reference
        
        Args:
            start_year: First year to load
            end_year: Last year to load
        """
        logger.info(f"Loading draft data from PFR ({start_year}-{end_year})...")
        
        for year in range(start_year, end_year + 1):
            try:
                url = f"https://www.pro-football-reference.com/years/{year}/draft.htm"
                logger.info(f"  Fetching {year} draft...")
                
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    draft_table = soup.find('table', {'id': 'drafts'})
                    
                    if draft_table:
                        rows = draft_table.find_all('tr')
                        
                        draft_count = 0
                        for row in rows:
                            # Skip header rows
                            if row.find('th', {'scope': 'row'}):
                                cells = row.find_all('td')
                                
                                if len(cells) >= 3:
                                    # Round
                                    round_cell = row.find('th', {'data-stat': 'draft_round'})
                                    round_num = round_cell.get_text(strip=True) if round_cell else None
                                    
                                    # Pick
                                    pick_cell = row.find('td', {'data-stat': 'draft_pick'})
                                    pick_num = pick_cell.get_text(strip=True) if pick_cell else None
                                    
                                    # Player name
                                    name_cell = row.find('td', {'data-stat': 'player'})
                                    if name_cell:
                                        player_link = name_cell.find('a')
                                        if player_link:
                                            player_name = player_link.get_text(strip=True)
                                            
                                            # Team
                                            team_cell = row.find('td', {'data-stat': 'team'})
                                            team = team_cell.get_text(strip=True) if team_cell else ''
                                            
                                            # Position
                                            pos_cell = row.find('td', {'data-stat': 'pos'})
                                            position = pos_cell.get_text(strip=True) if pos_cell else ''
                                            
                                            # Store in cache
                                            if player_name:
                                                # Normalize name for matching
                                                name_key = self._normalize_name(player_name)
                                                
                                                self.draft_cache[name_key] = {
                                                    'player_name': player_name,
                                                    'draft_year': year,
                                                    'draft_round': int(round_num) if round_num and round_num.isdigit() else None,
                                                    'draft_pick': int(pick_num) if pick_num and pick_num.isdigit() else None,
                                                    'draft_team': team,
                                                    'position': position
                                                }
                                                draft_count += 1
                        
                        logger.info(f"    ✅ Loaded {draft_count} players from {year}")
                    else:
                        logger.warning(f"    ⚠️  No draft table found for {year}")
                else:
                    logger.warning(f"    ⚠️  Failed to fetch {year} (status {response.status_code})")
                
                # Rate limit
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"    ❌ Error loading {year}: {e}")
        
        logger.info(f"✅ Loaded {len(self.draft_cache)} total draft picks\n")
    
    def _normalize_name(self, name: str) -> str:
        """Normalize player name for matching"""
        # Remove suffixes
        name = re.sub(r'\s+(Jr\.|Sr\.|II|III|IV)\.?$', '', name, flags=re.IGNORECASE)
        
        # Remove special characters
        name = name.replace('.', '').replace("'", '').replace('-', ' ')
        
        # Lowercase and strip
        name = name.lower().strip()
        
        return name
    
    def validate_player(self, player_name: str, draft_year, draft_round, draft_pick) -> Dict:
        """
        Validate draft data for a single player
        
        Args:
            player_name: Player's name
            draft_year: Current draft year value (may be "Undrafted")
            draft_round: Current draft round value (may be "Undrafted")
            draft_pick: Current draft pick value (may be "Undrafted")
            
        Returns:
            Dict with validated draft data (or original if no changes)
        """
        name_key = self._normalize_name(player_name)
        
        # Check if we have draft data for this player
        if name_key in self.draft_cache:
            pfr_data = self.draft_cache[name_key]
            
            # If currently marked as Undrafted but PFR has draft data
            if draft_year == "Undrafted" or draft_round == "Undrafted":
                return {
                    'draft_year': pfr_data['draft_year'],
                    'draft_round': pfr_data['draft_round'],
                    'draft_pick': pfr_data['draft_pick'],
                    'source': 'PFR (corrected)',
                    'was_incorrect': True
                }
            
            # If draft data exists but differs from PFR
            elif draft_year and draft_year != pfr_data['draft_year']:
                logger.warning(f"  {player_name}: ESPN says {draft_year}, PFR says {pfr_data['draft_year']}")
                return {
                    'draft_year': pfr_data['draft_year'],
                    'draft_round': pfr_data['draft_round'],
                    'draft_pick': pfr_data['draft_pick'],
                    'source': 'PFR (conflicting data)',
                    'was_incorrect': True
                }
        
        # No changes needed
        return {
            'draft_year': draft_year,
            'draft_round': draft_round,
            'draft_pick': draft_pick,
            'source': 'original',
            'was_incorrect': False
        }
    
    def validate_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validate draft data for all players in DataFrame
        
        Args:
            df: DataFrame with draft columns
            
        Returns:
            DataFrame with validated draft data
        """
        logger.info(f"Validating draft data for {len(df)} players...")
        
        corrections = 0
        missing_data = 0
        
        # Track original values
        df['original_draft_year'] = df.get('draft_year', df.get('identity.draft_year'))
        
        for idx, row in df.iterrows():
            player_name = row.get('player_name', '')
            
            # Get current draft data (check both flat and nested columns)
            draft_year = row.get('draft_year', row.get('identity.draft_year'))
            draft_round = row.get('draft_round', row.get('identity.draft_round'))
            draft_pick = row.get('draft_pick', row.get('identity.draft_pick'))
            
            # Validate
            validated = self.validate_player(player_name, draft_year, draft_round, draft_pick)
            
            if validated['was_incorrect']:
                corrections += 1
                logger.info(f"  ✓ Corrected: {player_name} - {validated['draft_year']} R{validated['draft_round']} #{validated['draft_pick']}")
                
                # Update DataFrame
                if 'draft_year' in df.columns:
                    df.at[idx, 'draft_year'] = validated['draft_year']
                    df.at[idx, 'draft_round'] = validated['draft_round']
                    df.at[idx, 'draft_pick'] = validated['draft_pick']
                
                if 'identity.draft_year' in df.columns:
                    df.at[idx, 'identity.draft_year'] = validated['draft_year']
                    df.at[idx, 'identity.draft_round'] = validated['draft_round']
                    df.at[idx, 'identity.draft_pick'] = validated['draft_pick']
                
                # Add source column
                if 'draft_data_source' not in df.columns:
                    df['draft_data_source'] = 'original'
                df.at[idx, 'draft_data_source'] = validated['source']
            
            elif draft_year == "Undrafted" or draft_year is None or pd.isna(draft_year):
                missing_data += 1
        
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ VALIDATION COMPLETE")
        logger.info(f"{'='*80}")
        logger.info(f"Total players: {len(df)}")
        logger.info(f"Corrections made: {corrections}")
        logger.info(f"Still missing draft data: {missing_data}")
        logger.info(f"{'='*80}\n")
        
        return df


# ============================================================================
# CLI
# ============================================================================

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Draft Data Validator - Validate/correct draft data from Pro Football Reference",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate all draft data (2000-2024)
  python draft_data_validator.py nfl_players.csv validated.csv
  
  # Only check recent years
  python draft_data_validator.py players.csv output.csv --years 2020-2024
  
  # Check specific year range
  python draft_data_validator.py players.csv output.csv --start 2015 --end 2023

Speed:
  ~30 seconds to load all drafts (2000-2024)
  ~1 second to validate 1000 players after loading
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='Input CSV file with player_name and draft columns'
    )
    
    parser.add_argument(
        'output',
        type=str,
        help='Output CSV file with validated draft data'
    )
    
    parser.add_argument(
        '--start',
        type=int,
        default=2000,
        help='Start year for draft data (default: 2000)'
    )
    
    parser.add_argument(
        '--end',
        type=int,
        default=2024,
        help='End year for draft data (default: 2024)'
    )
    
    parser.add_argument(
        '--years',
        type=str,
        help='Year range (e.g., "2020-2024") - shorthand for --start and --end'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Parse year range
    if args.years:
        try:
            start, end = map(int, args.years.split('-'))
            args.start = start
            args.end = end
        except:
            logger.error(f"Invalid year range: {args.years}. Use format: 2020-2024")
            sys.exit(1)
    
    # Load input data
    logger.info(f"Loading {args.input}...")
    df = pd.read_csv(args.input)
    
    if 'player_name' not in df.columns:
        logger.error("Input CSV must have 'player_name' column")
        sys.exit(1)
    
    logger.info(f"Loaded {len(df)} players\n")
    
    # Initialize validator
    validator = DraftDataValidator()
    
    # Load draft data
    validator.load_draft_data(start_year=args.start, end_year=args.end)
    
    # Validate
    df_validated = validator.validate_dataframe(df)
    
    # Save results
    df_validated.to_csv(args.output, index=False)
    logger.info(f"✅ Results saved to: {args.output}")


if __name__ == '__main__':
    main()

