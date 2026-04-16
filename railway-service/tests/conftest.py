"""
PyTest configuration and fixtures
Provides reusable test fixtures and test execution tracking
"""

import pytest
from app.services.supabase_client import get_supabase_client
from app.config import settings
import time
import os
import logging

logger = logging.getLogger(__name__)


@pytest.fixture
def supabase():
    """
    Supabase client fixture
    
    Returns:
        Supabase Client instance for testing
    """
    client = get_supabase_client()
    if client is None:
        pytest.skip("Supabase not configured (set SUPABASE_URL and SUPABASE_SERVICE_KEY)")
    return client


@pytest.fixture
def test_athlete_id():
    """
    Fixture providing a test athlete ID
    
    Returns:
        UUID string for testing
    """
    return "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def test_api_key():
    """
    Fixture providing test API key
    
    Returns:
        API key string for testing
    """
    return os.getenv('API_KEY', 'test_key')


@pytest.fixture(autouse=True)
def track_test_execution(request):
    """
    Auto-track all test executions to database
    
    This fixture runs automatically for every test and records:
    - Test name
    - Test type (from markers)
    - Pass/fail status
    - Duration
    - Error messages if failed
    
    Args:
        request: PyTest request object
    """
    test_name = request.node.name
    test_type = 'unit'  # Default
    
    # Determine test type from markers
    if request.node.get_closest_marker('integration'):
        test_type = 'integration'
    elif request.node.get_closest_marker('e2e'):
        test_type = 'e2e'
    
    start_time = time.time()
    
    # Run the test
    yield
    
    # Calculate duration
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Determine test status
    if hasattr(request.node, 'rep_call'):
        status = 'passed' if request.node.rep_call.passed else 'failed'
        error_msg = str(request.node.rep_call.longrepr) if status == 'failed' else None
    else:
        status = 'skipped'
        error_msg = None
    
    # Store in database (only if running with real database)
    if settings.supabase_enabled and not os.getenv('SKIP_TEST_TRACKING'):
        try:
            supabase = get_supabase_client()
            if supabase is None:
                return
            supabase.table('test_executions').insert({
                'test_name': test_name,
                'test_type': test_type,
                'status': status,
                'duration_ms': duration_ms,
                'error_message': error_msg[:1000] if error_msg else None  # Limit length
            }).execute()
            logger.info(f"Tracked test: {test_name} ({status}) - {duration_ms}ms")
        except Exception as e:
            logger.warning(f"Failed to track test execution: {e}")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Hook to attach test result to item for tracking
    
    This allows the track_test_execution fixture to access test results
    """
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


@pytest.fixture
def mock_athlete_data():
    """
    Fixture providing mock athlete data for testing
    
    Returns:
        Dict with sample athlete data
    """
    return {
        'athlete_id': '00000000-0000-0000-0000-000000000001',
        'canonical_name': 'Test Athlete',
        'sport': 'cfb',
        'school': 'Test University',
        'position': 'QB',
        'is_active': True
    }


@pytest.fixture
def mock_scraper_result():
    """
    Fixture providing mock scraper result
    
    Returns:
        Dict with sample scraper result
    """
    return {
        'success': True,
        'league': 'cfb',
        'athlete_id': '00000000-0000-0000-0000-000000000001',
        'data': {
            'name': 'Test Athlete',
            'stats': {},
            'social': {}
        }
    }


@pytest.fixture
def mock_crawler_result():
    """
    Fixture providing mock crawler result
    
    Returns:
        Dict with sample crawler result
    """
    return {
        'success': True,
        'athlete_id': '00000000-0000-0000-0000-000000000001',
        'crawlers_run': ['news_article', 'social_media'],
        'events_created': 5
    }
