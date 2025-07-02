"""Tests for pipeline orchestration."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from datetime import datetime

from nfl_gravity.core.config import Config
from nfl_gravity.pipeline.orchestrator import PipelineOrchestrator
from nfl_gravity.pipeline.schedulers import SimpleScheduler, ScheduleFrequency
from nfl_gravity.mcp import MCP
from nfl_gravity.core.exceptions import NFLGravityError


@pytest.fixture
def config():
    """Test configuration with temporary directories."""
    config = Config()
    
    # Use temporary directories for testing
    config.data_dir = tempfile.mkdtemp()
    config.log_dir = tempfile.mkdtemp()
    
    return config


@pytest.fixture
def mock_extractors():
    """Mock extractors for testing."""
    wiki_mock = Mock()
    wiki_mock.search_player.return_value = None
    wiki_mock.extract_player_data.return_value = {'data_source': 'wikipedia'}
    
    social_mock = Mock()
    social_mock.discover_social_profiles.return_value = {'data_source': 'social_media'}
    social_mock.extract_team_social_data.return_value = {'data_source': 'team_social'}
    
    nfl_mock = Mock()
    nfl_mock.extract_team_roster.return_value = [
        {
            'name': 'Test Player',
            'position': 'QB',
            'jersey_number': 12,
            'data_source': 'nfl.com'
        }
    ]
    
    return {
        'wikipedia': wiki_mock,
        'social_media': social_mock,
        'nfl_sites': nfl_mock
    }


class TestPipelineOrchestrator:
    """Test pipeline orchestration."""
    
    def test_init(self, config):
        """Test orchestrator initialization."""
        orchestrator = PipelineOrchestrator(config)
        
        assert orchestrator.config == config
        assert orchestrator.wikipedia_extractor is not None
        assert orchestrator.social_media_extractor is not None
        assert orchestrator.nfl_sites_extractor is not None
        assert orchestrator.player_validator is not None
        assert orchestrator.team_validator is not None
        assert orchestrator.data_writer is not None
    
    def test_pipeline_state_initialization(self, config):
        """Test pipeline state initialization."""
        orchestrator = PipelineOrchestrator(config)
        
        state = orchestrator.get_pipeline_status()
        
        assert state['status'] == 'ready'
        assert state['progress'] == 0
        assert state['total_teams'] == 0
        assert state['current_team'] is None
        assert isinstance(state['errors'], list)
    
    @patch('nfl_gravity.pipeline.orchestrator.PipelineOrchestrator._process_team')
    @patch('nfl_gravity.pipeline.orchestrator.PipelineOrchestrator._process_team_players')
    def test_run_full_pipeline_success(self, mock_process_players, mock_process_team, config):
        """Test successful full pipeline run."""
        # Mock return values
        mock_process_team.return_value = {
            'name': 'chiefs',
            'data_source': 'test'
        }
        
        mock_process_players.return_value = [
            {
                'name': 'Test Player',
                'team': 'chiefs',
                'position': 'QB',
                'data_source': 'test'
            }
        ]
        
        orchestrator = PipelineOrchestrator(config)
        
        # Mock data writer
        orchestrator.data_writer.write_data = Mock(return_value={
            'players': ['test_players.parquet'],
            'teams': ['test_teams.parquet']
        })
        
        result = orchestrator.run_full_pipeline(['chiefs'], fast_mode=True)
        
        assert result['status'] == 'success'
        assert result['teams_processed'] == 1
        assert result['total_players'] == 1
        assert result['total_teams'] == 1
        assert 'output_files' in result
        assert 'duration' in result
    
    def test_run_full_pipeline_empty_teams(self, config):
        """Test pipeline with empty teams list."""
        orchestrator = PipelineOrchestrator(config)
        
        result = orchestrator.run_full_pipeline([], fast_mode=True)
        
        assert result['teams_processed'] == 0
        assert result['total_players'] == 0
        assert result['total_teams'] == 0
    
    def test_get_pipeline_status(self, config):
        """Test getting pipeline status."""
        orchestrator = PipelineOrchestrator(config)
        
        status = orchestrator.get_pipeline_status()
        
        assert 'status' in status
        assert 'progress' in status
        assert 'total_teams' in status
        assert 'current_team' in status
        assert 'start_time' in status
        assert 'errors' in status
    
    def test_stop_pipeline(self, config):
        """Test stopping pipeline."""
        orchestrator = PipelineOrchestrator(config)
        
        # Simulate running state
        orchestrator.pipeline_state['status'] = 'running'
        
        orchestrator.stop_pipeline()
        
        assert orchestrator.pipeline_state['status'] == 'stopped'


class TestSimpleScheduler:
    """Test simple scheduler functionality."""
    
    def test_init(self, config):
        """Test scheduler initialization."""
        scheduler = SimpleScheduler(config)
        
        assert scheduler.config == config
        assert scheduler._scheduled_jobs == []
        assert scheduler._running is False
        assert scheduler._scheduler_thread is None
    
    def test_schedule_pipeline(self, config):
        """Test scheduling a pipeline job."""
        scheduler = SimpleScheduler(config)
        
        # Mock pipeline function
        mock_pipeline = Mock(return_value={'status': 'success'})
        
        job_id = scheduler.schedule_pipeline(
            mock_pipeline,
            ['chiefs', 'patriots'],
            ScheduleFrequency.DAILY,
            job_name='test_job'
        )
        
        assert job_id is not None
        assert len(scheduler._scheduled_jobs) == 1
        assert scheduler._running is True
        
        # Clean up
        scheduler.stop()
    
    def test_get_job_status(self, config):
        """Test getting job status."""
        scheduler = SimpleScheduler(config)
        
        mock_pipeline = Mock()
        job_id = scheduler.schedule_pipeline(
            mock_pipeline,
            ['chiefs'],
            ScheduleFrequency.ONCE,
            job_name='status_test'
        )
        
        status = scheduler.get_job_status(job_id)
        
        assert status is not None
        assert status['id'] == job_id
        assert status['name'] == 'status_test'
        assert status['frequency'] == 'once'
        
        scheduler.stop()
    
    def test_list_jobs(self, config):
        """Test listing all jobs."""
        scheduler = SimpleScheduler(config)
        
        mock_pipeline = Mock()
        
        # Schedule multiple jobs
        job1 = scheduler.schedule_pipeline(mock_pipeline, ['chiefs'], ScheduleFrequency.DAILY)
        job2 = scheduler.schedule_pipeline(mock_pipeline, ['patriots'], ScheduleFrequency.WEEKLY)
        
        jobs = scheduler.list_jobs()
        
        assert len(jobs) == 2
        assert all(job is not None for job in jobs)
        
        scheduler.stop()
    
    def test_cancel_job(self, config):
        """Test canceling a job."""
        scheduler = SimpleScheduler(config)
        
        mock_pipeline = Mock()
        job_id = scheduler.schedule_pipeline(mock_pipeline, ['chiefs'], ScheduleFrequency.DAILY)
        
        # Cancel the job
        result = scheduler.cancel_job(job_id)
        
        assert result is True
        assert len(scheduler._scheduled_jobs) == 0
        
        # Try to cancel non-existent job
        result = scheduler.cancel_job('non_existent')
        assert result is False
        
        scheduler.stop()
    
    def test_scheduler_status(self, config):
        """Test getting scheduler status."""
        scheduler = SimpleScheduler(config)
        
        status = scheduler.get_scheduler_status()
        
        assert 'running' in status
        assert 'total_jobs' in status
        assert 'active_jobs' in status
        assert 'failed_jobs' in status
        
        scheduler.stop()
    
    def test_calculate_next_run(self, config):
        """Test next run calculation."""
        scheduler = SimpleScheduler(config)
        
        test_time = datetime.now()
        
        # Test job structure
        daily_job = {
            'frequency': ScheduleFrequency.DAILY,
            'last_run': test_time
        }
        
        next_run = scheduler._calculate_next_run(daily_job)
        
        # Should be 1 day later
        assert next_run > test_time
        assert (next_run - test_time).days == 1


class TestMCP:
    """Test main MCP coordinator."""
    
    def test_init_default_config(self):
        """Test MCP initialization with default config."""
        mcp = MCP()
        
        assert mcp.config is not None
        assert mcp.orchestrator is not None
        assert mcp.data_writer is not None
        assert mcp.mcp_state['current_state'] == 'ready'
    
    def test_init_custom_config(self, config):
        """Test MCP initialization with custom config."""
        mcp = MCP(config)
        
        assert mcp.config == config
    
    def test_run_pipeline_validation(self, config):
        """Test pipeline run with validation."""
        mcp = MCP(config)
        
        # Test empty teams list
        with pytest.raises(ValueError, match="No teams specified"):
            mcp.run_pipeline([])
        
        # Test invalid teams
        with pytest.raises(ValueError, match="Invalid teams"):
            mcp.run_pipeline(['invalid_team'])
    
    @patch('nfl_gravity.pipeline.orchestrator.PipelineOrchestrator.run_full_pipeline')
    def test_run_pipeline_success(self, mock_orchestrator, config):
        """Test successful pipeline run."""
        # Mock orchestrator response
        mock_orchestrator.return_value = {
            'teams_processed': 1,
            'total_players': 25,
            'total_teams': 1,
            'output_files': {'players': ['test.parquet']},
            'output_dir': '/test',
            'duration': 120.5,
            'errors': []
        }
        
        mcp = MCP(config)
        result = mcp.run_pipeline(['chiefs'], fast_mode=True)
        
        assert result['teams_processed'] == 1
        assert result['total_players'] == 25
        assert mcp.mcp_state['current_state'] == 'completed'
        assert mcp.mcp_state['total_runs'] == 1
    
    @patch('nfl_gravity.pipeline.orchestrator.PipelineOrchestrator.run_full_pipeline')
    def test_run_pipeline_failure(self, mock_orchestrator, config):
        """Test pipeline run failure."""
        # Mock orchestrator to raise exception
        mock_orchestrator.side_effect = Exception("Pipeline failed")
        
        mcp = MCP(config)
        
        with pytest.raises(NFLGravityError, match="Pipeline execution failed"):
            mcp.run_pipeline(['chiefs'])
        
        assert mcp.mcp_state['current_state'] == 'failed'
    
    def test_get_status(self, config):
        """Test getting MCP status."""
        mcp = MCP(config)
        
        status = mcp.get_status()
        
        assert 'state' in status
        assert 'initialized_at' in status
        assert 'total_runs' in status
        assert 'pipeline_status' in status
        assert 'config_valid' in status
        assert 'data_directory' in status
    
    def test_validate_configuration(self, config):
        """Test configuration validation."""
        mcp = MCP(config)
        
        validation = mcp.validate_configuration()
        
        assert 'valid' in validation
        assert 'messages' in validation
        assert 'components' in validation
        assert 'config_summary' in validation
    
    def test_get_supported_teams(self, config):
        """Test getting supported teams."""
        mcp = MCP(config)
        
        teams = mcp.get_supported_teams()
        
        assert isinstance(teams, list)
        assert len(teams) == 32
        assert 'chiefs' in teams
        assert 'patriots' in teams
    
    def test_stop_pipeline(self, config):
        """Test stopping pipeline."""
        mcp = MCP(config)
        
        # Simulate running state
        mcp.mcp_state['current_state'] = 'running'
        
        mcp.stop_pipeline()
        
        assert mcp.mcp_state['current_state'] == 'stopped'
    
    def test_reset_state(self, config):
        """Test resetting MCP state."""
        mcp = MCP(config)
        
        # Modify state
        mcp.mcp_state['total_runs'] = 5
        mcp.mcp_state['current_state'] = 'completed'
        
        mcp.reset_state()
        
        assert mcp.mcp_state['total_runs'] == 0
        assert mcp.mcp_state['current_state'] == 'ready'
        assert mcp.mcp_state['last_run'] is None
    
    def test_get_version_info(self, config):
        """Test getting version information."""
        mcp = MCP(config)
        
        version_info = mcp.get_version_info()
        
        assert 'version' in version_info
        # May have 'error' key if import fails, which is acceptable
    
    def test_run_health_check(self, config):
        """Test running health check."""
        mcp = MCP(config)
        
        health = mcp.run_health_check()
        
        assert 'overall_healthy' in health
        assert 'timestamp' in health
        assert 'checks' in health
        assert 'configuration' in health['checks']
        assert 'directories' in health['checks']


@pytest.fixture
def sample_pipeline_result():
    """Sample pipeline result for testing."""
    return {
        'status': 'success',
        'teams_processed': 2,
        'total_players': 50,
        'total_teams': 2,
        'output_files': {
            'players': ['players_20240101_120000.parquet', 'players_20240101_120000.csv'],
            'teams': ['teams_20240101_120000.parquet', 'teams_20240101_120000.csv']
        },
        'output_dir': '/tmp/test_data/2024-01-01',
        'duration': 180.5,
        'errors': ['Warning: Could not extract social media for Player X']
    }


class TestPipelineIntegration:
    """Integration tests for pipeline components."""
    
    def test_orchestrator_with_mcp(self, config, sample_pipeline_result):
        """Test orchestrator integration with MCP."""
        mcp = MCP(config)
        
        # Mock the orchestrator
        mcp.orchestrator.run_full_pipeline = Mock(return_value=sample_pipeline_result)
        
        result = mcp.run_pipeline(['chiefs', 'patriots'], fast_mode=True)
        
        assert result == sample_pipeline_result
        assert mcp.mcp_state['total_runs'] == 1
    
    def test_scheduler_with_mcp(self, config):
        """Test scheduler integration with MCP."""
        mcp = MCP(config)
        scheduler = SimpleScheduler(config)
        
        # Schedule a job using MCP's run_pipeline method
        job_id = scheduler.schedule_pipeline(
            mcp.run_pipeline,
            ['chiefs'],
            ScheduleFrequency.DAILY,
            job_name='integration_test'
        )
        
        assert job_id is not None
        
        job_status = scheduler.get_job_status(job_id)
        assert job_status['name'] == 'integration_test'
        
        scheduler.stop()
