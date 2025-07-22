"""
Simple Comprehensive Collector - Fast production-ready comprehensive data collection
No AI enhancement, focuses on authentic data from reliable sources
"""

import logging
import requests
import re
from typing import Dict, Optional
from enhanced_nfl_scraper import EnhancedNFLScraper

logger = logging.getLogger(__name__)

class SimpleComprehensiveCollector:
    """Fast comprehensive data collector for production use."""
    
    def __init__(self):
        self.roster_scraper = EnhancedNFLScraper()
        
    def collect_player_data(self, player_name: str, team: str) -> Optional[Dict]:
        """Collect comprehensive player data quickly without AI enhancement."""
        try:
            logger.info(f"Fast comprehensive collection: {player_name} ({team})")
            
            # Get basic roster data first
            roster = self.roster_scraper.extract_roster(team)
            if not roster:
                return None
            
            # Find player in roster
            player_data = None
            for player in roster:
                if player.get('name', '').lower() == player_name.lower():
                    player_data = player.copy()
                    break
            
            if not player_data:
                # Create basic structure if not found
                player_data = {
                    'name': player_name,
                    'team': team,
                    'current_team': team
                }
            
            # Enhance with additional fields quickly
            self._add_quick_enhancements(player_data, player_name, team)
            
            # Calculate data quality
            filled_fields = len([v for v in player_data.values() if v is not None and str(v).strip() != ''])
            total_fields = len(player_data)
            quality_score = (filled_fields / total_fields) * 5.0
            
            player_data['data_quality'] = round(quality_score, 2)
            player_data['fields_filled'] = filled_fields
            player_data['collection_method'] = 'simple_comprehensive'
            
            logger.info(f"✅ {player_name}: {filled_fields} fields, {quality_score:.1f}/5.0 quality")
            
            return player_data
            
        except Exception as e:
            logger.error(f"Error collecting data for {player_name}: {e}")
            return None
    
    def _add_quick_enhancements(self, player_data: Dict, player_name: str, team: str):
        """Add quick enhancements without heavy API calls."""
        
        # Add team-specific data
        player_data['current_team'] = team
        
        # Initialize comprehensive fields with empty values
        comprehensive_fields = [
            'age', 'birth_date', 'birth_place', 'college', 'high_school',
            'experience', 'draft_year', 'draft_round', 'draft_pick',
            'twitter_handle', 'instagram_handle', 'twitter_followers', 'instagram_followers',
            'pro_bowls', 'all_pros', 'championships', 'awards',
            'contract_value', 'current_salary', 'guaranteed_money',
            'career_games', 'career_starts', 'injuries', 'status'
        ]
        
        for field in comprehensive_fields:
            if field not in player_data:
                player_data[field] = None
        
        # Quick position-specific defaults
        position = player_data.get('position', '').upper()
        if position == 'QB':
            player_data['career_pass_yards'] = None
            player_data['career_pass_tds'] = None
            player_data['career_pass_rating'] = None
        elif position in ['RB', 'FB']:
            player_data['career_rush_yards'] = None
            player_data['career_rush_tds'] = None
            player_data['career_rush_avg'] = None
        elif position in ['WR', 'TE']:
            player_data['career_rec_yards'] = None
            player_data['career_receptions'] = None
            player_data['career_rec_tds'] = None
        
        # Quick team success factors
        championship_teams = ['chiefs', 'buccaneers', 'rams', 'broncos', 'seahawks', 'ravens', 'patriots']
        if team.lower() in championship_teams:
            player_data['team_success_factor'] = 'high'
        else:
            player_data['team_success_factor'] = 'medium'
        
        # Market size estimate
        large_markets = ['cowboys', 'giants', 'jets', 'rams', 'chargers', 'bears', 'eagles', '49ers']
        if team.lower() in large_markets:
            player_data['market_size'] = 'large'
        else:
            player_data['market_size'] = 'medium'
        
        logger.debug(f"Added quick enhancements for {player_name}")

# Global instance
simple_comprehensive_collector = SimpleComprehensiveCollector()