"""Pytest configuration and shared fixtures."""

import pytest
import tempfile
import os
import shutil
from unittest.mock import Mock, patch

from nfl_gravity.core.config import Config


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_config(temp_dir):
    """Create a test configuration with temporary directories."""
    config = Config()
    
    # Use temporary directories
    config.data_dir = os.path.join(temp_dir, 'data')
    config.log_dir = os.path.join(temp_dir, 'logs')
    
    # Create directories
    os.makedirs(config.data_dir, exist_ok=True)
    os.makedirs(config.log_dir, exist_ok=True)
    
    # Disable external API calls by default
    config.enable_llm = False
    config.openai_api_key = None
    
    # Reduce delays for faster tests
    config.request_delay_min = 0.1
    config.request_delay_max = 0.2
    
    return config


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
        'games_played': 16,
        'games_started': 16,
        'twitter_handle': 'PatrickMahomes',
        'instagram_handle': 'patrickmahomes',
        'twitter_followers': 4200000,
        'instagram_followers': 5100000,
        'wikipedia_url': 'https://en.wikipedia.org/wiki/Patrick_Mahomes',
        'career_highlights': [
            'Super Bowl Champion (2020, 2023)',
            'Super Bowl MVP (2020)',
            'NFL MVP (2018, 2022)'
        ],
        'awards': [
            'Pro Bowl (2018-2023)',
            'First-team All-Pro (2018, 2022)'
        ],
        'data_source': 'test',
        'scraped_at': '2024-01-01T12:00:00'
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
        'twitter_handle': 'Chiefs',
        'instagram_handle': 'kansascitychiefs',
        'official_website': 'https://www.chiefs.com',
        'data_source': 'test',
        'scraped_at': '2024-01-01T12:00:00'
    }


@pytest.fixture
def mock_requests():
    """Mock requests module for testing."""
    with patch('requests.Session') as mock_session_class:
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Default successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<html><body>Test content</body></html>'
        mock_response.text = '<html><body>Test content</body></html>'
        mock_response.json.return_value = {'test': 'data'}
        mock_response.raise_for_status = Mock()
        
        mock_session.get.return_value = mock_response
        mock_session.post.return_value = mock_response
        
        yield mock_session


@pytest.fixture
def sample_html_content():
    """Sample HTML content for testing scrapers."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test NFL Page</title>
    </head>
    <body>
        <div class="player-info">
            <h1>Patrick Mahomes</h1>
            <table class="infobox">
                <tr>
                    <th>Position</th>
                    <td>Quarterback</td>
                </tr>
                <tr>
                    <th>Height</th>
                    <td>6 ft 3 in</td>
                </tr>
                <tr>
                    <th>Weight</th>
                    <td>230 lb</td>
                </tr>
                <tr>
                    <th>College</th>
                    <td>Texas Tech</td>
                </tr>
                <tr>
                    <th>Draft</th>
                    <td>2017 NFL Draft, 1st round (10th pick)</td>
                </tr>
            </table>
            
            <div class="social-links">
                <a href="https://twitter.com/PatrickMahomes">@PatrickMahomes</a>
                <a href="https://instagram.com/patrickmahomes">@patrickmahomes</a>
            </div>
            
            <div class="career-highlights">
                <h2>Career Highlights</h2>
                <ul>
                    <li>Super Bowl Champion (2020, 2023)</li>
                    <li>Super Bowl MVP (2020)</li>
                    <li>NFL MVP (2018, 2022)</li>
                </ul>
            </div>
        </div>
        
        <div class="team-roster">
            <h2>Kansas City Chiefs Roster</h2>
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Number</th>
                        <th>Position</th>
                        <th>Height</th>
                        <th>Weight</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Patrick Mahomes</td>
                        <td>15</td>
                        <td>QB</td>
                        <td>6-3</td>
                        <td>230</td>
                    </tr>
                    <tr>
                        <td>Travis Kelce</td>
                        <td>87</td>
                        <td>TE</td>
                        <td>6-5</td>
                        <td>250</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    return {
        'twitter_handle': 'PatrickMahomes',
        'instagram_handle': 'patrickmahomes',
        'follower_count': 4200000,
        'following_count': 842,
        'verified': True,
        'bio': 'Kansas City Chiefs Quarterback',
        'confidence': 0.95
    }


@pytest.fixture(autouse=True)
def disable_external_requests(monkeypatch, request):
    """Disable external HTTP requests by default in tests."""
    def mock_get(*args, **kwargs):
        raise Exception("HTTP requests are disabled in tests. Use mock_requests fixture.")

    def mock_post(*args, **kwargs):
        raise Exception("HTTP requests are disabled in tests. Use mock_requests fixture.")

    if 'mock_requests' in request.fixturenames or 'requests_mock' in request.fixturenames:
        return

    monkeypatch.setattr('requests.get', mock_get)
    monkeypatch.setattr('requests.post', mock_post)


# Pytest hooks for better test output
def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (may skip in CI)"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "external: marks tests that require external services"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Mark slow tests
        if "slow" in item.nodeid or "integration" in item.nodeid:
            item.add_marker(pytest.mark.slow)
        
        # Mark integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # Mark external service tests
        if any(keyword in item.nodeid.lower() for keyword in ["api", "external", "network"]):
            item.add_marker(pytest.mark.external)


# Custom assertions for NFL Gravity specific testing
class NFLGravityAssertions:
    """Custom assertions for NFL Gravity testing."""
    
    @staticmethod
    def assert_valid_player_data(player_data):
        """Assert that player data contains required fields."""
        required_fields = ['name', 'team', 'position']
        for field in required_fields:
            assert field in player_data, f"Missing required field: {field}"
            assert player_data[field] is not None, f"Field {field} cannot be None"
            assert player_data[field] != '', f"Field {field} cannot be empty"
    
    @staticmethod
    def assert_valid_team_data(team_data):
        """Assert that team data contains required fields."""
        required_fields = ['name', 'city', 'division', 'conference']
        for field in required_fields:
            assert field in team_data, f"Missing required field: {field}"
            assert team_data[field] is not None, f"Field {field} cannot be None"
            assert team_data[field] != '', f"Field {field} cannot be empty"
    
    @staticmethod
    def assert_valid_nfl_team(team_name):
        """Assert that team name is a valid NFL team."""
        valid_teams = [
            '49ers', 'bears', 'bengals', 'bills', 'broncos', 'browns', 'buccaneers',
            'cardinals', 'chargers', 'chiefs', 'colts', 'commanders', 'cowboys',
            'dolphins', 'eagles', 'falcons', 'giants', 'jaguars', 'jets', 'lions',
            'packers', 'panthers', 'patriots', 'raiders', 'rams', 'ravens',
            'saints', 'seahawks', 'steelers', 'texans', 'titans', 'vikings'
        ]
        assert team_name.lower() in valid_teams, f"Invalid NFL team: {team_name}"


@pytest.fixture
def nfl_assertions():
    """Provide NFL Gravity specific assertions."""
    return NFLGravityAssertions()
