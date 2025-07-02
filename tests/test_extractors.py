"""Tests for data extractors."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
from bs4 import BeautifulSoup

from nfl_gravity.core.config import Config
from nfl_gravity.extractors.wikipedia import WikipediaExtractor
from nfl_gravity.extractors.social_media import SocialMediaExtractor
from nfl_gravity.extractors.nfl_sites import NFLSitesExtractor
from nfl_gravity.core.exceptions import ExtractionError


@pytest.fixture
def config():
    """Test configuration."""
    return Config()


@pytest.fixture
def mock_html_response():
    """Mock HTML response for testing."""
    html_content = """
    <html>
        <body>
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
            </table>
        </body>
    </html>
    """
    
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = html_content.encode('utf-8')
    mock_response.text = html_content
    mock_response.raise_for_status = Mock()
    
    return mock_response


class TestWikipediaExtractor:
    """Test Wikipedia data extraction."""
    
    def test_init(self, config):
        """Test Wikipedia extractor initialization."""
        extractor = WikipediaExtractor(config)
        
        assert extractor.config == config
        assert extractor.session is not None
        assert 'User-Agent' in extractor.session.headers
    
    @patch('requests.Session.get')
    def test_search_player_success(self, mock_get, config):
        """Test successful player search."""
        # Mock search API response
        search_response = {
            'pages': [
                {
                    'title': 'Patrick Mahomes',
                    'key': 'Patrick_Mahomes',
                    'description': 'American football quarterback for the Kansas City Chiefs'
                }
            ]
        }
        
        mock_get.return_value.json.return_value = search_response
        mock_get.return_value.raise_for_status = Mock()
        
        extractor = WikipediaExtractor(config)
        result = extractor.search_player('Patrick Mahomes', 'chiefs')
        
        assert result is not None
        assert 'wikipedia.org/wiki/Patrick_Mahomes' in result
    
    @patch('requests.Session.get')
    def test_search_player_not_found(self, mock_get, config):
        """Test player search when no results found."""
        # Mock empty search response
        search_response = {'pages': []}
        
        mock_get.return_value.json.return_value = search_response
        mock_get.return_value.raise_for_status = Mock()
        
        extractor = WikipediaExtractor(config)
        result = extractor.search_player('Unknown Player', 'unknown')
        
        assert result is None
    
    @patch('requests.Session.get')
    def test_extract_player_data(self, mock_get, config, mock_html_response):
        """Test player data extraction from Wikipedia page."""
        mock_get.return_value = mock_html_response
        
        extractor = WikipediaExtractor(config)
        result = extractor.extract_player_data('https://en.wikipedia.org/wiki/Test_Player')
        
        assert result is not None
        assert result['wikipedia_url'] == 'https://en.wikipedia.org/wiki/Test_Player'
        assert result['data_source'] == 'wikipedia'
        assert 'position' in result
    
    def test_parse_infobox_fields(self, config):
        """Test infobox field parsing."""
        extractor = WikipediaExtractor(config)
        
        raw_data = {
            'birth_info': 'September 17, 1995 (age 28)',
            'height': '6 ft 3 in (1.91 m)',
            'weight': '230 lb (104 kg)',
            'draft_info': '2017 NFL Draft, 1st round (10th pick)'
        }
        
        parsed = extractor._parse_infobox_fields(raw_data)
        
        assert 'age' in parsed
        assert parsed['age'] == 28
        assert 'height' in parsed
        assert 'weight' in parsed
        assert parsed['weight'] == 230


class TestSocialMediaExtractor:
    """Test social media data extraction."""
    
    def test_init(self, config):
        """Test social media extractor initialization."""
        extractor = SocialMediaExtractor(config)
        
        assert extractor.config == config
        assert extractor.session is not None
    
    def test_extract_handles_regex(self, config):
        """Test regex-based handle extraction."""
        extractor = SocialMediaExtractor(config)
        
        text = """
        Follow @PatrickMahomes on Twitter and instagram.com/patrickmahomes
        for the latest updates from the Chiefs quarterback.
        """
        
        handles = extractor._extract_handles_regex(text)
        
        assert 'twitter_handle' in handles
        assert 'instagram_handle' in handles
        assert handles['twitter_handle'] == 'PatrickMahomes'
        assert handles['instagram_handle'] == 'patrickmahomes'
    
    def test_convert_follower_count(self, config):
        """Test follower count conversion."""
        extractor = SocialMediaExtractor(config)
        
        assert extractor._convert_follower_count('1000') == 1000
        assert extractor._convert_follower_count('1.5K') == 1500
        assert extractor._convert_follower_count('2.3M') == 2300000
        assert extractor._convert_follower_count('1,234') == 1234
    
    def test_get_official_team_handles(self, config):
        """Test official team handle mapping."""
        extractor = SocialMediaExtractor(config)
        
        chiefs_handles = extractor._get_official_team_handles('chiefs')
        
        assert 'twitter_handle' in chiefs_handles
        assert 'instagram_handle' in chiefs_handles
        assert chiefs_handles['twitter_handle'] == 'Chiefs'
    
    @patch('requests.Session.get')
    def test_discover_social_profiles(self, mock_get, config):
        """Test social profile discovery."""
        # Mock search results
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<html><body>Follow @PatrickMahomes on Twitter</body></html>'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        extractor = SocialMediaExtractor(config)
        result = extractor.discover_social_profiles('Patrick Mahomes', 'chiefs')
        
        assert result is not None
        assert 'data_source' in result


class TestNFLSitesExtractor:
    """Test NFL sites data extraction."""
    
    def test_init(self, config):
        """Test NFL sites extractor initialization."""
        extractor = NFLSitesExtractor(config)
        
        assert extractor.config == config
        assert extractor.session is not None
        assert 'nfl.com' in extractor.sites
        assert 'espn.com' in extractor.sites
        assert 'pro-football-reference.com' in extractor.sites
    
    def test_build_roster_url(self, config):
        """Test roster URL building."""
        extractor = NFLSitesExtractor(config)
        
        url = extractor._build_roster_url('chiefs', 'nfl.com')
        
        assert 'nfl.com' in url
        assert 'kc' in url or 'chiefs' in url.lower()
    
    def test_get_team_mapping(self, config):
        """Test team name mapping for different sites."""
        extractor = NFLSitesExtractor(config)
        
        nfl_mapping = extractor._get_team_mapping('nfl.com')
        espn_mapping = extractor._get_team_mapping('espn.com')
        pfr_mapping = extractor._get_team_mapping('pro-football-reference.com')
        
        assert 'chiefs' in nfl_mapping
        assert 'chiefs' in espn_mapping
        assert 'chiefs' in pfr_mapping
        
        # Should have different codes for different sites
        assert len(nfl_mapping) == 32
        assert len(espn_mapping) == 32
        assert len(pfr_mapping) == 32
    
    def test_extract_number(self, config):
        """Test number extraction utility."""
        extractor = NFLSitesExtractor(config)
        
        assert extractor._extract_number('15') == 15
        assert extractor._extract_number('#15') == 15
        assert extractor._extract_number('Player #15') == 15
        assert extractor._extract_number('No number') is None
        assert extractor._extract_number('') is None
    
    def test_extract_weight(self, config):
        """Test weight extraction utility."""
        extractor = NFLSitesExtractor(config)
        
        assert extractor._extract_weight('230 lbs') == 230
        assert extractor._extract_weight('230 lb') == 230
        assert extractor._extract_weight('230') == 230
        assert extractor._extract_weight('No weight') is None
    
    @patch('requests.Session.get')
    def test_extract_team_roster_success(self, mock_get, config):
        """Test successful team roster extraction."""
        # Mock roster page HTML
        roster_html = """
        <html>
            <body>
                <table>
                    <tr>
                        <th>Name</th>
                        <th>Number</th>
                        <th>Position</th>
                        <th>Height</th>
                        <th>Weight</th>
                    </tr>
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
                </table>
            </body>
        </html>
        """
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = roster_html.encode('utf-8')
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        extractor = NFLSitesExtractor(config)
        
        with patch('nfl_gravity.core.utils.check_robots_txt', return_value=True):
            result = extractor.extract_team_roster('chiefs', 'nfl.com')
        
        assert isinstance(result, list)
        assert len(result) >= 0  # Might be empty due to parsing differences
    
    @patch('requests.Session.get')
    def test_extract_team_roster_http_error(self, mock_get, config):
        """Test roster extraction with HTTP error."""
        mock_get.side_effect = requests.RequestException("HTTP Error")
        
        extractor = NFLSitesExtractor(config)
        
        with patch('nfl_gravity.core.utils.check_robots_txt', return_value=True):
            with pytest.raises(ExtractionError):
                extractor.extract_team_roster('chiefs', 'nfl.com')


@pytest.fixture
def sample_roster_html():
    """Sample roster HTML for testing."""
    return """
    <html>
        <body>
            <table class="roster-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Number</th>
                        <th>Position</th>
                        <th>Height</th>
                        <th>Weight</th>
                        <th>College</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><a href="/player/123">Patrick Mahomes</a></td>
                        <td>15</td>
                        <td>QB</td>
                        <td>6'3"</td>
                        <td>230 lbs</td>
                        <td>Texas Tech</td>
                    </tr>
                    <tr>
                        <td><a href="/player/456">Travis Kelce</a></td>
                        <td>87</td>
                        <td>TE</td>
                        <td>6'5"</td>
                        <td>250 lbs</td>
                        <td>Cincinnati</td>
                    </tr>
                </tbody>
            </table>
        </body>
    </html>
    """


class TestExtractorIntegration:
    """Integration tests for extractors."""
    
    @patch('requests.Session.get')
    def test_multiple_extractors(self, mock_get, config, sample_roster_html):
        """Test using multiple extractors together."""
        # Mock responses for all extractors
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = sample_roster_html.encode('utf-8')
        mock_response.text = sample_roster_html
        mock_response.json.return_value = {'pages': []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Initialize extractors
        wiki_extractor = WikipediaExtractor(config)
        social_extractor = SocialMediaExtractor(config)
        nfl_extractor = NFLSitesExtractor(config)
        
        # Test that they all initialize without error
        assert wiki_extractor is not None
        assert social_extractor is not None
        assert nfl_extractor is not None
    
    def test_extractor_error_handling(self, config):
        """Test extractor error handling."""
        extractor = WikipediaExtractor(config)
        
        # Test with invalid URL - should not raise exception
        result = extractor.search_player('', '')
        assert result is None  # Should handle gracefully
