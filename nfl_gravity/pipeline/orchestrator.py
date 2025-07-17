"""Main pipeline orchestrator for NFL Gravity."""

import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..core.config import Config
from ..core.exceptions import NFLGravityError
from ..core.validators import PlayerDataValidator, TeamDataValidator
from ..core.utils import create_output_directory, get_timestamp
from ..extractors.wikipedia import WikipediaExtractor
from ..extractors.social_media import SocialMediaExtractor
from ..extractors.nfl_sites import NFLSitesExtractor
from ..storage.writer import DataWriter


class PipelineOrchestrator:
    """Main orchestrator for the NFL data extraction pipeline."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger("nfl_gravity.pipeline")
        
        # Initialize extractors
        self.wikipedia_extractor = WikipediaExtractor(config)
        self.social_media_extractor = SocialMediaExtractor(config)
        self.nfl_sites_extractor = NFLSitesExtractor(config)
        
        # Initialize validators
        self.player_validator = PlayerDataValidator()
        self.team_validator = TeamDataValidator()
        
        # Initialize data writer
        self.data_writer = DataWriter(config)
        
        # Pipeline state
        self.pipeline_state = {
            'status': 'ready',
            'current_team': None,
            'progress': 0,
            'total_teams': 0,
            'start_time': None,
            'end_time': None,
            'errors': []
        }
    
    def run_full_pipeline(self, teams: List[str], fast_mode: bool = False, 
                         output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the complete NFL data extraction pipeline.
        
        Args:
            teams: List of team names to process
            fast_mode: Skip heavy LLM processing if True
            output_dir: Custom output directory
            
        Returns:
            Dictionary with pipeline results
        """
        self.logger.info(f"Starting NFL Gravity pipeline for {len(teams)} teams")
        
        # Initialize pipeline state
        self.pipeline_state.update({
            'status': 'running',
            'total_teams': len(teams),
            'progress': 0,
            'start_time': get_timestamp(),
            'errors': []
        })
        
        # Create output directory
        if not output_dir:
            output_dir = create_output_directory(self.config.data_dir)
        
        all_players = []
        all_teams = []
        
        try:
            # Process each team
            for i, team in enumerate(teams):
                self.logger.info(f"Processing team {i+1}/{len(teams)}: {team}")
                self.pipeline_state['current_team'] = team
                self.pipeline_state['progress'] = (i / len(teams)) * 100
                
                try:
                    # Extract team data
                    team_data = self._process_team(team, fast_mode)
                    if team_data:
                        all_teams.append(team_data)
                    
                    # Extract player data for the team
                    team_players = self._process_team_players(team, fast_mode)
                    all_players.extend(team_players)
                    
                    self.logger.info(f"Completed {team}: {len(team_players)} players processed")
                    
                except Exception as e:
                    error_msg = f"Error processing team {team}: {e}"
                    self.logger.error(error_msg)
                    self.pipeline_state['errors'].append(error_msg)
                    continue
            
            # Write results to files
            output_files = self.data_writer.write_data(
                players=all_players,
                teams=all_teams,
                output_dir=output_dir
            )
            
            # Update pipeline state
            self.pipeline_state.update({
                'status': 'completed',
                'end_time': get_timestamp(),
                'progress': 100
            })
            
            results = {
                'status': 'success',
                'teams_processed': len(teams) - len([e for e in self.pipeline_state['errors'] if 'Error processing team' in e]),
                'total_players': len(all_players),
                'total_teams': len(all_teams),
                'output_files': output_files,
                'output_dir': output_dir,
                'duration': self._calculate_duration(),
                'errors': self.pipeline_state['errors']
            }
            
            self.logger.info(f"Pipeline completed successfully: {results}")
            return results
            
        except Exception as e:
            self.pipeline_state.update({
                'status': 'failed',
                'end_time': get_timestamp()
            })
            
            error_msg = f"Pipeline failed: {e}"
            self.logger.error(error_msg)
            raise NFLGravityError(error_msg)
    
    def _process_team(self, team: str, fast_mode: bool = False) -> Optional[Dict[str, Any]]:
        """
        Process a single team to extract team-level data.
        
        Args:
            team: Team name
            fast_mode: Skip heavy processing if True
            
        Returns:
            Validated team data or None if processing fails
        """
        try:
            team_data = {
                'name': team,
                'scraped_at': datetime.utcnow()
            }
            
            # Extract social media data for the team
            if self.config.enable_social_media and not fast_mode:
                social_data = self.social_media_extractor.extract_team_social_data(team)
                team_data.update(social_data)
            
            # Validate team data
            validated_team = self.team_validator.validate_and_clean(team_data)
            
            if validated_team:
                return validated_team.dict()
            else:
                self.logger.warning(f"Team data validation failed for {team}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error processing team {team}: {e}")
            return None
    
    def _process_team_players(self, team: str, fast_mode: bool = False) -> List[Dict[str, Any]]:
        """
        Process all players for a team.
        
        Args:
            team: Team name
            fast_mode: Skip heavy processing if True
            
        Returns:
            List of validated player data
        """
        players = []
        
        try:
            # Use enhanced scraper to extract complete roster (93+ players)
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            from enhanced_nfl_scraper import EnhancedNFLScraper
            enhanced_scraper = EnhancedNFLScraper()
            roster_data = enhanced_scraper.extract_complete_team_roster(team)
            
            if not roster_data:
                self.logger.warning(f"No roster data found for {team}")
                return players
            
            # Process players with threading for better performance
            max_workers = min(5, len(roster_data))  # Limit concurrent requests
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_player = {
                    executor.submit(self._process_single_player, player_data, team, fast_mode): player_data
                    for player_data in roster_data  # Process all players in roster
                }
                
                for future in as_completed(future_to_player):
                    original_player = future_to_player[future]
                    try:
                        processed_player = future.result()
                        if processed_player:
                            players.append(processed_player)
                    except Exception as e:
                        self.logger.error(f"Error processing player {original_player.get('name', 'unknown')}: {e}")
            
            return players
            
        except Exception as e:
            self.logger.error(f"Error processing players for team {team}: {e}")
            return []
    
    def _process_single_player(self, player_data: Dict[str, Any], team: str, 
                              fast_mode: bool = False) -> Optional[Dict[str, Any]]:
        """
        Process a single player with full data enrichment.
        
        Args:
            player_data: Initial player data from roster
            team: Team name
            fast_mode: Skip heavy processing if True
            
        Returns:
            Enriched and validated player data or None if processing fails
        """
        try:
            player_name = player_data.get('name', '')
            if not player_name:
                return None
            
            # Start with roster data
            enriched_data = player_data.copy()
            enriched_data.update({
                'team': team,
                'scraped_at': datetime.utcnow()
            })
            
            # Wikipedia enrichment
            if self.config.enable_wikipedia and not fast_mode:
                try:
                    wikipedia_url = self.wikipedia_extractor.search_player(player_name, team)
                    if wikipedia_url:
                        wikipedia_data = self.wikipedia_extractor.extract_player_data(wikipedia_url)
                        enriched_data.update(wikipedia_data)
                except Exception as e:
                    self.logger.warning(f"Wikipedia extraction failed for {player_name}: {e}")
            
            # Social media enrichment
            if self.config.enable_social_media and not fast_mode:
                try:
                    social_data = self.social_media_extractor.discover_social_profiles(player_name, team)
                    enriched_data.update(social_data)
                except Exception as e:
                    self.logger.warning(f"Social media extraction failed for {player_name}: {e}")
            
            # Validate and clean data
            validated_player = self.player_validator.validate_and_clean(enriched_data)
            
            if validated_player:
                return validated_player.dict()
            else:
                self.logger.warning(f"Player data validation failed for {player_name}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error processing player {player_data.get('name', 'unknown')}: {e}")
            return None
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """
        Get current pipeline status.
        
        Returns:
            Dictionary with current pipeline status
        """
        return self.pipeline_state.copy()
    
    def _calculate_duration(self) -> Optional[float]:
        """Calculate pipeline duration in seconds."""
        if self.pipeline_state['start_time'] and self.pipeline_state['end_time']:
            start = datetime.fromisoformat(self.pipeline_state['start_time'])
            end = datetime.fromisoformat(self.pipeline_state['end_time'])
            return (end - start).total_seconds()
        return None
    
    def stop_pipeline(self):
        """Stop the running pipeline gracefully."""
        if self.pipeline_state['status'] == 'running':
            self.pipeline_state['status'] = 'stopped'
            self.pipeline_state['end_time'] = get_timestamp()
            self.logger.info("Pipeline stopped by user request")
