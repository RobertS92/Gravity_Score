"""CrawlerService is a stub; external repo owns crawlers."""

import pytest
from app.services.crawler_service import CrawlerService


@pytest.mark.unit
def test_crawler_service_init():
    service = CrawlerService()
    assert service is not None
    assert service.orchestrator is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_all_crawlers_skipped():
    service = CrawlerService()
    result = await service.run_all_crawlers("test-athlete-id")
    assert result["success"] is True
    assert result.get("skipped") is True
    assert "external" in result["message"].lower()


@pytest.mark.unit
def test_get_crawler_status():
    service = CrawlerService()
    status = service.get_crawler_status()
    assert status["available"] is False


@pytest.mark.unit
def test_get_available_crawlers():
    service = CrawlerService()
    assert service.get_available_crawlers() == []
