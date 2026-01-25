"""
Tests for crawler service
"""

import pytest
from app.services.crawler_service import CrawlerService
from unittest.mock import Mock, patch, AsyncMock
import uuid


@pytest.mark.unit
def test_crawler_service_init():
    """Test crawler service initialization"""
    service = CrawlerService()
    assert service is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_all_crawlers_not_available():
    """Test running crawlers when orchestrator not available"""
    service = CrawlerService()
    service.orchestrator = None
    
    result = await service.run_all_crawlers('test-id')
    
    assert result['success'] == False
    assert 'not available' in result['error']


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_all_crawlers_success(test_athlete_id, mock_crawler_result):
    """Test successfully running all crawlers"""
    service = CrawlerService()
    
    if not service.orchestrator:
        pytest.skip("Crawler orchestrator not available")
    
    with patch.object(service.orchestrator, 'run_all_crawlers', new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_crawler_result
        
        result = await service.run_all_crawlers(test_athlete_id)
        
        assert result is not None
        mock_run.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_single_crawler(test_athlete_id):
    """Test running a single crawler"""
    service = CrawlerService()
    
    if not service.orchestrator:
        pytest.skip("Crawler orchestrator not available")
    
    with patch.object(service.orchestrator, 'run_crawler', new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {'success': True, 'events_created': 2}
        
        result = await service.run_crawler('news_article', test_athlete_id)
        
        assert result is not None
        mock_run.assert_called_once_with('news_article', uuid.UUID(test_athlete_id))


@pytest.mark.unit
def test_get_crawler_status():
    """Test getting crawler status"""
    service = CrawlerService()
    
    if not service.orchestrator:
        status = service.get_crawler_status()
        assert status['available'] == False
    else:
        with patch.object(service.orchestrator, 'get_crawler_status', return_value={}):
            status = service.get_crawler_status()
            assert status['available'] == True


@pytest.mark.unit
def test_get_available_crawlers():
    """Test getting list of available crawlers"""
    service = CrawlerService()
    
    crawlers = service.get_available_crawlers()
    
    # Should return a list (empty or with crawler names)
    assert isinstance(crawlers, list)
    
    # If orchestrator is available, should have known crawlers
    if service.orchestrator:
        expected_crawlers = [
            'news_article', 'social_media', 'transfer_portal',
            'sentiment', 'injury_report', 'brand_partnership',
            'game_stats', 'trade'
        ]
        for crawler in expected_crawlers:
            assert crawler in crawlers
