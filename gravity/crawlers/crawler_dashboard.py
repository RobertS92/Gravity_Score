"""
Crawler Dashboard
Web dashboard for monitoring crawler status (simplified version)
"""

import logging
from typing import Dict, Any
from datetime import datetime

from gravity.crawlers.crawler_monitor import CrawlerMonitor
from gravity.crawlers.crawler_orchestrator import CrawlerOrchestrator

logger = logging.getLogger(__name__)


class CrawlerDashboard:
    """
    Provides dashboard data for crawler monitoring
    """
    
    def __init__(self):
        self.monitor = CrawlerMonitor()
        self.orchestrator = CrawlerOrchestrator()
        logger.info("Crawler dashboard initialized")
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get all dashboard data
        
        Returns:
            Complete dashboard data dict
        """
        try:
            # Get crawler status
            crawler_status = self.orchestrator.get_crawler_status()
            
            # Get health status
            health_status = self.monitor.check_crawler_health()
            
            # Get performance metrics
            performance_metrics = {}
            for crawler_name in crawler_status['crawlers'].keys():
                performance_metrics[crawler_name] = self.monitor.get_crawler_metrics(
                    crawler_name,
                    days=7
                )
            
            # Get data quality metrics
            data_quality = self.monitor.get_data_quality_metrics(days=7)
            
            # Get score recalculation metrics
            recalculation_metrics = self.monitor.get_score_recalculation_metrics(days=7)
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'crawler_status': crawler_status,
                'health_status': health_status,
                'performance_metrics': performance_metrics,
                'data_quality': data_quality,
                'recalculation_metrics': recalculation_metrics
            }
            
        except Exception as e:
            logger.error(f"Failed to get dashboard data: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
