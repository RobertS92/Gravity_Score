"""Main MCP (Modular Content Pipeline) coordinator class."""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from .core.config import Config
from .core.utils import setup_logging, get_timestamp
from .core.exceptions import NFLGravityError, ConfigurationError
from .pipeline.orchestrator import PipelineOrchestrator
from .storage.writer import DataWriter


class MCP:
    """
    Main Modular Content Pipeline coordinator.
    
    This is the primary entry point for the NFL Gravity package, providing
    a unified interface to coordinate all pipeline stages.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the MCP coordinator.
        
        Args:
            config: Configuration object, creates default if None
        """
        self.config = config or Config()
        
        # Validate configuration
        validation_errors = self.config.validate()
        if validation_errors:
            # Log warnings but don't fail initialization
            for error in validation_errors:
                print(f"Configuration warning: {error}")
        
        # Set up logging
        self.logger = setup_logging(
            log_level=self.config.log_level,
            log_file=self.config.get_log_file()
        )
        
        self.logger.info("NFL Gravity MCP initialized")
        
        # Initialize components
        self.orchestrator = PipelineOrchestrator(self.config)
        self.data_writer = DataWriter(self.config)
        
        # MCP state tracking
        self.mcp_state = {
            'initialized_at': get_timestamp(),
            'total_runs': 0,
            'last_run': None,
            'last_result': None,
            'current_state': 'ready'
        }
    
    def run_pipeline(self, teams: List[str], fast_mode: bool = False, 
                    output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the complete NFL data extraction pipeline.
        
        Args:
            teams: List of team names to process
            fast_mode: Skip heavy LLM processing if True
            output_dir: Custom output directory (uses config default if None)
            
        Returns:
            Dictionary with pipeline results
            
        Raises:
            NFLGravityError: If pipeline execution fails
        """
        if not teams:
            raise ValueError("No teams specified for processing")
        
        # Validate teams
        invalid_teams = [team for team in teams if team.lower() not in self.config.nfl_teams]
        if invalid_teams:
            raise ValueError(f"Invalid teams specified: {', '.join(invalid_teams)}")
        
        self.logger.info(f"Starting MCP pipeline for {len(teams)} teams (fast_mode={fast_mode})")
        
        # Update state
        self.mcp_state['current_state'] = 'running'
        self.mcp_state['last_run'] = get_timestamp()
        
        try:
            # Run the orchestrated pipeline
            results = self.orchestrator.run_full_pipeline(
                teams=teams,
                fast_mode=fast_mode,
                output_dir=output_dir
            )
            
            # Update state with results
            self.mcp_state['current_state'] = 'completed'
            self.mcp_state['total_runs'] += 1
            self.mcp_state['last_result'] = results
            
            self.logger.info(f"MCP pipeline completed successfully: {results['total_players']} players, {results['total_teams']} teams")
            
            return results
            
        except Exception as e:
            self.mcp_state['current_state'] = 'failed'
            self.logger.error(f"MCP pipeline failed: {e}")
            raise NFLGravityError(f"Pipeline execution failed: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current MCP status.
        
        Returns:
            Dictionary with MCP status information
        """
        # Get orchestrator status
        pipeline_status = self.orchestrator.get_pipeline_status()
        
        # Combine with MCP state
        status = {
            'state': self.mcp_state['current_state'],
            'initialized_at': self.mcp_state['initialized_at'],
            'total_runs': self.mcp_state['total_runs'],
            'last_run': self.mcp_state['last_run'],
            'pipeline_status': pipeline_status,
            'config_valid': len(self.config.validate()) == 0,
            'data_directory': self.config.data_dir,
            'log_directory': self.config.log_dir
        }
        
        # Add last result summary if available
        if self.mcp_state['last_result']:
            last_result = self.mcp_state['last_result']
            status['last_result_summary'] = {
                'teams_processed': last_result.get('teams_processed', 0),
                'total_players': last_result.get('total_players', 0),
                'total_teams': last_result.get('total_teams', 0),
                'duration': last_result.get('duration', 0),
                'output_dir': last_result.get('output_dir'),
                'error_count': len(last_result.get('errors', []))
            }
        
        return status
    
    def get_latest_data_info(self) -> Dict[str, Any]:
        """
        Get information about the latest scraped data.
        
        Returns:
            Dictionary with latest data information
        """
        try:
            return self.data_writer.get_data_info()
        except Exception as e:
            self.logger.error(f"Error getting latest data info: {e}")
            return {'error': str(e)}
    
    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate the current configuration.
        
        Returns:
            Dictionary with validation results
        """
        validation_messages = self.config.validate()
        
        # Check component availability
        component_status = {}
        
        # Check LLM availability
        try:
            from .llm.adapter import LLMAdapter
            llm = LLMAdapter(self.config)
            component_status['llm'] = {
                'available': llm.is_available(),
                'provider_info': llm.get_provider_info()
            }
        except Exception as e:
            component_status['llm'] = {
                'available': False,
                'error': str(e)
            }
        
        # Check extractors
        try:
            component_status['extractors'] = {
                'wikipedia': self.config.enable_wikipedia,
                'social_media': self.config.enable_social_media,
                'nfl_sites': True  # Always available
            }
        except Exception as e:
            component_status['extractors'] = {'error': str(e)}
        
        return {
            'valid': len(validation_messages) == 0,
            'messages': validation_messages,
            'components': component_status,
            'config_summary': {
                'data_dir': self.config.data_dir,
                'log_dir': self.config.log_dir,
                'llm_provider': self.config.llm_provider,
                'output_formats': self.config.output_formats,
                'supported_teams': len(self.config.nfl_teams)
            }
        }
    
    def stop_pipeline(self):
        """Stop any running pipeline operations gracefully."""
        if self.mcp_state['current_state'] == 'running':
            self.logger.info("Stopping MCP pipeline...")
            self.orchestrator.stop_pipeline()
            self.mcp_state['current_state'] = 'stopped'
    
    def reset_state(self):
        """Reset MCP state (useful for testing)."""
        self.mcp_state.update({
            'total_runs': 0,
            'last_run': None,
            'last_result': None,
            'current_state': 'ready'
        })
        self.logger.info("MCP state reset")
    
    def get_supported_teams(self) -> List[str]:
        """
        Get list of supported NFL teams.
        
        Returns:
            List of supported team names
        """
        return self.config.nfl_teams.copy()
    
    def get_version_info(self) -> Dict[str, Any]:
        """
        Get version and package information.
        
        Returns:
            Dictionary with version information
        """
        try:
            from . import __version__, __author__
            
            return {
                'version': __version__,
                'author': __author__,
                'python_version': f"{__import__('sys').version_info.major}.{__import__('sys').version_info.minor}",
                'dependencies': self._get_dependency_versions()
            }
        except Exception as e:
            return {'error': f"Failed to get version info: {e}"}
    
    def _get_dependency_versions(self) -> Dict[str, str]:
        """Get versions of key dependencies."""
        dependencies = {}
        
        dep_names = [
            'pandas', 'requests', 'beautifulsoup4', 'pydantic', 
            'pyarrow', 'trafilatura', 'openai'
        ]
        
        for dep in dep_names:
            try:
                module = __import__(dep)
                version = getattr(module, '__version__', 'unknown')
                dependencies[dep] = version
            except ImportError:
                dependencies[dep] = 'not installed'
            except Exception:
                dependencies[dep] = 'error'
        
        return dependencies
    
    def run_health_check(self) -> Dict[str, Any]:
        """
        Run a comprehensive health check of the system.
        
        Returns:
            Dictionary with health check results
        """
        health = {
            'overall_healthy': True,
            'timestamp': get_timestamp(),
            'checks': {}
        }
        
        # Configuration check
        config_valid = len(self.config.validate()) == 0
        health['checks']['configuration'] = {
            'healthy': config_valid,
            'details': self.config.validate()
        }
        if not config_valid:
            health['overall_healthy'] = False
        
        # Directory access check
        try:
            import os
            dirs_ok = (os.access(self.config.data_dir, os.W_OK) and 
                      os.access(self.config.log_dir, os.W_OK))
            health['checks']['directories'] = {
                'healthy': dirs_ok,
                'data_dir_writable': os.access(self.config.data_dir, os.W_OK),
                'log_dir_writable': os.access(self.config.log_dir, os.W_OK)
            }
            if not dirs_ok:
                health['overall_healthy'] = False
        except Exception as e:
            health['checks']['directories'] = {
                'healthy': False,
                'error': str(e)
            }
            health['overall_healthy'] = False
        
        # Network connectivity check (basic)
        try:
            import requests
            response = requests.get('https://httpbin.org/status/200', timeout=5)
            network_ok = response.status_code == 200
            health['checks']['network'] = {
                'healthy': network_ok,
                'details': 'Basic connectivity test passed'
            }
        except Exception as e:
            health['checks']['network'] = {
                'healthy': False,
                'error': str(e)
            }
            # Network issues don't fail overall health (might be expected)
        
        # LLM availability check
        try:
            from .llm.adapter import LLMAdapter
            llm = LLMAdapter(self.config)
            llm_ok = llm.is_available() if self.config.enable_llm else True
            health['checks']['llm'] = {
                'healthy': llm_ok,
                'enabled': self.config.enable_llm,
                'provider': llm.primary_provider if llm.is_available() else None
            }
        except Exception as e:
            health['checks']['llm'] = {
                'healthy': False,
                'error': str(e)
            }
            # LLM issues don't fail overall health (optional feature)
        
        return health
