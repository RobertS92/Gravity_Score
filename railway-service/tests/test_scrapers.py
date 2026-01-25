"""
Tests for scraper service
"""

import pytest
from app.services.scraper_service import ScraperService
from unittest.mock import Mock, patch


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scraper_service_init():
    """Test scraper service initialization"""
    service = ScraperService()
    assert service is not None
    assert service.supabase is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_athlete_invalid_league(mock_athlete_data):
    """Test scraping with invalid league"""
    service = ScraperService()
    
    with patch.object(service.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = mock_athlete_data
        
        result = await service.scrape_athlete(
            mock_athlete_data['athlete_id'],
            'invalid_league'
        )
        
        assert result['success'] == False
        assert 'error' in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_athlete_not_found():
    """Test scraping with non-existent athlete"""
    service = ScraperService()
    
    with patch.object(service.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = None
        
        with pytest.raises(ValueError, match="not found"):
            await service.scrape_athlete('nonexistent-id', 'cfb')


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_nil_success(mock_athlete_data, mock_scraper_result):
    """Test successful NIL scraping"""
    service = ScraperService()
    
    if not service.nil_orchestrator:
        pytest.skip("NIL orchestrator not available")
    
    with patch.object(service.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = mock_athlete_data
        
        with patch.object(service.nil_orchestrator, 'collect_all', return_value=mock_scraper_result['data']):
            result = await service.scrape_athlete(
                mock_athlete_data['athlete_id'],
                'cfb',
                store_results=False
            )
            
            assert result['success'] == True
            assert result['league'] == 'nil'


@pytest.mark.unit
def test_scraper_service_availability():
    """Test which scrapers are available"""
    service = ScraperService()
    
    # At least one scraper should be available
    available = [
        service.nil_orchestrator is not None,
        service.nfl_scraper is not None,
        service.nba_scraper is not None
    ]
    
    assert any(available), "At least one scraper should be available"
