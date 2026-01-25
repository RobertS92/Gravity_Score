"""
Crawler Monitor
Monitors crawler health, performance, and data quality
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict

from gravity.storage import get_storage_manager
from gravity.db.models import CrawlerExecution

logger = logging.getLogger(__name__)


class CrawlerMonitor:
    """
    Monitor crawler health, performance, and data quality
    """
    
    def __init__(self):
        self.storage = get_storage_manager()
        logger.info("Crawler monitor initialized")
    
    def get_crawler_metrics(
        self,
        crawler_name: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get crawler performance metrics
        
        Args:
            crawler_name: Optional crawler name filter
            days: Number of days to analyze
        
        Returns:
            Metrics dict
        """
        try:
            with self.storage.get_session() as session:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                
                query = session.query(CrawlerExecution).filter(
                    CrawlerExecution.started_at >= cutoff_date
                )
                
                if crawler_name:
                    query = query.filter(CrawlerExecution.crawler_name == crawler_name)
                
                executions = query.all()
                
                # Calculate metrics
                metrics = {
                    'total_executions': len(executions),
                    'successful': 0,
                    'failed': 0,
                    'running': 0,
                    'total_events_created': 0,
                    'avg_duration_seconds': 0,
                    'success_rate': 0.0,
                    'errors': []
                }
                
                durations = []
                for exec in executions:
                    if exec.status == 'completed':
                        metrics['successful'] += 1
                        metrics['total_events_created'] += exec.events_created or 0
                        if exec.duration_seconds:
                            durations.append(exec.duration_seconds)
                    elif exec.status == 'failed':
                        metrics['failed'] += 1
                        if exec.errors:
                            metrics['errors'].extend(exec.errors)
                    elif exec.status == 'running':
                        metrics['running'] += 1
                
                if durations:
                    metrics['avg_duration_seconds'] = sum(durations) / len(durations)
                
                if metrics['total_executions'] > 0:
                    metrics['success_rate'] = metrics['successful'] / metrics['total_executions']
                
                return metrics
                
        except Exception as e:
            logger.error(f"Failed to get crawler metrics: {e}")
            return {}
    
    def check_crawler_health(self) -> Dict[str, Any]:
        """
        Check health of all crawlers
        
        Returns:
            Health status dict
        """
        health = {
            'status': 'healthy',
            'crawlers': {},
            'alerts': []
        }
        
        try:
            # Check each crawler
            crawler_names = ['news_article', 'social_media', 'transfer_portal', 
                           'sentiment', 'injury_report', 'brand_partnership', 
                           'game_stats', 'trade']
            
            for crawler_name in crawler_names:
                metrics = self.get_crawler_metrics(crawler_name, days=1)
                
                crawler_health = {
                    'status': 'healthy',
                    'success_rate': metrics.get('success_rate', 0.0),
                    'recent_executions': metrics.get('total_executions', 0),
                    'avg_duration': metrics.get('avg_duration_seconds', 0)
                }
                
                # Check for issues
                if metrics.get('success_rate', 1.0) < 0.7:
                    crawler_health['status'] = 'unhealthy'
                    health['alerts'].append({
                        'crawler': crawler_name,
                        'type': 'low_success_rate',
                        'message': f"Success rate below 70%: {metrics.get('success_rate', 0):.1%}"
                    })
                
                if metrics.get('avg_duration_seconds', 0) > 60:
                    crawler_health['status'] = 'degraded'
                    health['alerts'].append({
                        'crawler': crawler_name,
                        'type': 'slow_execution',
                        'message': f"Average execution time exceeds 60s: {metrics.get('avg_duration_seconds', 0):.1f}s"
                    })
                
                if metrics.get('failed', 0) >= 3:
                    crawler_health['status'] = 'unhealthy'
                    health['alerts'].append({
                        'crawler': crawler_name,
                        'type': 'multiple_failures',
                        'message': f"{metrics.get('failed', 0)} failures in last 24 hours"
                    })
                
                health['crawlers'][crawler_name] = crawler_health
            
            # Overall status
            unhealthy_count = sum(1 for c in health['crawlers'].values() if c['status'] == 'unhealthy')
            if unhealthy_count > 0:
                health['status'] = 'unhealthy'
            elif any(c['status'] == 'degraded' for c in health['crawlers'].values()):
                health['status'] = 'degraded'
            
            return health
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_data_quality_metrics(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get data quality metrics
        
        Args:
            days: Number of days to analyze
        
        Returns:
            Data quality metrics dict
        """
        try:
            with self.storage.get_session() as session:
                from gravity.db.models import AthleteEvent
                
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                
                # Get events created by crawlers
                events = session.query(AthleteEvent).filter(
                    AthleteEvent.created_at >= cutoff_date,
                    AthleteEvent.crawler_name.isnot(None)
                ).all()
                
                metrics = {
                    'total_events': len(events),
                    'events_by_crawler': defaultdict(int),
                    'events_by_type': defaultdict(int),
                    'events_by_sport': defaultdict(int),
                    'avg_confidence': 0.0
                }
                
                confidences = []
                for event in events:
                    metrics['events_by_crawler'][event.crawler_name] += 1
                    metrics['events_by_type'][event.event_type] += 1
                    
                    # Try to extract confidence from raw_data
                    if event.raw_data and isinstance(event.raw_data, dict):
                        confidence = event.raw_data.get('confidence', None)
                        if confidence:
                            confidences.append(confidence)
                
                if confidences:
                    metrics['avg_confidence'] = sum(confidences) / len(confidences)
                
                return metrics
                
        except Exception as e:
            logger.error(f"Failed to get data quality metrics: {e}")
            return {}
    
    def get_score_recalculation_metrics(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get score recalculation metrics
        
        Args:
            days: Number of days to analyze
        
        Returns:
            Recalculation metrics dict
        """
        try:
            with self.storage.get_session() as session:
                from gravity.db.models import ScoreRecalculation
                
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                
                recalculations = session.query(ScoreRecalculation).filter(
                    ScoreRecalculation.recalculated_at >= cutoff_date
                ).all()
                
                metrics = {
                    'total_recalculations': len(recalculations),
                    'recalculations_by_event_type': defaultdict(int),
                    'avg_score_delta': 0.0,
                    'components_recalculated': defaultdict(int)
                }
                
                deltas = []
                for recalc in recalculations:
                    if recalc.trigger_event_type:
                        metrics['recalculations_by_event_type'][recalc.trigger_event_type] += 1
                    
                    if recalc.score_delta:
                        deltas.append(abs(recalc.score_delta))
                    
                    if recalc.components_recalculated:
                        for component in recalc.components_recalculated:
                            metrics['components_recalculated'][component] += 1
                
                if deltas:
                    metrics['avg_score_delta'] = sum(deltas) / len(deltas)
                
                return metrics
                
        except Exception as e:
            logger.error(f"Failed to get recalculation metrics: {e}")
            return {}
