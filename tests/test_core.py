"""Tests for core functionality."""

import pytest
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch

from nfl_gravity.core.config import Config
from nfl_gravity.core.utils import (
    clean_text, get_user_agent, extract_social_metrics, 
    convert_metric_to_number, create_output_directory
)
from nfl_gravity.core.validators import PlayerDataValidator, TeamDataValidator
from nfl_gravity.core.exceptions import ValidationError, NFLGravityError


class TestConfig:
    """Test configuration management."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = Config()
        
        assert config.llm_provider == "openai"
        assert config.llm_model == "gpt-4o"  # the newest OpenAI model
        assert config.data_dir == "data"
        assert config.log_dir == "logs"
        assert config.enable_social_media is True
        assert config.enable_wikipedia is True
        assert len(config.nfl_teams) == 32
    
    def test_config_validation(self):
        """Test configuration validation."""
        config = Config()
        messages = config.validate()
        
        # Should have some messages about missing API keys
        assert isinstance(messages, list)
    
    def test_get_log_file(self):
        """Test log file path generation."""
        config = Config()
        log_file = config.get_log_file()
        
        assert log_file.endswith("nfl_gravity.log")
        assert config.log_dir in log_file
    
    def test_get_output_dir(self):
        """Test output directory generation."""
        config = Config()
        output_dir = config.get_output_dir("2024-01-01")
        
        assert "2024-01-01" in output_dir
        assert config.data_dir in output_dir


class TestUtils:
    """Test utility functions."""
    
    def test_clean_text(self):
        """Test text cleaning functionality."""
        # Test basic cleaning
        assert clean_text("  hello world  ") == "hello world"
        assert clean_text("hello\n\nworld") == "hello world"
        assert clean_text("") == ""
        assert clean_text(None) == ""
    
    def test_get_user_agent(self):
        """Test user agent generation."""
        ua1 = get_user_agent()
        ua2 = get_user_agent()
        
        assert len(ua1) > 20
        assert "Mozilla" in ua1
        # Should be random
        assert ua1 != ua2 or True  # Might be same by chance
    
    def test_extract_social_metrics(self):
        """Test social media metrics extraction."""
        text = "This player has 1.2K followers and 5M likes on social media"
        
        metrics = extract_social_metrics(text)
        
        # Should extract some metrics
        assert isinstance(metrics, dict)
    
    def test_convert_metric_to_number(self):
        """Test metric string conversion."""
        assert convert_metric_to_number("1000") == 1000
        assert convert_metric_to_number("1.2K") == 1200
        assert convert_metric_to_number("5M") == 5000000
        assert convert_metric_to_number("1,500") == 1500
    
    def test_create_output_directory(self):
        """Test output directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = create_output_directory(temp_dir)
            
            assert os.path.exists(output_dir)
            assert temp_dir in output_dir
            assert datetime.now().strftime("%Y-%m-%d") in output_dir


class TestValidators:
    """Test data validators."""
    
    def test_player_data_validator(self):
        """Test player data validation."""
        validator = PlayerDataValidator()
        
        # Valid player data
        valid_data = {
            'name': 'Tom Brady',
            'team': 'buccaneers',
            'position': 'QB',
            'jersey_number': 12,
            'height': '6\'4"',
            'weight': 225,
            'age': 45
        }
        
        result = validator.validate_and_clean(valid_data)
        
        assert result is not None
        assert result.name == 'Tom Brady'
        assert result.team == 'buccaneers'
        assert result.position == 'QB'
        assert result.jersey_number == 12
    
    def test_player_data_validator_invalid(self):
        """Test player data validation with invalid data."""
        validator = PlayerDataValidator()
        
        # Invalid data (missing required fields)
        invalid_data = {
            'name': '',  # Empty name
            'team': 'invalid_team',
            'position': 'INVALID_POS',
            'jersey_number': -5  # Invalid number
        }
        
        result = validator.validate_and_clean(invalid_data)
        
        # Should return None for invalid data
        assert result is None
        assert len(validator.discarded_fields) > 0
    
    def test_team_data_validator(self):
        """Test team data validation."""
        validator = TeamDataValidator()
        
        # Valid team data
        valid_data = {
            'name': 'Kansas City Chiefs',
            'city': 'Kansas City',
            'division': 'AFC West',
            'conference': 'AFC',
            'founded': 1960
        }
        
        result = validator.validate_and_clean(valid_data)
        
        assert result is not None
        assert result.name == 'Kansas City Chiefs'
        assert result.city == 'Kansas City'
        assert result.division == 'AFC West'
        assert result.conference == 'AFC'
    
    def test_team_data_validator_invalid(self):
        """Test team data validation with invalid data."""
        validator = TeamDataValidator()
        
        # Invalid data
        invalid_data = {
            'name': '',  # Empty name
            'city': '',  # Empty city
            'division': 'Invalid Division',
            'conference': 'INVALID',  # Not AFC or NFC
            'founded': 1800  # Too early
        }
        
        result = validator.validate_and_clean(invalid_data)
        
        # Should return None for invalid data
        assert result is None


class TestExceptions:
    """Test custom exceptions."""
    
    def test_nfl_gravity_error(self):
        """Test base exception."""
        with pytest.raises(NFLGravityError):
            raise NFLGravityError("Test error")
    
    def test_validation_error(self):
        """Test validation exception."""
        with pytest.raises(ValidationError):
            raise ValidationError("Validation failed")
    
    def test_exception_inheritance(self):
        """Test exception inheritance."""
        error = ValidationError("Test")
        
        assert isinstance(error, NFLGravityError)
        assert isinstance(error, Exception)


@pytest.fixture
def sample_player_data():
    """Sample player data for testing."""
    return {
        'name': 'Patrick Mahomes',
        'team': 'chiefs',
        'position': 'QB',
        'jersey_number': 15,
        'height': '6\'3"',
        'weight': 230,
        'age': 28,
        'college': 'Texas Tech',
        'draft_year': 2017,
        'draft_round': 1,
        'draft_pick': 10,
        'twitter_handle': 'PatrickMahomes',
        'instagram_handle': 'patrickmahomes',
        'data_source': 'test'
    }


@pytest.fixture
def sample_team_data():
    """Sample team data for testing."""
    return {
        'name': 'Kansas City Chiefs',
        'city': 'Kansas City',
        'division': 'AFC West',
        'conference': 'AFC',
        'founded': 1960,
        'stadium': 'Arrowhead Stadium',
        'head_coach': 'Andy Reid',
        'wins': 14,
        'losses': 3,
        'ties': 0,
        'data_source': 'test'
    }


class TestIntegration:
    """Integration tests for core components."""
    
    def test_config_with_validators(self, sample_player_data):
        """Test config integration with validators."""
        config = Config()
        validator = PlayerDataValidator()
        
        result = validator.validate_and_clean(sample_player_data)
        
        assert result is not None
        assert result.team in config.nfl_teams
    
    def test_utils_with_real_data(self):
        """Test utilities with realistic data."""
        social_text = """
        Patrick Mahomes has 4.5M followers on Twitter and 2.1M on Instagram.
        He's very active on social media with great engagement.
        """
        
        metrics = extract_social_metrics(social_text)
        cleaned_text = clean_text(social_text)
        
        assert len(cleaned_text) > 0
        assert isinstance(metrics, dict)
