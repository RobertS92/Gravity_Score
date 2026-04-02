"""
Integration tests for crawlers
"""

import asyncio
from datetime import date, datetime
import uuid

import pytest

try:
    from gravity.crawlers.crawler_orchestrator import CrawlerOrchestrator
    from gravity.crawlers.crawler_monitor import CrawlerMonitor
    from gravity.crawlers.event_processor import EventProcessor
    from gravity.crawlers.score_recalculator import ScoreRecalculator
except ImportError:  # gravity.crawlers removed — scrapers rebuilt under gravity.scrapers
    pytest.skip(
        "gravity.crawlers package removed; use gravity.scrapers instead",
        allow_module_level=True,
    )


@pytest.mark.asyncio
async def test_news_crawler_integration():
    """Test news crawler → event storage → score recalculation"""
    # This is a placeholder test - would need actual test data
    pass


@pytest.mark.asyncio
async def test_game_stats_crawler():
    """Test stats → features → Proof/Velocity scores"""
    # This is a placeholder test - would need actual test data
    pass


@pytest.mark.asyncio
async def test_event_driven_recalculation():
    """Test event → automatic score update"""
    # This is a placeholder test - would need actual test data
    pass


@pytest.mark.asyncio
async def test_crawler_orchestrator():
    """Test running multiple crawlers"""
    orchestrator = CrawlerOrchestrator()
    
    # Test getting crawler status
    status = orchestrator.get_crawler_status()
    assert 'crawlers' in status
    assert len(status['crawlers']) == 8  # 8 crawlers


@pytest.mark.asyncio
async def test_score_recalculation():
    """Test feature → component → Gravity score pipeline"""
    # This is a placeholder test - would need actual test data
    pass


@pytest.mark.asyncio
async def test_event_processor():
    """Test event processor event-to-score mapping"""
    processor = EventProcessor()
    
    # Test getting affected components
    components = processor.get_affected_components('trade_completed')
    assert 'proximity' in components
    assert 'risk' in components
    assert 'proof' in components


@pytest.mark.asyncio
async def test_crawler_monitor():
    """Test crawler monitoring"""
    monitor = CrawlerMonitor()
    
    # Test health check
    health = monitor.check_crawler_health()
    assert 'status' in health
    assert 'crawlers' in health


def test_crawler_base_class():
    """Test base crawler functionality"""
    from gravity.crawlers.base_crawler import BaseCrawler
    
    # Base class is abstract, so we test through concrete implementations
    from gravity.crawlers.news_article_crawler import NewsArticleCrawler
    
    crawler = NewsArticleCrawler()
    assert crawler.get_crawler_name() == 'news_article'
    assert 'nfl' in crawler.get_supported_sports()
